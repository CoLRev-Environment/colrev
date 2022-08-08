#! /usr/bin/env python
import json
import logging
import pkgutil
import typing
from pathlib import Path
from subprocess import CalledProcessError
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT

import git

import colrev_core.exceptions as colrev_exceptions
from colrev_core.environment import EnvironmentManager
from colrev_core.review_manager import ReviewManager
from colrev_core.settings import ReviewType


class colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    ORANGE = "\033[93m"
    BLUE = "\033[94m"
    END = "\033[0m"


class Initializer:

    SHARE_STAT_REQ_options = ["NONE", "PROCESSED", "SCREENED", "COMPLETED"]

    def __init__(
        self,
        *,
        project_name: str,
        SHARE_STAT_REQ: str,
        review_type: str,
        url: str = "NA",
        example: bool = False,
        local_index_repo: bool = False,
    ) -> None:

        saved_args = locals()

        assert not (example and local_index_repo)
        if project_name is not None:
            self.project_name = project_name
        else:
            self.project_name = str(Path.cwd().name)
        if SHARE_STAT_REQ not in self.SHARE_STAT_REQ_options:
            raise colrev_exceptions.ParameterError(
                parameter="init.SHARE_STAT_REQ",
                value=SHARE_STAT_REQ,
                options=self.SHARE_STAT_REQ_options,
            )

        if review_type not in ReviewType._member_names_:
            raise colrev_exceptions.ParameterError(
                parameter="init.review_type",
                value=f"'{review_type}'",
                options=ReviewType._member_names_,
            )

        self.instructions: typing.List[str] = []
        self.SHARE_STAT_REQ = SHARE_STAT_REQ
        self.review_type = review_type
        self.url = url

        self.logger = self.__setup_init_logger(level=logging.INFO)

        self.__require_empty_directory()
        self.logger.info("Setup files")
        self.__setup_files()
        self.logger.info("Setup git")
        self.__setup_git()
        self.logger.info("Create commit")
        if example:
            self.__create_example_repo()

        self.REVIEW_MANAGER = ReviewManager()

        self.__create_commit(saved_args=saved_args)
        if not example:
            self.REVIEW_MANAGER.logger.info("Register repo")
            self.__register_repo()
        if local_index_repo:
            self.__create_local_index()

        self.REVIEW_MANAGER.logger.info("Post-commit edits")
        self.__post_commit_edits()

        print("\n")
        for instruction in self.instructions:
            self.REVIEW_MANAGER.logger.info(instruction)

    def __setup_init_logger(self, *, level=logging.INFO) -> logging.Logger:

        init_logger = logging.getLogger("colrev_core-init_logger")

        init_logger.setLevel(level)

        if init_logger.handlers:
            for handler in init_logger.handlers:
                init_logger.removeHandler(handler)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(level)

        init_logger.addHandler(handler)
        init_logger.propagate = False

        return init_logger

    def __register_repo(self) -> None:

        EnvironmentManager.register_repo(path_to_register=Path.cwd())

    def __create_commit(self, *, saved_args: dict) -> None:

        self.REVIEW_MANAGER.report_logger.info("Initialize review repository")
        self.REVIEW_MANAGER.report_logger.info(
            f'{"Set project title:".ljust(30, " ")}{self.project_name}'
        )
        self.REVIEW_MANAGER.report_logger.info(
            f'{"Set SHARE_STAT_REQ:".ljust(30, " ")}{self.SHARE_STAT_REQ}'
        )
        del saved_args["local_index_repo"]
        self.REVIEW_MANAGER.create_commit(
            msg="Initial commit",
            manual_author=True,
            script_call="colrev init",
            saved_args=saved_args,
        )

    def __setup_files(self) -> None:

        # Note: parse instead of copy to avoid format changes
        filedata = pkgutil.get_data(__name__, "template/settings.json")
        if filedata:
            settings = json.loads(filedata.decode("utf-8"))
            with open("settings.json", "w", encoding="utf8") as file:
                json.dump(settings, file, indent=4)

        Path("search").mkdir()
        Path("pdfs").mkdir()

        files_to_retrieve = [
            [Path("template/readme.md"), Path("readme.md")],
            [Path("template/.pre-commit-config.yaml"), Path(".pre-commit-config.yaml")],
            [Path("template/.markdownlint.yaml"), Path(".markdownlint.yaml")],
            [Path("template/.gitattributes"), Path(".gitattributes")],
            [Path("template/LICENSE-CC-BY-4.0.txt"), Path("LICENSE.txt")],
            [
                Path("template/docker-compose.yml"),
                Path.home() / Path("colrev/docker-compose.yml"),
            ],
        ]
        for rp, p in files_to_retrieve:
            self.__retrieve_package_file(template_file=rp, target=p)

        with open("settings.json", encoding="utf-8") as f:
            settings = json.load(f)

        settings["project"]["review_type"] = self.review_type
        # Principle: adapt values provided by the default settings.json
        # instead of creating a new settings.json

        if self.review_type not in ["curated_masterdata"]:
            settings["data"]["scripts"] = [
                {
                    "endpoint": "MANUSCRIPT",
                    "paper_endpoint_version": "1.0",
                    "word_template": "APA-7.docx",
                    "csl_style": "apa.csl",
                }
            ]

        if "literature_review" == self.review_type:
            pass

        elif "narrative_review" == self.review_type:
            pass

        elif "descriptive_review" == self.review_type:
            settings["data"]["scripts"].append(
                {"endpoint": "PRISMA", "prisma_data_endpoint_version": "1.0"}
            )

        elif "scoping_review" == self.review_type:
            settings["data"]["scripts"].append(
                {"endpoint": "PRISMA", "prisma_data_endpoint_version": "1.0"}
            )

        elif "critical_review" == self.review_type:
            settings["data"]["scripts"].append(
                {"endpoint": "PRISMA", "prisma_data_endpoint_version": "1.0"}
            )

        elif "theoretical_review" == self.review_type:
            pass

        elif "conceptual_review" == self.review_type:
            pass

        elif "qualitative_systematic_review" == self.review_type:
            settings["data"]["scripts"].append(
                {
                    "endpoint": "STRUCTURED",
                    "structured_data_endpoint_version": "1.0",
                    "fields": [],
                }
            )
            settings["data"]["scripts"].append(
                {"endpoint": "PrismaDiagram", "prisma_data_endpoint_version": "1.0"}
            )

        elif "meta_analysis" == self.review_type:
            settings["data"]["scripts"].append(
                {
                    "endpoint": "STRUCTURED",
                    "structured_data_endpoint_version": "1.0",
                    "fields": [],
                }
            )
            settings["data"]["scripts"].append(
                {"endpoint": "PRISMA", "prisma_data_endpoint_version": "1.0"}
            )

        elif "scientometric" == self.review_type:
            settings["pdf_get"]["pdf_required_for_screen_and_synthesis"] = False

        elif "peer_review" == self.review_type:
            settings["pdf_get"]["pdf_required_for_screen_and_synthesis"] = False

            settings["data"]["scripts"].append(
                {
                    "endpoint": "PEER_REVIEW",
                }
            )
            settings["sources"].append(
                {
                    "filename": "search/references.bib",
                    "search_type": "DB",
                    "source_name": "BACKWARD_SEARCH",
                    "source_identifier": "{{cited_by_file}} (references)",
                    "search_parameters": "SCOPE file='paper.pdf'",
                    "search_script": {"endpoint": "backward_search"},
                    "conversion_script": {"endpoint": "bibtex"},
                    "source_prep_scripts": [],
                    "comment": "",
                }
            )

            settings["prep"]["prep_rounds"] = [
                d
                for d in settings["prep"]["prep_rounds"]
                if d.get("name", "") != "exclusion"
            ]

            self.instructions.append(
                "Store the file as paper.pdf in the pdfs directory"
            )
            self.instructions.append(
                "Afterwards, run colrev search && colrev load && colrev search"
            )

            # TODO : add backward search (only for peer-reviewed pdf)
            # endpoint: extract diff between imported metadata and prepared metadata
            # ordered in terms of change significance

        elif "realtime" == self.review_type:
            settings["project"]["delay_automated_processing"] = False
            settings["prep"]["prep_rounds"] = [
                {
                    "name": "high_confidence",
                    "similarity": 0.95,
                    "scripts": [
                        "load_fixes",
                        "remove_urls_with_500_errors",
                        "remove_broken_IDs",
                        "global_ids_consistency_check",
                        "prep_curated",
                        "format",
                        "resolve_crossrefs",
                        "get_doi_from_urls",
                        "get_masterdata_from_doi",
                        "get_masterdata_from_crossref",
                        "get_masterdata_from_dblp",
                        "get_masterdata_from_open_library",
                        "get_year_from_vol_iss_jour_crossref",
                        "get_record_from_local_index",
                        "remove_nicknames",
                        "format_minor",
                        "drop_fields",
                    ],
                }
            ]

        elif "curated_masterdata" == self.review_type:
            # replace readme
            self.__retrieve_package_file(
                template_file=Path("template/review_type/curated_masterdata/readme.md"),
                target=Path("readme.md"),
            )
            if self.url:
                self.__inplace_change(
                    filename=Path("readme.md"),
                    old_string="{{url}}",
                    new_string=self.url,
                )
            CROSSREF_SOURCE = {
                "filename": "search/CROSSREF.bib",
                "search_type": "DB",
                "source_name": "CROSSREF",
                "source_identifier": "https://api.crossref.org/works/{{doi}}",
                "search_parameters": "",
                "search_script": {"endpoint": "search_crossref"},
                "conversion_script": {"endpoint": "bibtex"},
                "source_prep_scripts": [],
                "comment": "",
            }
            settings["sources"].insert(0, CROSSREF_SOURCE)
            settings["search"]["retrieve_forthcoming"] = False

            # TODO : exclude complementary materials in prep scripts
            # TODO : exclude get_masterdata_from_citeas etc. from prep
            settings["prep"]["man_prep_scripts"] = [
                {"endpoint": "prep_man_curation_jupyter"},
                {"endpoint": "export_man_prep"},
            ]
            settings["prescreen"][
                "explanation"
            ] = "All records are automatically prescreen included."

            settings["screen"][
                "explanation"
            ] = "All records are automatically included in the screen."

            settings["project"]["curated_masterdata"] = True
            settings["prescreen"]["scripts"] = [
                {"endpoint": "scope_prescreen", "ExcludeComplementaryMaterials": True},
                {"endpoint": "conditional_prescreen"},
            ]
            settings["screen"]["scripts"] = [{"endpoint": "conditional_screen"}]
            settings["pdf_get"]["scripts"] = []
            # TODO : Deactivate languages, ...
            #  exclusion and add a complementary exclusion built-in script

            settings["dedupe"]["scripts"] = [
                {
                    "endpoint": "curation_full_outlet_dedupe",
                    "selected_source": "search/CROSSREF.bib",
                },
                {
                    "endpoint": "curation_full_outlet_dedupe",
                    "selected_source": "search/pdfs.bib",
                },
                {"endpoint": "curation_missing_dedupe"},
            ]

            # curated repo: automatically prescreen/screen-include papers
            # (no data endpoint -> automatically rev_synthesized)

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)

        if "review" in self.project_name.lower():
            self.__inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=self.project_name.rstrip(" "),
            )
        else:
            r_type_suffix = self.review_type.replace("_", " ").replace(
                "meta analysis", "meta-analysis"
            )
            self.__inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=self.project_name.rstrip(" ") + f": A {r_type_suffix}",
            )

        global_git_vars = EnvironmentManager.get_name_mail_from_global_git_config()
        if 2 != len(global_git_vars):
            logging.error("Global git variables (user name and email) not available.")
            return

        # Note: need to write the .gitignore because file would otherwise be
        # ignored in the template directory.
        with open(".gitignore", "w", encoding="utf8") as f:
            f.write(
                "*.bib.sav\n"
                + "missing_pdf_files.csv\n"
                + "manual_cleansing_statistics.csv\n"
                + "data.csv\n"
                + "venv\n"
                + ".records_learned_settings\n"
                + ".corrections\n"
                + ".ipynb_checkpoints/\n"
                + "pdfs\n"
                + "requests_cache.sqlite\n"
                + "__pycache__\n"
                + ".tei"
            )

    def __post_commit_edits(self) -> None:

        if "curated_masterdata" == self.review_type:
            self.REVIEW_MANAGER.settings.project.curation_url = "TODO"
            self.REVIEW_MANAGER.settings.project.curated_fields = ["url", "doi", "TODO"]

            PDF_SOURCE = [
                s
                for s in self.REVIEW_MANAGER.settings.sources
                if "search/pdfs.bib" == str(s.filename)
            ][0]
            PDF_SOURCE.search_parameters = (
                "SCOPE path='pdfs' WITH journal='TODO' "
                + "AND sub_dir_pattern='TODO:volume_number|year'"
            )

            CROSSREF_SOURCE = [
                s
                for s in self.REVIEW_MANAGER.settings.sources
                if "search/CROSSREF.bib" == str(s.filename)
            ][0]
            CROSSREF_SOURCE.search_parameters = "SCOPE journal_issn='TODO'"

            self.REVIEW_MANAGER.save_settings()

            self.REVIEW_MANAGER.logger.info("Completed setup.")
            self.REVIEW_MANAGER.logger.info(
                f"{colors.ORANGE}Open the settings.json and "
                f"edit all fields marked with 'TODO'.{colors.END}"
            )

    def __setup_git(self) -> None:

        git_repo = git.Repo.init()

        # To check if git actors are set
        EnvironmentManager.get_name_mail_from_global_git_config()

        logging.info("Install latest pre-commmit hooks")
        scripts_to_call = [
            ["pre-commit", "install"],
            ["pre-commit", "install", "--hook-type", "prepare-commit-msg"],
            ["pre-commit", "install", "--hook-type", "pre-push"],
            ["pre-commit", "autoupdate"],
            ["daff", "git", "csv"],
        ]
        for script_to_call in scripts_to_call:
            try:
                self.logger.info(f'{" ".join(script_to_call)}...')
                check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)
            except CalledProcessError:
                if "" == " ".join(script_to_call):
                    self.logger.info(
                        f"{' '.join(script_to_call)} did not succeed "
                        "(Internet connection could not be available)"
                    )
                else:
                    self.logger.info(f"Failed: {' '.join(script_to_call)}")

        git_repo.index.add(
            [
                "readme.md",
                ".pre-commit-config.yaml",
                ".gitattributes",
                ".gitignore",
                "settings.json",
                ".markdownlint.yaml",
                "LICENSE.txt",
            ]
        )

    def __require_empty_directory(self):

        cur_content = [str(x) for x in Path.cwd().glob("**/*")]

        if "venv" in cur_content:
            cur_content.remove("venv")
            # Note: we can use paths directly when initiating the project
        if "report.log" in cur_content:
            cur_content.remove("report.log")

        if 0 != len(cur_content):
            raise colrev_exceptions.NonEmptyDirectoryError()

    def __inplace_change(
        self, *, filename: Path, old_string: str, new_string: str
    ) -> None:
        with open(filename, encoding="utf8") as f:
            s = f.read()
            if old_string not in s:
                logging.info(f'"{old_string}" not found in {filename}.')
                return
        with open(filename, "w", encoding="utf8") as f:
            s = s.replace(old_string, new_string)
            f.write(s)

    def __retrieve_package_file(self, *, template_file: Path, target: Path) -> None:

        filedata = pkgutil.get_data(__name__, str(template_file))
        if filedata:
            with open(target, "w", encoding="utf8") as file:
                file.write(filedata.decode("utf-8"))

    def __create_example_repo(self) -> None:
        """The example repository is intended to provide an initial illustration
        of CoLRev. It focuses on a quick overview of the process and does
        not cover advanced features or special cases."""

        self.logger.info("Include 30_example_records.bib")
        self.__retrieve_package_file(
            template_file=Path("template/example/30_example_records.bib"),
            target=Path("search/30_example_records.bib"),
        )

        git_repo = git.Repo.init()
        git_repo.index.add(["search/30_example_records.bib"])

    def __create_local_index(self) -> None:
        from colrev_core.environment import LocalIndex
        import os

        self.REVIEW_MANAGER.report_logger.handlers = []

        local_index_path = LocalIndex.local_environment_path / Path("local_index")
        curdir = Path.cwd()
        if not local_index_path.is_dir():
            local_index_path.mkdir(parents=True, exist_ok=True)
            os.chdir(local_index_path)
            Initializer(
                project_name="local_index",
                SHARE_STAT_REQ="PROCESSED",
                review_type="curated_masterdata",
                local_index_repo=True,
            )
            self.logger.info("Created local_index repository")

        os.chdir(curdir)


if __name__ == "__main__":
    pass
