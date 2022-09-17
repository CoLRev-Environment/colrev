#! /usr/bin/env python
"""CoLRev init operation: Create a project and specify settings."""
from __future__ import annotations

import json
import logging
import os
import typing
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

# from importlib.metadata import version

# pylint: disable=too-few-public-methods


class Initializer:

    share_stat_req_options = ["NONE", "PROCESSED", "SCREENED", "COMPLETED"]

    def __init__(
        self,
        *,
        review_type: str,
        example: bool = False,
        local_index_repo: bool = False,
    ) -> None:

        saved_args = locals()

        assert not (example and local_index_repo)

        # TODO : adapt to  new colrev.review_types
        # if review_type not in colrev.settings.ReviewType.get_options():
        #     raise colrev_exceptions.ParameterError(
        #         parameter="init.review_type",
        #         value=f"'{review_type}'",
        #         options=colrev.settings.ReviewType.get_options(),
        #     )

        self.__check_init_precondition()

        # TODO : this will change to project.title
        self.project_name = str(Path.cwd().name)
        self.review_type = review_type.replace("-", "_").lower().replace(" ", "_")
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
        cur_content = [str(x) for x in Path.cwd().glob("**/*")]

        # pylint: disable=duplicate-code
        if "venv" in cur_content:
            cur_content.remove("venv")
            # Note: we can use paths directly when initiating the project
        if "report.log" in cur_content:
            cur_content.remove("report.log")

        if 0 != len(cur_content):
            raise colrev_exceptions.NonEmptyDirectoryError()

    def __setup_init_logger(self, *, level=logging.INFO) -> logging.Logger:
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

        # Note: parse instead of copy to avoid format changes
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/settings.json")
        )
        if filedata:
            settings = json.loads(filedata.decode("utf-8"))
            settings["project"]["review_type"] = str(self.review_type)
            with open(path / Path("settings.json"), "w", encoding="utf8") as file:
                json.dump(settings, file, indent=4)

        Path("search").mkdir()
        Path("pdfs").mkdir()
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
            [
                Path("template/docker-compose.yml"),
                colrev_path / Path("docker-compose.yml"),
            ],
        ]
        for retrieval_path, target_path in files_to_retrieve:
            colrev.env.utils.retrieve_package_file(
                template_file=retrieval_path, target=target_path
            )

        self.review_manager = colrev.review_manager.ReviewManager()

        review_types = self.review_manager.get_review_types(
            review_type=self.review_type
        )

        settings = self.review_manager.settings

        print("TODO : reactivate (settings_editor branch)")
        # settings.project.authors = [
        #     colrev.settings.Author(
        #         name=self.review_manager.committer,
        #         initials="".join(
        #             part[0] for part in self.review_manager.committer.split(" ")
        #         ),
        #         email=self.review_manager.email,
        #     )
        # ]

        settings.project.title = self.project_name

        # colrev_version = version("colrev_core")
        # colrev_version = colrev_version[: colrev_version.find("+")]
        # settings.project.colrev_version = colrev_version

        self.review_type = settings.project.review_type

        # Principle: adapt values provided by the default settings.json
        # instead of creating a new settings.json

        settings = review_types.packages[self.review_type].initialize(settings=settings)

        self.review_manager.save_settings()

        if "review" in self.project_name.lower():
            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=self.project_name.rstrip(" "),
            )
        else:
            r_type_suffix = self.review_type.replace("_", " ").replace(
                "meta analysis", "meta-analysis"
            )
            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=self.project_name.rstrip(" ") + f": A {r_type_suffix}",
            )

        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        global_git_vars = environment_manager.get_name_mail_from_git()
        if 2 != len(global_git_vars):
            logging.error("Global git variables (user name and email) not available.")
            return

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
                if "search/pdfs.bib" == str(s.filename)
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
                if "search/CROSSREF.bib" == str(s.filename)
            ][0]
            crossref_source.search_parameters = {"scope": {"journal_issn": "TODO"}}

            self.review_manager.save_settings()

            self.review_manager.logger.info("Completed setup.")
            self.review_manager.logger.info(
                "%sOpen the settings.json and edit all fields marked with 'TODO'%s.",
                colors.ORANGE,
                colors.END,
            )

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
                    self.logger.info("Failed: %s", " ".join(script_to_call))

    def __require_empty_directory(self) -> None:

        cur_content = [str(x) for x in Path.cwd().glob("**/*")]

        if "venv" in cur_content:
            cur_content.remove("venv")
            # Note: we can use paths directly when initiating the project
        if "report.log" in cur_content:
            cur_content.remove("report.log")

        if 0 != len(cur_content):
            raise colrev_exceptions.NonEmptyDirectoryError()

    def __create_example_repo(self) -> None:
        """The example repository is intended to provide an initial illustration
        of CoLRev. It focuses on a quick overview of the process and does
        not cover advanced features or special cases."""

        self.logger.info("Include 30_example_records.bib")
        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/example/30_example_records.bib"),
            target=Path("search/30_example_records.bib"),
        )

        git_repo = git.Repo.init()
        git_repo.index.add(["search/30_example_records.bib"])

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
