#! /usr/bin/env python
"""CoLRev init operation: Create a project and specify settings."""
from __future__ import annotations

import json
import logging
import os
import typing
from importlib.metadata import version
from pathlib import Path
from subprocess import CalledProcessError
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT

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
        local_index_repo: bool = False,
    ) -> None:

        if review_type is None:
            review_type = "literature_review"

        saved_args = locals()
        assert not (example and local_index_repo)

        self.review_type = review_type.replace("-", "_").lower().replace(" ", "_")
        if "." not in self.review_type:
            self.review_type = "colrev_built_in." + self.review_type
        review_manager = colrev.review_manager.ReviewManager(force_mode=True)
        try:
            res = review_manager.get_review_types(review_type=self.review_type)
        except colrev.exceptions.MissingDependencyError as exc:
            res = review_manager.get_review_types(
                review_type="colrev_built_in.literature_review"
            )
            raise colrev_exceptions.ParameterError(
                parameter="init.review_type",
                value=f"'{review_type}'",
                options=list(res.all_available_packages_names.keys()),
            ) from exc

        self.__check_init_precondition()

        self.title = str(Path.cwd().name)
        self.instructions: typing.List[str] = []
        self.logger = self.__setup_init_logger(level=logging.INFO)

        self.__require_empty_directory()
        self.logger.info("Setup git")
        self.__setup_git()
        self.logger.info("Setup files")
        self.__setup_files(path=Path.cwd())

        if example:
            self.__create_example_repo()

        self.review_manager = colrev.review_manager.ReviewManager()

        self.logger.info("Create commit")
        self.__create_commit(saved_args=saved_args)
        if not example:
            self.review_manager.logger.info("Register repo")
            self.__register_repo()
        if local_index_repo:
            self.__create_local_index()

        self.review_manager.logger.info("Post-commit edits")
        self.__post_commit_edits()

        print("\n")
        for instruction in self.instructions:
            self.review_manager.logger.info(instruction)

    def __check_init_precondition(self) -> None:
        cur_content = [str(x.relative_to(Path.cwd())) for x in Path.cwd().glob("**/*")]
        cur_content = [x for x in cur_content if not x.startswith("venv")]

        # pylint: disable=duplicate-code
        if str(colrev.review_manager.ReviewManager.REPORT_RELATIVE) in cur_content:
            cur_content.remove(str(colrev.review_manager.ReviewManager.REPORT_RELATIVE))
        if cur_content:
            raise colrev_exceptions.NonEmptyDirectoryError()

        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        global_git_vars = environment_manager.get_name_mail_from_git()
        if 2 != len(global_git_vars):
            raise colrev_exceptions.CoLRevException(
                "Global git variables (user name and email) not available."
            )

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

        environment_manager = self.review_manager.get_environment_manager()
        environment_manager.register_repo(path_to_register=Path.cwd())

    def __create_commit(self, *, saved_args: dict) -> None:

        del saved_args["local_index_repo"]
        self.review_manager.create_commit(
            msg="Initial commit",
            manual_author=True,
            script_call="colrev init",
            saved_args=saved_args,
        )

    def __setup_files(self, *, path: Path) -> None:
        # pylint: disable=too-many-locals

        # Note: parse instead of copy to avoid format changes
        settings_filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/settings.json")
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
            [Path("template/readme.md"), Path("readme.md")],
            [
                Path("template/.pre-commit-config.yaml"),
                Path(".pre-commit-config.yaml"),
            ],
            [Path("template/.markdownlint.yaml"), Path(".markdownlint.yaml")],
            [Path("template/.gitattributes"), Path(".gitattributes")],
            [Path("template/gitignore"), Path(".gitignore")],
            [Path("template/LICENSE-CC-BY-4.0.txt"), Path("LICENSE.txt")],
        ]
        for retrieval_path, target_path in files_to_retrieve:
            colrev.env.utils.retrieve_package_file(
                template_file=retrieval_path, target=target_path
            )

        self.review_manager = colrev.review_manager.ReviewManager()

        settings = self.review_manager.settings

        settings.project.authors = [
            colrev.settings.Author(
                name=self.review_manager.committer,
                initials="".join(
                    part[0] for part in self.review_manager.committer.split(" ")
                ),
                email=self.review_manager.email,
            )
        ]

        colrev_version = version("colrev")
        colrev_version = colrev_version[: colrev_version.find("+")]
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

        # Note : to avoid file setup at colrev status (calls data_operation.main)
        data_operation = self.review_manager.get_data_operation(
            notify_state_transition_operation=False
        )
        data_operation.main()

        files_to_add = [
            "readme.md",
            ".pre-commit-config.yaml",
            ".gitattributes",
            ".gitignore",
            "settings.json",
            ".markdownlint.yaml",
            "LICENSE.txt",
        ]
        for file_to_add in files_to_add:
            self.review_manager.dataset.add_changes(path=Path(file_to_add))

    def __post_commit_edits(self) -> None:

        if "curated_masterdata" == self.review_type:
            self.review_manager.settings.project.curation_url = "TODO"
            self.review_manager.settings.project.curated_fields = ["url", "doi", "TODO"]

            pdf_source = [
                s
                for s in self.review_manager.settings.sources
                if "data/search/pdfs.bib" == str(s.filename)
            ][0]
            pdf_source.search_parameters = {
                "scope": {
                    "path": "pdfs",
                    "journal": "TODO",
                    "sub_dir_pattern": "TODO:volume_number|year",
                }
            }

            crossref_source = [
                s
                for s in self.review_manager.settings.sources
                if "data/search/CROSSREF.bib" == str(s.filename)
            ][0]
            crossref_source.search_parameters = {"scope": {"journal_issn": "TODO"}}

            self.review_manager.save_settings()

            self.review_manager.logger.info("Completed setup.")

    def __setup_git(self) -> None:

        git.Repo.init()

        # To check if git actors are set
        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        environment_manager.get_name_mail_from_git()

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
                self.logger.info("%s...", " ".join(script_to_call))
                check_call(script_to_call, stdout=DEVNULL, stderr=STDOUT)
            except CalledProcessError:
                if "" == " ".join(script_to_call):
                    self.logger.info(
                        "%s did not succeed "
                        "(Internet connection could not be available)",
                        " ".join(script_to_call),
                    )
                else:
                    self.logger.error(
                        "%sFailed: %s%s",
                        colors.RED,
                        " ".join(script_to_call),
                        colors.END,
                    )

    def __require_empty_directory(self) -> None:

        cur_content = [str(x.relative_to(Path.cwd())) for x in Path.cwd().glob("**/*")]
        cur_content = [x for x in cur_content if not x.startswith("venv")]

        if str(colrev.review_manager.ReviewManager.REPORT_RELATIVE) in cur_content:
            cur_content.remove(str(colrev.review_manager.ReviewManager.REPORT_RELATIVE))
        if str(colrev.review_manager.ReviewManager.SETTINGS_RELATIVE) in cur_content:
            cur_content.remove(
                str(colrev.review_manager.ReviewManager.SETTINGS_RELATIVE)
            )

        if cur_content:
            raise colrev_exceptions.NonEmptyDirectoryError()

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
            {"endpoint": "colrev_built_in.simple_dedupe"}
        ]

        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)
        git_repo.index.add(["settings.json"])

    def __create_local_index(self) -> None:

        self.review_manager.report_logger.handlers = []

        local_index = self.review_manager.get_local_index()
        local_index_path = local_index.local_environment_path / Path("local_index")

        curdir = Path.cwd()
        if not local_index_path.is_dir():
            local_index_path.mkdir(parents=True, exist_ok=True)
            os.chdir(local_index_path)
            Initializer(
                review_type="curated_masterdata",
                local_index_repo=True,
            )
            self.logger.info("Created local_index repository")

        os.chdir(curdir)


if __name__ == "__main__":
    pass
