#! /usr/bin/env python
"""CoLRev init operation: Create a project and specify settings."""
from __future__ import annotations

import json
import logging
import os
import platform
import shutil
from importlib.metadata import version
from pathlib import Path
from subprocess import CalledProcessError  # nosec
from subprocess import check_call  # nosec
from subprocess import DEVNULL  # nosec
from subprocess import STDOUT  # nosec

import git
from git.exc import InvalidGitRepositoryError

import colrev.env.docker_manager
import colrev.env.environment_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.ops.check
import colrev.review_manager
import colrev.settings
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class Initializer:
    """Initialize a CoLRev project"""

    review_manager: colrev.review_manager.ReviewManager

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        review_type: str,
        target_path: Path,
        example: bool = False,
        force_mode: bool = False,
        light: bool = False,
        exact_call: str = "",
    ) -> None:
        self.force_mode = force_mode
        self.target_path = target_path
        os.chdir(target_path)
        self.review_manager = colrev.review_manager.ReviewManager(
            path_str=str(self.target_path), force_mode=True, navigate_to_home_dir=False
        )
        self.review_type = self._format_review_type(review_type)
        self.title = str(self.target_path.name)
        self._setup_repo(
            example=example,
            exact_call=exact_call,
            no_docker=light,
        )

    def _setup_repo(
        self,
        *,
        example: bool,
        exact_call: str,
        no_docker: bool,
    ) -> None:
        self.no_docker = no_docker
        if platform.system() != "Linux":
            self.no_docker = True

        self._reset_if_existing_repo_with_single_commit()
        self._check_init_precondition()
        self.review_manager.logger.info("Create CoLRev repository")
        self._setup_git()
        self._setup_files()
        self._setup_settings()
        self._finalize()
        if example:
            self._create_example_repo()

        self.review_manager = colrev.review_manager.ReviewManager(exact_call=exact_call)

        self.review_manager.dataset.create_commit(
            msg="Initial commit",
            manual_author=True,
            skip_hooks=True,
        )
        self._register_repo(example=example)

        self._post_commit_edits()

        self.review_manager.logger.info(
            "%sCompleted init operation%s", Colors.GREEN, Colors.END
        )

    def _format_review_type(self, review_type: str) -> str:
        formatted_review_type = review_type.replace("-", "_").lower().replace(" ", "_")
        if "." not in formatted_review_type:
            formatted_review_type = "colrev." + formatted_review_type

        return formatted_review_type

    def _reset_if_existing_repo_with_single_commit(self) -> None:
        def is_empty_colrev_template() -> bool:
            files = list(
                os.path.join(root, file)
                for root, _, files in os.walk(self.target_path)
                for file in files
            )
            files = [os.path.relpath(file, self.target_path) for file in files]
            files = [
                file
                for file in files
                if not file.startswith(".git/")
                and not file.startswith(".devcontainer/")
            ]
            return not files

        try:
            git_repo = git.Repo.init()
            if len(list(git_repo.iter_commits())) == 1:
                if is_empty_colrev_template():
                    return
                print("Detected existing repository")
                if "y" != input("Reset existing repository? (y/n) "):
                    raise colrev_exceptions.CoLRevException("Operation aborted.")
                for root, dirs, files in os.walk(self.target_path):
                    for file in files:
                        os.remove(os.path.join(root, file))
                    for directory in dirs:
                        shutil.rmtree(os.path.join(root, directory))
        except (InvalidGitRepositoryError, ValueError):
            pass

    def _check_init_precondition(self) -> None:
        if self.force_mode:
            return
        cur_content = [
            str(x.relative_to(self.target_path)) for x in self.target_path.glob("**/*")
        ]
        cur_content = [
            x for x in cur_content if not x.startswith("venv") and x != ".history"
        ]
        if str(self.review_manager.paths.REPORT_FILE) in cur_content:
            cur_content.remove(str(self.review_manager.paths.REPORT_FILE))

        if all(x.startswith((".git", ".devcontainer", ".vscode")) for x in cur_content):
            return

        if all(x.startswith((".git", ".devcontainer", ".vscode")) for x in cur_content):
            return

        if cur_content:
            raise colrev_exceptions.NonEmptyDirectoryError(
                filepath=self.target_path, content=cur_content
            )

        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        environment_manager.get_name_mail_from_git()

        try:
            colrev.env.docker_manager.DockerManager.check_docker_installed()
        except colrev_exceptions.MissingDependencyError as exc:  # pragma: no cover
            if not self.no_docker:
                raise colrev_exceptions.CoLRevException(
                    "Docker not installed. Docker is optional but recommended.\n"
                    "For more information, see "
                    "https://colrev.readthedocs.io/en/latest/manual/manual.html"
                    "To init a repository without Docker, run "
                    f"{Colors.ORANGE}colrev init --light{Colors.END}"
                ) from exc

    def _setup_git(self) -> None:
        self.review_manager.logger.info("Set up git repository")

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
        ]
        for script_to_call in scripts_to_call:
            try:
                if script_to_call["description"]:
                    self.review_manager.logger.debug(
                        "%s...", script_to_call["description"]
                    )
                check_call(
                    script_to_call["command"], stdout=DEVNULL, stderr=STDOUT
                )  # nosec
            except CalledProcessError:
                if " ".join(script_to_call["command"]) == "pre-commit autoupdate":
                    pass
                else:
                    self.review_manager.logger.error(
                        "%sFailed: %s%s",
                        Colors.RED,
                        " ".join(script_to_call),
                        Colors.END,
                    )

    def _fix_pre_commit_hooks_windows(self) -> None:
        # https://stackoverflow.com/questions/12410164/github-for-windows-pre-commit-hook
        if any(platform.win32_ver()):
            with open(".git/hooks/pre-commit", encoding="utf-8") as file:
                lines = file.readlines()

            lines[0] = """#!C:/Program\\ Files/Git/usr/bin/sh.exe\n"""

            with open(".git/hooks/pre-commit", "w", encoding="utf-8") as file:
                file.writelines(lines)

    def _setup_files(self) -> None:

        # Note: parse instead of copy to avoid format changes
        settings_filedata = colrev.env.utils.get_package_file_content(
            module="colrev.ops", filename=Path("init/settings.json")
        )
        if settings_filedata:
            settings = json.loads(settings_filedata.decode("utf-8"))
            settings["project"]["review_type"] = str(self.review_type)
            with open(self.review_manager.paths.settings, "w", encoding="utf8") as file:
                json.dump(settings, file, indent=4)

        self.review_manager.paths.search.mkdir(parents=True)
        self.review_manager.paths.pdf.mkdir(parents=True)

        colrev_path = Path.home() / Path("colrev")
        colrev_path.mkdir(exist_ok=True, parents=True)

        files_to_retrieve = [
            [Path("ops/init/readme.md"), self.review_manager.paths.readme],
            [
                Path("ops/init/pre-commit-config.yaml"),
                self.review_manager.paths.pre_commit_config,
            ],
            [
                Path("ops/init/markdownlint.yaml"),
                self.review_manager.path / Path(".markdownlint.yaml"),
            ],
            [
                Path("ops/init/pre-commit.yml"),
                self.review_manager.path / Path(".github/workflows/pre-commit.yml"),
            ],
            [
                Path("ops/init/gitattributes"),
                self.review_manager.path / Path(".gitattributes"),
            ],
            [
                Path("ops/init/LICENSE-CC-BY-4.0.txt"),
                self.review_manager.path / Path("LICENSE.txt"),
            ],
            [
                Path("ops/init/colrev_update.yml"),
                self.review_manager.path / Path(".github/workflows/colrev_update.yml"),
            ],
        ]
        for retrieval_path, target_path in files_to_retrieve:
            colrev.env.utils.retrieve_package_file(
                template_file=retrieval_path, target=target_path
            )

    def _setup_settings(self) -> None:

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

        # Principle: adapt values provided by the default SETTINGS_FILE
        # instead of creating a new SETTINGS_FILE
        package_manager = self.review_manager.get_package_manager()
        review_type_class = package_manager.get_package_endpoint_class(
            package_type=EndpointType.review_type,
            package_identifier=self.review_type,
        )
        check_operation = colrev.ops.check.CheckOperation(self.review_manager)
        review_type_object = review_type_class(
            operation=check_operation,
            settings={"endpoint": settings.project.review_type},
        )

        settings = review_type_object.initialize(settings=settings)
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
            r_type_suffix = str(review_type_object)

            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{project_title}}",
                new_string=project_title.rstrip(" ").capitalize()
                + f": A {r_type_suffix} protocol",
            )

        if self.no_docker:
            settings.data.data_package_endpoints = [
                x
                for x in settings.data.data_package_endpoints
                if x["endpoint"] not in ["colrev.paper_md"]
            ]
            settings.sources = [
                x for x in settings.sources if x.endpoint not in ["colrev.files_dir"]
            ]

            settings.pdf_prep.pdf_prep_package_endpoints = [
                x
                for x in settings.pdf_prep.pdf_prep_package_endpoints
                if x["endpoint"]
                not in [
                    "colrev.ocrmypdf",
                    "colrev.remove_coverpage",
                    "colrev.remove_last_page",
                    "colrev.grobid_tei",
                ]
            ]

        self.review_manager.save_settings()

    def _finalize(self) -> None:
        settings = self.review_manager.settings

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

        with open(
            self.review_manager.paths.records, mode="w", encoding="utf-8"
        ) as file:
            file.write("\n")

        self._fix_pre_commit_hooks_windows()

        git_repo = self.review_manager.dataset.get_repo()
        git_repo.git.add(all=True)

    def _register_repo(self, *, example: bool) -> None:
        if example or "pytest" in os.getcwd():
            return
        self.review_manager.logger.info("Register CoLRev repository")
        environment_manager = self.review_manager.get_environment_manager()
        environment_manager.register_repo(
            self.target_path, logger=self.review_manager.logger
        )

    def _post_commit_edits(self) -> None:
        if self.review_type != "colrev.curated_masterdata":
            return

        self.review_manager.logger.info("Post-commit edits")
        self.review_manager.settings.project.curation_url = "TODO"
        self.review_manager.settings.project.curated_fields = [
            Fields.URL,
            Fields.DOI,
            "TODO",
        ]

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
                    Fields.JOURNAL: "TODO",
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

    def _create_example_repo(self) -> None:
        """The example repository is intended to provide an initial illustration
        of CoLRev. It focuses on a quick overview of the process and does
        not cover advanced features or special cases."""

        self.review_manager.logger.info("Include 30_example_records.bib")
        colrev.env.utils.retrieve_package_file(
            template_file=Path("ops/init/30_example_records.bib"),
            target=Path("data/search/30_example_records.bib"),
        )

        git_repo = self.review_manager.dataset.get_repo()
        git_repo.index.add(["data/search/30_example_records.bib"])

        with open(self.review_manager.paths.settings, encoding="utf-8") as file:
            settings = json.load(file)

        settings["dedupe"]["dedupe_package_endpoints"] = [{"endpoint": "colrev.dedupe"}]
        settings["sources"] = [
            {
                "endpoint": "colrev.unknown_source",
                "filename": str(Path("data/search/30_example_records.bib")),
                "search_type": "DB",
                "search_parameters": {
                    "query_file": str(Path("data/search/30_example_records_query.txt"))
                },
                "comment": "",
            }
        ]

        with open(self.review_manager.paths.settings, "w", encoding="utf-8") as outfile:
            json.dump(settings, outfile, indent=4)
        git_repo.index.add([self.review_manager.paths.SETTINGS_FILE])
