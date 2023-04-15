#! /usr/bin/env python
"""CoLRev init operation: Create a project and specify settings."""
from __future__ import annotations

import json
import logging
import os
from importlib.metadata import version
from pathlib import Path
from subprocess import CalledProcessError
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT
from typing import Optional

import git

import colrev.dataset
import colrev.env.environment_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.review_manager  # pylint: disable=cyclic-import
import colrev.settings
import colrev.ui_cli.cli_colors as colors


# pylint: disable=too-few-public-methods


class Initializer:
    """Initialize a CoLRev project"""

    share_stat_req_options = ["none", "processed", "screened", "completed"]

    def __init__(
        self,
        *,
        review_type: str,
        example: bool = False,
        light: bool = False,
        local_pdf_collection: bool = False,
        target_path: Optional[Path] = None,
        exact_call: str = "",
    ) -> None:
        saved_args = locals()
        if example and local_pdf_collection:
            raise colrev_exceptions.RepoInitError(
                msg="Cannot initialize local_pdf_collection repository with example data."
            )
        self.light = light

        self.review_type = review_type.replace("-", "_").lower().replace(" ", "_")
        if "." not in self.review_type:
            self.review_type = "colrev." + self.review_type

        if target_path:
            os.chdir(target_path)
            self.target_path = target_path
        else:
            self.target_path = Path.cwd()

        review_manager = colrev.review_manager.ReviewManager(
            path_str=str(target_path), force_mode=True, navigate_to_home_dir=False
        )

        try:
            res = review_manager.get_review_types(review_type=self.review_type)
        except colrev.exceptions.MissingDependencyError as exc:
            res = review_manager.get_review_types(
                review_type="colrev.literature_review"
            )
            raise colrev_exceptions.ParameterError(
                parameter="init.review_type",
                value=f"'{review_type}'",
                options=list(res.all_available_packages_names.keys()),
            ) from exc

        self.__check_init_precondition()

        self.title = str(self.target_path.name)
        self.logger = self.__setup_init_logger(level=logging.INFO)

        self.__setup_git()
        self.__setup_files(path=self.target_path)

        if example:
            self.__create_example_repo()

        self.review_manager = colrev.review_manager.ReviewManager(exact_call=exact_call)

        self.__create_commit(saved_args=saved_args)
        if not example:
            if "pytest" not in os.getcwd():
                self.__register_repo()
        if local_pdf_collection:
            self.__create_local_pdf_collection()

        self.__post_commit_edits()

        self.review_manager.logger.info(
            "%sCompleted init operation%s", colors.GREEN, colors.END
        )

    def __check_init_precondition(self) -> None:
        cur_content = [
            str(x.relative_to(self.target_path)) for x in self.target_path.glob("**/*")
        ]
        cur_content = [x for x in cur_content if not x.startswith("venv")]

        if str(colrev.review_manager.ReviewManager.REPORT_RELATIVE) in cur_content:
            cur_content.remove(str(colrev.review_manager.ReviewManager.REPORT_RELATIVE))
        if cur_content:
            raise colrev_exceptions.NonEmptyDirectoryError(
                filepath=self.target_path, content=cur_content
            )

        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        environment_manager.get_name_mail_from_git()

        try:
            environment_manager.check_docker_installed()
        except colrev_exceptions.MissingDependencyError as exc:  # pragma: no cover
            if not self.light:
                raise colrev_exceptions.CoLRevException(
                    "Docker not installed. Docker is optional but recommended.\n"
                    "For more information, see "
                    "https://colrev.readthedocs.io/en/latest/manual/manual.html"
                    "To init a repository without Docker, run "
                    f"{colors.ORANGE}colrev init --light{colors.END}"
                ) from exc

    def __setup_init_logger(self, *, level: int = logging.INFO) -> logging.Logger:
        # pylint: disable=duplicate-code
        init_logger = logging.getLogger("colrev-init_logger")

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
        self.review_manager.logger.info("Register CoLRev repository")

        environment_manager = self.review_manager.get_environment_manager()
        environment_manager.register_repo(path_to_register=self.target_path)

    def __create_commit(self, *, saved_args: dict) -> None:
        del saved_args["local_pdf_collection"]
        self.review_manager.create_commit(
            msg="Initial commit",
            manual_author=True,
        )

    def __setup_files(self, *, path: Path) -> None:
        # pylint: disable=too-many-locals

        # Note: parse instead of copy to avoid format changes
        settings_filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/init/settings.json")
        )
        if settings_filedata:
            settings = json.loads(settings_filedata.decode("utf-8"))
            settings["project"]["review_type"] = str(self.review_type)
            with open(path / Path("settings.json"), "w", encoding="utf8") as file:
                json.dump(settings, file, indent=4)

        colrev.review_manager.ReviewManager.SEARCHDIR_RELATIVE.mkdir(parents=True)
        colrev.review_manager.ReviewManager.PDF_DIR_RELATIVE.mkdir(parents=True)

        colrev_path = Path.home() / Path("colrev")
        colrev_path.mkdir(exist_ok=True, parents=True)

        files_to_retrieve = [
            [Path("template/init/readme.md"), Path("readme.md")],
            [
                Path("template/init/pre-commit-config.yaml"),
                Path(".pre-commit-config.yaml"),
            ],
            [Path("template/init/markdownlint.yaml"), Path(".markdownlint.yaml")],
            [
                Path("template/init/pre-commit.yml"),
                Path(".github/workflows/pre-commit.yml"),
            ],
            [Path("template/init/gitattributes"), Path(".gitattributes")],
            [Path("template/init/LICENSE-CC-BY-4.0.txt"), Path("LICENSE.txt")],
            [
                Path("template/init/colrev_update.yml"),
                Path(".github/workflows/colrev_update.yml"),
            ],
        ]
        for retrieval_path, target_path in files_to_retrieve:
            colrev.env.utils.retrieve_package_file(
                template_file=retrieval_path, target=target_path
            )

        self.review_manager = colrev.review_manager.ReviewManager()

        settings = self.review_manager.settings

        committer, email = self.review_manager.get_committer()
        settings.project.authors = [
            colrev.settings.Author(
                name=committer,
                initials="".join(part[0] for part in committer.split(" ")),
                email=email,
            )
        ]

        colrev_version = version("colrev")
        if "+" in colrev_version:
            colrev_version = colrev_version[: colrev_version.rfind("+")]
        settings.project.colrev_version = colrev_version

        settings.project.title = self.title
        self.review_type = settings.project.review_type

        # Principle: adapt values provided by the default settings.json
        # instead of creating a new settings.json

        review_types = self.review_manager.get_review_types(
            review_type=self.review_type
        )
        settings = review_types.packages[self.review_type].initialize(settings=settings)

        self.review_manager.save_settings()

        project_title = self.review_manager.settings.project.title
        if "review" in project_title.lower():
            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=project_title.rstrip(" ").capitalize(),
            )
        else:
            package_manager = self.review_manager.get_package_manager()
            check_operation = colrev.operation.CheckOperation(
                review_manager=self.review_manager
            )
            review_type_endpoint = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.review_type,
                selected_packages=[{"endpoint": self.review_type}],
                operation=check_operation,
                ignore_not_available=False,
            )
            r_type_suffix = str(review_type_endpoint[self.review_type])

            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=project_title.rstrip(" ").capitalize()
                + f": A {r_type_suffix} protocol",
            )

        if self.light:
            settings.data.data_package_endpoints = [
                x
                for x in settings.data.data_package_endpoints
                if x["endpoint"] not in ["colrev.paper_md"]
            ]
            settings.sources = [
                x for x in settings.sources if x.endpoint not in ["colrev.pdfs_dir"]
            ]

            settings.pdf_prep.pdf_prep_package_endpoints = [
                x
                for x in settings.pdf_prep.pdf_prep_package_endpoints
                if x["endpoint"]
                not in [
                    "colrev.pdf_check_ocr",
                    "colrev.remove_coverpage",
                    "colrev.remove_last_page",
                    "colrev.create_tei",
                ]
            ]

        self.review_manager.save_settings()

        # Note : to avoid file setup at colrev status (calls data_operation.main)
        data_operation = self.review_manager.get_data_operation(
            notify_state_transition_operation=False
        )
        data_operation.main(silent_mode=True)

        self.review_manager.logger.info("Set up %s", self.review_type)

        for source in settings.sources:
            self.review_manager.logger.info(
                " add search %s", source.endpoint.replace("colrev.", "")
            )

        for data_package_endpoint in settings.data.data_package_endpoints:
            self.review_manager.logger.info(
                " add data   %s",
                data_package_endpoint["endpoint"].replace("colrev.", ""),
            )

        with open("data/records.bib", mode="w", encoding="utf-8") as file:
            file.write("\n")

        git_repo = self.review_manager.dataset.get_repo()
        git_repo.git.add(all=True)

    def __post_commit_edits(self) -> None:
        if self.review_type == "colrev.curated_masterdata":
            self.review_manager.logger.info("Post-commit edits")
            self.review_manager.settings.project.curation_url = "TODO"
            self.review_manager.settings.project.curated_fields = ["url", "doi", "TODO"]

            pdf_source_l = [
                s
                for s in self.review_manager.settings.sources
                if "data/search/pdfs.bib" == str(s.filename)
            ]
            if pdf_source_l:
                pdf_source = pdf_source_l[0]
                pdf_source.search_parameters = {
                    "scope": {
                        "path": "pdfs",
                        "journal": "TODO",
                        "subdir_pattern": "TODO:volume_number|year",
                    }
                }

            crossref_source_l = [
                s
                for s in self.review_manager.settings.sources
                if "data/search/CROSSREF.bib" == str(s.filename)
            ]
            if crossref_source_l:
                crossref_source = crossref_source_l[0]
                crossref_source.search_parameters = {"scope": {"journal_issn": "TODO"}}

            self.review_manager.save_settings()

            self.review_manager.logger.info("Completed setup.")

    def __setup_git(self) -> None:
        self.logger.info("Create CoLRev repository")

        self.logger.info("Set up git repository")

        git.Repo.init()

        # To check if git actors are set
        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        environment_manager.get_name_mail_from_git()

        logging.info("Install latest pre-commmit hooks")
        scripts_to_call = [
            {
                "description": "Install pre-commit hooks",
                "command": ["pre-commit", "install"],
            },
            {
                "description": "",
                "command": [
                    "pre-commit",
                    "install",
                    "--hook-type",
                    "prepare-commit-msg",
                ],
            },
            {
                "description": "",
                "command": ["pre-commit", "install", "--hook-type", "pre-push"],
            },
            {"description": "", "command": ["pre-commit", "autoupdate"]},
            {"description": "", "command": ["daff", "git", "csv"]},
        ]
        for script_to_call in scripts_to_call:
            try:
                if script_to_call["description"]:
                    self.logger.debug("%s...", script_to_call["description"])
                check_call(script_to_call["command"], stdout=DEVNULL, stderr=STDOUT)
            except CalledProcessError:
                if " ".join(script_to_call["command"]) == "pre-commit autoupdate":
                    pass
                else:
                    self.logger.error(
                        "%sFailed: %s%s",
                        colors.RED,
                        " ".join(script_to_call),
                        colors.END,
                    )

    def __create_example_repo(self) -> None:
        """The example repository is intended to provide an initial illustration
        of CoLRev. It focuses on a quick overview of the process and does
        not cover advanced features or special cases."""

        self.logger.info("Include 30_example_records.bib")
        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/example/30_example_records.bib"),
            target=Path("data/search/30_example_records.bib"),
        )

        git_repo = git.Repo.init()
        git_repo.index.add(["data/search/30_example_records.bib"])

        with open("settings.json", encoding="utf-8") as file:
            settings = json.load(file)

        settings["dedupe"]["dedupe_package_endpoints"] = [
            {"endpoint": "colrev.simple_dedupe"}
        ]

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)
        git_repo.index.add(["settings.json"])

    def __create_local_pdf_collection(self) -> None:
        self.review_manager.report_logger.handlers = []

        local_index = self.review_manager.get_local_index()
        local_pdf_collection_path = local_index.local_environment_path / Path(
            "local_pdf_collection"
        )

        if not local_pdf_collection_path.is_dir():
            local_pdf_collection_path.mkdir(parents=True, exist_ok=True)
            os.chdir(local_pdf_collection_path)
            Initializer(
                review_type="colrev.literature_review",
                local_pdf_collection=True,
            )
            self.logger.info("Created local_pdf_collection repository")

        os.chdir(self.target_path)


if __name__ == "__main__":
    pass
