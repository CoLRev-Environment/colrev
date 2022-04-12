#!/usr/bin/env python3
import ast
import configparser
import importlib
import io
import logging
import multiprocessing as mp
import os
import pprint
import re
import sys
import tempfile
import typing
from contextlib import redirect_stdout
from importlib.metadata import version
from pathlib import Path

import git
import yaml

from colrev_core import review_dataset
from colrev_core.data import ManuscriptRecordSourceTagError
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import UnstagedGitChangesError
from colrev_core.review_dataset import DuplicatesError
from colrev_core.review_dataset import FieldError
from colrev_core.review_dataset import OriginError
from colrev_core.review_dataset import PropagatedIDChange


class ReviewManager:

    notified_next_process = None

    def __init__(self, path_str: str = None, force_mode: bool = False) -> None:
        from colrev_core.review_dataset import ReviewDataset

        self.force_mode = force_mode

        if path_str is not None:
            self.path = Path(path_str)
        else:
            self.path = Path.cwd()

        self.paths = self.__get_file_paths(self.path)
        self.config = self.__load_config()

        if self.config["DEBUG_MODE"]:
            self.report_logger = self.__setup_report_logger(logging.DEBUG)
            self.logger = self.__setup_logger(logging.DEBUG)
        else:
            self.report_logger = self.__setup_report_logger(logging.INFO)
            self.logger = self.__setup_logger(logging.INFO)

        self.pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)
        self.REVIEW_DATASET = ReviewDataset(self)
        self.sources = self.REVIEW_DATASET.load_sources()

        try:
            self.config["DATA_FORMAT"] = ast.literal_eval(self.config["DATA_FORMAT"])
        except ValueError:
            self.logger.error(
                f'Could not load DATA_FORMAT ({self.config["DATA_FORMAT"] }), '
                "using fallback"
            )
            self.config["DATA_FORMAT"] = ["MANUSCRIPT"]
            pass

        if self.config["DEBUG_MODE"]:
            print("\n\n")
            self.logger.debug("Created review manager instance")
            self.logger.debug(f" config: {self.pp.pformat(self.config)}")

    def __get_file_paths(self, repository_dir_str: Path) -> dict:
        repository_dir = repository_dir_str
        main_refs = "references.bib"
        data = "data.csv"
        pdf_dir = "pdfs"
        sources = "sources.yaml"
        paper = "paper.md"
        shared_config = "shared_config.ini"
        private_config = "private_config.ini"
        readme = "readme.md"
        report = "report.log"
        search_dir = "search"
        status = "status.yaml"
        corrections = ".corrections"
        return {
            "REPO_DIR": repository_dir,
            "MAIN_REFERENCES_RELATIVE": Path(main_refs),
            "MAIN_REFERENCES": repository_dir.joinpath(main_refs),
            "DATA_RELATIVE": Path(data),
            "DATA": repository_dir.joinpath(data),
            "PDF_DIRECTORY_RELATIVE": Path(pdf_dir),
            "PDF_DIRECTORY": repository_dir.joinpath(pdf_dir),
            "SOURCES_RELATIVE": Path(sources),
            "SOURCES": repository_dir.joinpath(sources),
            "PAPER_RELATIVE": Path(paper),
            "PAPER": repository_dir.joinpath(paper),
            "SHARED_CONFIG_RELATIVE": Path(shared_config),
            "SHARED_CONFIG": repository_dir.joinpath(shared_config),
            "PRIVATE_CONFIG_RELATIVE": Path(private_config),
            "PRIVATE_CONFIG": repository_dir.joinpath(private_config),
            "README_RELATIVE": Path(readme),
            "README": repository_dir.joinpath(readme),
            "REPORT_RELATIVE": Path(report),
            "REPORT": repository_dir.joinpath(report),
            "SEARCHDIR_RELATIVE": Path(search_dir),
            "SEARCHDIR": repository_dir.joinpath(search_dir),
            "STATUS_RELATIVE": Path(status),
            "STATUS": repository_dir.joinpath(status),
            "CORRECTIONS_PATH": repository_dir.joinpath(corrections),
        }

    def __load_config(self) -> dict:
        local_config = configparser.ConfigParser()
        confs = []
        if self.paths["SHARED_CONFIG"].is_file():
            confs.append(self.paths["SHARED_CONFIG"])
        if self.paths["PRIVATE_CONFIG"].is_file():
            confs.append(self.paths["PRIVATE_CONFIG"])
        local_config.read(confs)

        csl_fallback = (
            "https://raw.githubusercontent.com/citation-style-language/"
            + "styles/6152ccea8b7d7a472910d36524d1bf3557a83bfc/mis-quarterly.csl"
        )

        word_template_url_fallback = (
            "https://raw.githubusercontent.com/geritwagner/templates/main/MISQ.docx"
        )
        config = dict(
            DELAY_AUTOMATED_PROCESSING=local_config.getboolean(
                "general", "DELAY_AUTOMATED_PROCESSING", fallback=True
            ),
            BATCH_SIZE=local_config.getint("general", "BATCH_SIZE", fallback=500),
            SHARE_STAT_REQ=local_config.get(
                "general", "SHARE_STAT_REQ", fallback="PROCESSED"
            ),
            CPUS=local_config.getint("general", "CPUS", fallback=mp.cpu_count() - 1),
            EMAIL=local_config.get(
                "general", "EMAIL", fallback=self.__email_fallback()
            ),
            GIT_ACTOR=local_config.get(
                "general", "GIT_ACTOR", fallback=self.__actor_fallback()
            ),
            DEBUG_MODE=local_config.getboolean("general", "DEBUG_MODE", fallback=False),
            DATA_FORMAT=local_config.get(
                "general", "DATA_FORMAT", fallback='["MANUSCRIPT"]'
            ),
            ID_PATTERN=local_config.get(
                "general", "ID_PATTERN", fallback="THREE_AUTHORS_YEAR"
            ),
            CSL=local_config.get("general", "CSL", fallback=csl_fallback),
            WORD_TEMPLATE_URL=local_config.get(
                "general", "WORD_TEMPLATE_URL", fallback=word_template_url_fallback
            ),
            PDF_PATH_TYPE=local_config.get(
                "general", "PDF_PATH_TYPE", fallback="SYMLINK"
            ),
        )
        return config

    def get_remote_url(self):
        git_repo = self.REVIEW_DATASET.get_repo()
        for remote in git_repo.remotes:
            if remote.url:
                remote_url = remote.url.rstrip(".git")
                return remote_url

        return None

    def __actor_fallback(self) -> str:
        from colrev_core.environment import EnvironmentManager

        name = EnvironmentManager.get_name_mail_from_global_git_config()[0]
        return name

    def __email_fallback(self) -> str:
        from colrev_core.environment import EnvironmentManager

        email = EnvironmentManager.get_name_mail_from_global_git_config()[1]
        return email

    def __setup_logger(self, level=logging.INFO) -> logging.Logger:
        # for logger debugging:
        # from logging_tree import printout
        # printout()
        logger = logging.getLogger(f"colrev_core{str(self.path).replace('/', '_')}")

        logger.setLevel(level)

        if logger.handlers:
            for handler in logger.handlers:
                logger.removeHandler(handler)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(level)

        logger.addHandler(handler)
        logger.propagate = False

        return logger

    def __setup_report_logger(self, level=logging.INFO) -> logging.Logger:
        report_logger = logging.getLogger(
            f"colrev_core_report{str(self.path).replace('/', '_')}"
        )

        if report_logger.handlers:
            for handler in report_logger.handlers:
                report_logger.removeHandler(handler)

        report_logger.setLevel(level)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        report_file_handler = logging.FileHandler("report.log", mode="a")
        report_file_handler.setFormatter(formatter)

        report_logger.addHandler(report_file_handler)

        if logging.DEBUG == level:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            report_logger.addHandler(handler)
        report_logger.propagate = False

        return report_logger

    def __get_colrev_versions(self) -> typing.List[str]:

        current_colrev_core_version = version("colrev_core")
        last_colrev_core_version = current_colrev_core_version

        last_commit_message = self.REVIEW_DATASET.get_commit_message(0)
        cmsg_lines = last_commit_message.split("\n")
        for cmsg_line in cmsg_lines[0:100]:
            if "colrev_core" in cmsg_line and "version" in cmsg_line:
                last_colrev_core_version = cmsg_line[cmsg_line.find("version ") + 8 :]

        return [last_colrev_core_version, current_colrev_core_version]

    def __check_software(self) -> None:
        last_version, current_version = self.__get_colrev_versions()
        if last_version != current_version:
            raise SoftwareUpgradeError(last_version, current_version)
        return

    def upgrade_colrev(self) -> None:
        from colrev_core.process import CheckProcess

        last_version, current_version = self.__get_colrev_versions()

        if "+" in last_version:
            last_version = last_version[: last_version.find("+")]
        if "+" in current_version:
            current_version = current_version[: current_version.find("+")]

        cur_major = current_version[: current_version.rfind(".")]
        next_minor = str(int(current_version[current_version.rfind(".") + 1 :]) + 1)
        upcoming_version = cur_major + "." + next_minor

        CheckProcess(self)  # to notify

        def inplace_change(filename: Path, old_string: str, new_string: str) -> None:
            with open(filename) as f:
                s = f.read()
                if old_string not in s:
                    logging.info(f'"{old_string}" not found in {filename}.')
                    return
            with open(filename, "w") as f:
                s = s.replace(old_string, new_string)
                f.write(s)
            return

        def migrate_0_3_0(self) -> bool:
            records = self.REVIEW_DATASET.load_records_dict()
            if len(records.values()) > 0:
                for record in records.values():
                    if "LOCAL_INDEX" == record.get("metadata_source", ""):
                        record["metadata_source"] = "CURATED"
                    if "pdf_hash" in record:
                        record["colrev_pdf_id"] = "cpid1:" + record["pdf_hash"]
                        del record["pdf_hash"]

                self.REVIEW_DATASET.save_records_dict(records)
                self.REVIEW_DATASET.add_record_changes()

            inplace_change(
                self.paths["SOURCES"], "search_type: LOCAL_PAPER_INDEX", "PDFS"
            )
            self.REVIEW_DATASET.add_changes(str(self.paths["SOURCES_RELATIVE"]))

            if self.REVIEW_DATASET.has_changes():
                return True
            return False

        def migrate_0_4_0(self) -> bool:
            from colrev_core.record import Record
            from tqdm import tqdm

            self.logger.info("Create alsoKnownAs fields from origins and history")
            recs_dict = self.REVIEW_DATASET.load_records_dict()
            if len(recs_dict) > 0:
                origin_records = self.REVIEW_DATASET.load_origin_records()
                for rec in tqdm(recs_dict.values()):
                    RECORD = Record(rec)
                    origins = RECORD.get_origins()
                    RECORD.set_also_known_as(
                        [origin_records[origin] for origin in origins]
                    )
                for history_recs in self.REVIEW_DATASET.load_from_git_history():
                    for hist_rec in tqdm(history_recs.values()):
                        for rec in recs_dict.values():
                            RECORD = Record(rec)
                            HIST_RECORD = Record(hist_rec)
                            # TODO : acces hist_rec based on an origin-key record-list?
                            if RECORD.shares_origins(HIST_RECORD):
                                RECORD.set_also_known_as([HIST_RECORD.get_data()])

                self.REVIEW_DATASET.save_records_dict(recs_dict)
                self.REVIEW_DATASET.add_record_changes()

            return True

        # next version should be:
        # ...
        # {'from': '0.4.0', "to": '0.5.0', 'script': migrate_0_4_0}
        # {'from': '0.5.0', "to": upcoming_version, 'script': migrate_0_5_0}
        migration_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {"from": "0.3.0", "to": "0.4.0", "script": migrate_0_3_0},
            {"from": "0.4.0", "to": upcoming_version, "script": migrate_0_4_0},
        ]

        # Start with the first step if the version is older:
        if last_version not in [x["from"] for x in migration_scripts]:
            last_version = "0.3.0"

        while current_version in [x["from"] for x in migration_scripts]:
            self.logger.info(f"Current CoLRev version: {last_version}")

            migrator = [x for x in migration_scripts if x["from"] == last_version].pop()

            migration_script = migrator["script"]

            self.logger.info(f"Migrating from {migrator['from']} to {migrator['to']}")

            updated = migration_script(self)
            if updated:
                self.logger.info(f"Updated to: {current_version}")
            else:
                self.logger.info("Nothing to do.")
                self.logger.info(
                    "If the update notification occurs again, run\n "
                    "git commit -n -m --allow-empty 'update colrev'"
                )

            # Note : the version in the commit message will be set to
            # the current_version immediately. Therefore, use the migrator['to'] field.
            last_version = migrator["to"]

            if last_version == upcoming_version:
                break

        if self.REVIEW_DATASET.has_changes():
            self.create_commit(f"Upgrade to CoLRev {upcoming_version}")

        return

    def __check_repository_setup(self) -> None:
        from git.exc import GitCommandError

        # 1. git repository?
        if not self.__is_git_repo(self.paths["REPO_DIR"]):
            raise RepoSetupError("no git repository. Use colrev_core init")

        # 2. colrev_core project?
        if not self.__is_colrev_core_project():
            raise RepoSetupError(
                "No colrev_core repository."
                + "To retrieve a shared repository, use colrev_core init."
                + "To initalize a new repository, "
                + "execute the command in an empty directory."
            )

        installed_hooks = self.__get_installed_hooks()

        # 3. Pre-commit hooks installed?
        self.__require_hooks_installed(installed_hooks)

        # 4. Pre-commit hooks up-to-date?
        try:
            if not self.__hooks_up_to_date(installed_hooks):
                raise RepoSetupError(
                    "Pre-commit hooks not up-to-date. Use\n"
                    + "colrev config --update_hooks"
                )
                # This could also be a warning, but hooks should not change often.

        except GitCommandError:
            self.logger.warning(
                "No Internet connection, cannot check remote "
                "colrev-hooks repository for updates."
            )
        return

    def __get_base_prefix_compat(self) -> str:
        return (
            getattr(sys, "base_prefix", None)
            or getattr(sys, "real_prefix", None)
            or sys.prefix
        )

    def in_virtualenv(self) -> bool:
        return self.__get_base_prefix_compat() != sys.prefix

    def __check_git_conflicts(self) -> None:
        # Note: when check is called directly from the command line.
        # pre-commit hooks automatically notify on merge conflicts

        git_repo = git.Repo(str(self.paths["REPO_DIR"]))
        unmerged_blobs = git_repo.index.unmerged_blobs()

        for path in unmerged_blobs:
            list_of_blobs = unmerged_blobs[path]
            for (stage, blob) in list_of_blobs:
                if stage != 0:
                    raise GitConflictError(path)
        return

    def __is_git_repo(self, path: Path) -> bool:
        from git.exc import InvalidGitRepositoryError

        try:
            _ = git.Repo(str(path)).git_dir
            return True
        except InvalidGitRepositoryError:
            return False

    def __is_colrev_core_project(self) -> bool:
        # Note : 'private_config.ini', 'shared_config.ini' are optional
        # "search",
        required_paths = [Path(".pre-commit-config.yaml"), Path(".gitignore")]
        if not all(x.is_file() for x in required_paths):
            return False
        return True

    def __get_installed_hooks(self) -> dict:
        installed_hooks: dict = {"hooks": list()}
        with open(".pre-commit-config.yaml") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
        installed_hooks[
            "remote_pv_hooks_repo"
        ] = "https://github.com/geritwagner/colrev-hooks"
        for repository in pre_commit_config["repos"]:
            if repository["repo"] == installed_hooks["remote_pv_hooks_repo"]:
                installed_hooks["local_hooks_version"] = repository["rev"]
                installed_hooks["hooks"] = [hook["id"] for hook in repository["hooks"]]
        return installed_hooks

    def __lsremote(self, url: str) -> dict:
        remote_refs = {}
        g = git.cmd.Git()
        for ref in g.ls_remote(url).split("\n"):
            hash_ref_list = ref.split("\t")
            remote_refs[hash_ref_list[1]] = hash_ref_list[0]
        return remote_refs

    def __hooks_up_to_date(self, installed_hooks: dict) -> bool:
        refs = self.__lsremote(installed_hooks["remote_pv_hooks_repo"])
        remote_sha = refs["HEAD"]
        if remote_sha == installed_hooks["local_hooks_version"]:
            return True
        return False

    def __require_hooks_installed(self, installed_hooks: dict) -> bool:
        required_hooks = ["check", "format", "report", "sharing"]
        hooks_activated = set(installed_hooks["hooks"]) == set(required_hooks)
        if not hooks_activated:
            missing_hooks = [
                x for x in required_hooks if x not in installed_hooks["hooks"]
            ]
            raise RepoSetupError(
                f"missing hooks in .pre-commit-config.yaml ({missing_hooks})"
            )

        pch_file = Path(".git/hooks/pre-commit")
        if pch_file.is_file():
            with open(pch_file) as f:
                if "File generated by pre-commit" not in f.read(4096):
                    raise RepoSetupError(
                        "pre-commit hooks not installed (use pre-commit install)"
                    )
        else:
            raise RepoSetupError(
                "pre-commit hooks not installed (use pre-commit install)"
            )

        psh_file = Path(".git/hooks/pre-push")
        if psh_file.is_file():
            with open(psh_file) as f:
                if "File generated by pre-commit" not in f.read(4096):
                    raise RepoSetupError(
                        "pre-commit push hooks not installed "
                        "(use pre-commit install --hook-type pre-push)"
                    )
        else:
            raise RepoSetupError(
                "pre-commit push hooks not installed "
                "(use pre-commit install --hook-type pre-push)"
            )

        pcmh_file = Path(".git/hooks/prepare-commit-msg")
        if pcmh_file.is_file():
            with open(pcmh_file) as f:
                if "File generated by pre-commit" not in f.read(4096):
                    raise RepoSetupError(
                        "pre-commit prepare-commit-msg hooks not installed "
                        "(use pre-commit install --hook-type prepare-commit-msg)"
                    )
        else:
            raise RepoSetupError(
                "pre-commit prepare-commit-msg hooks not installed "
                "(use pre-commit install --hook-type prepare-commit-msg)"
            )

        return True

    def check_repo(self) -> dict:
        """Check whether the repository is in a consistent state
        Entrypoint for pre-commit hooks
        """
        # Note : we have to return status code and message
        # because printing from other packages does not work in pre-commit hook.

        from colrev_core.environment import EnvironmentManager

        # We work with exceptions because each issue may be raised in different checks.
        self.notified_next_process = ProcessType.check
        PASS, FAIL = 0, 1
        check_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {"script": EnvironmentManager.check_git_installed, "params": []},
            {"script": EnvironmentManager.check_docker_installed, "params": []},
            {"script": EnvironmentManager.build_docker_images, "params": []},
            {"script": self.__check_git_conflicts, "params": []},
            {"script": self.__check_repository_setup, "params": []},
            {"script": self.__check_software, "params": []},
        ]

        not self.paths["SEARCHDIR"].mkdir(exist_ok=True)

        if not self.paths["MAIN_REFERENCES"].is_file():
            self.logger.debug("Checks for MAIN_REFERENCES not activated")
        else:

            # Note : retrieving data once is more efficient than
            # reading the MAIN_REFERENCES multiple times (for each check)

            if self.REVIEW_DATASET.file_in_history(
                self.paths["MAIN_REFERENCES_RELATIVE"]
            ):
                prior = self.REVIEW_DATASET.retrieve_prior()
                self.logger.debug("prior")
                self.logger.debug(self.pp.pformat(prior))
            else:  # if MAIN_REFERENCES not yet in git history
                prior = {}

            data = self.REVIEW_DATASET.retrieve_data(prior)
            self.logger.debug("data")
            self.logger.debug(self.pp.pformat(data))

            main_refs_checks = [
                {
                    "script": self.REVIEW_DATASET.check_persisted_ID_changes,
                    "params": [prior, data],
                },
                {"script": self.REVIEW_DATASET.check_sources, "params": []},
                {
                    "script": self.REVIEW_DATASET.check_main_references_duplicates,
                    "params": data,
                },
                {
                    "script": self.REVIEW_DATASET.check_main_references_origin,
                    "params": [prior, data],
                },
                {
                    "script": self.REVIEW_DATASET.check_main_references_status_fields,
                    "params": data,
                },
                {
                    "script": self.REVIEW_DATASET.check_status_transitions,
                    "params": data,
                },
                {
                    "script": self.REVIEW_DATASET.check_main_references_screen,
                    "params": data,
                },
            ]

            if prior == {}:  # Selected checks if MAIN_REFERENCES not yet in git history
                main_refs_checks = [
                    x
                    for x in main_refs_checks
                    if x["script"]
                    in [
                        "check_sources",
                        "check_main_references_duplicates",
                    ]
                ]

            check_scripts += main_refs_checks

            self.logger.debug("Checks for MAIN_REFERENCES activated")

            PAPER = self.paths["PAPER"]
            if not PAPER.is_file():
                self.logger.debug("Checks for PAPER not activated\n")
            else:
                from colrev_core.data import Data

                DATA = Data(self, notify_state_transition_process=False)
                manuscript_checks = [
                    {
                        "script": DATA.check_new_record_source_tag,
                        "params": [],
                    },
                    {
                        "script": DATA.update_synthesized_status,
                        "params": [],
                    },
                    {
                        "script": self.update_status_yaml,
                        "params": [],
                    },
                ]
                check_scripts += manuscript_checks
                self.logger.debug("Checks for PAPER activated\n")

            # TODO: checks for structured data
            # See functions in comments
            # if DATA.is_file():
            #     data = pd.read_csv(DATA, dtype=str)
            #     check_duplicates_data(data)
            # check_screen_data(screen, data)
            # DATA = REVIEW_MANAGER.paths['DATA']

        try:

            for check_script in check_scripts:
                if [] == check_script["params"]:
                    self.logger.debug(f'{check_script["script"].__name__}() called')
                    check_script["script"]()
                else:
                    self.logger.debug(
                        f'{check_script["script"].__name__}(params) called'
                    )
                    if type(check_script["params"]) == list:
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](check_script["params"])
                self.logger.debug(f'{check_script["script"].__name__}: passed\n')
        except PropagatedIDChange:
            pass
        except (
            MissingDependencyError,
            GitConflictError,
            # PropagatedIDChange,
            DuplicatesError,
            OriginError,
            FieldError,
            review_dataset.StatusTransitionError,
            ManuscriptRecordSourceTagError,
            UnstagedGitChangesError,
            review_dataset.StatusFieldValueError,
        ) as e:
            pass
            return {"status": FAIL, "msg": f"{type(e).__name__}: {e}"}
        return {"status": PASS, "msg": "Everything ok."}

    def report(self, msg_file: Path) -> dict:
        """Append commit-message report if not already available
        Entrypoint for pre-commit hooks)
        """

        update = False
        with open(msg_file) as f:
            contents = f.read()
            if "Command" not in contents:
                update = True
            if "Properties" in contents:
                update = False
        with open(msg_file, "w") as f:
            f.write(contents)
            # Don't append if it's already there
            if update:
                report = self.__get_commit_report("MANUAL", saved_args=None)
                f.write(report)

        self.REVIEW_DATASET.check_corrections_of_curated_records()

        return {"msg": "TODO", "status": 0}

    def sharing(self) -> dict:
        """Check whether sharing requirements are met
        Entrypoint for pre-commit hooks)
        """

        from colrev_core.status import Status

        STATUS = Status(self)
        stat = STATUS.get_status_freq()
        collaboration_instructions = STATUS.get_collaboration_instructions(stat)
        status_code = all(
            ["SUCCESS" == x["level"] for x in collaboration_instructions["items"]]
        )
        msgs = "\n ".join(
            [
                x["level"] + x["title"] + x.get("msg", "")
                for x in collaboration_instructions["items"]
            ]
        )
        return {"msg": msgs, "status": status_code}

    def format_references(self) -> dict:
        """Format the references
        Entrypoint for pre-commit hooks)
        """

        PASS, FAIL = 0, 1
        if not self.paths["MAIN_REFERENCES"].is_file():
            return {"status": PASS, "msg": "Everything ok."}

        try:
            changed = self.REVIEW_DATASET.format_main_references()
            self.update_status_yaml()

        except (UnstagedGitChangesError, review_dataset.StatusFieldValueError) as e:
            pass
            return {"status": FAIL, "msg": f"{type(e).__name__}: {e}"}

        if changed:
            return {"status": FAIL, "msg": "references formatted"}
        else:
            return {"status": PASS, "msg": "Everything ok."}

    def notify(self, process: Process, state_transition=True) -> None:
        """Notify the REVIEW_MANAGER about the next process"""

        if state_transition:
            process.check_precondition()
        self.notified_next_process = process.type
        self.REVIEW_DATASET.reset_log_if_no_changes()

    def __get_commit_report(
        self, script_name: str = None, saved_args: dict = None
    ) -> str:
        from colrev_core.status import Status

        report = "\n\nReport\n\n"

        if script_name is not None:
            if "MANUAL" == script_name:
                report = report + "Commit created manually or by external script\n\n"
            elif " " in script_name:
                script_name = script_name.replace("colrev_core", "colrev").replace(
                    "colrev cli", "colrev"
                )
                script_name = (
                    script_name.split(" ")[0]
                    + " "
                    + script_name.split(" ")[1].replace("_", "-")
                )

                report = report + f"Command\n   {script_name}"
        if saved_args is None:
            report = report + "\n"
        else:
            report = report + " \\ \n"
            for k, v in saved_args.items():
                if (
                    isinstance(v, str)
                    or isinstance(v, bool)
                    or isinstance(v, int)
                    or isinstance(v, float)
                ):
                    if v == "":
                        report = report + f"     --{k} \\\n"
                    else:
                        report = report + f"     --{k}={v} \\\n"
            # Replace the last backslash (for argument chaining across linebreaks)
            report = report.rstrip(" \\\n") + "\n"
            try:
                last_commit_sha = self.REVIEW_DATASET.get_last_commit_sha()
                report = report + f"   On git repo with version {last_commit_sha}\n"
            except ValueError:
                pass

        # url = g.execut['git', 'config', '--get remote.origin.url']

        # append status
        STATUS = Status(self)
        f = io.StringIO()
        with redirect_stdout(f):
            stat = STATUS.get_status_freq()
            STATUS.print_review_status(stat)

        # Remove colors for commit message
        status_page = (
            f.getvalue()
            .replace("\033[91m", "")
            .replace("\033[92m", "")
            .replace("\033[93m", "")
            .replace("\033[94m", "")
            .replace("\033[0m", "")
        )
        status_page = status_page.replace("Status\n\n", "Status\n")
        report = report + status_page

        tree_hash = self.REVIEW_DATASET.get_tree_hash()
        if self.paths["MAIN_REFERENCES"].is_file():
            tree_info = f"Properties for tree {tree_hash}\n"  # type: ignore
            report = report + "\n\n" + tree_info
            report = report + "   - Traceability of records ".ljust(38, " ") + "YES\n"
            report = (
                report + "   - Consistency (based on hooks) ".ljust(38, " ") + "YES\n"
            )
            completeness_condition = STATUS.get_completeness_condition()
            if completeness_condition:
                report = (
                    report + "   - Completeness of iteration ".ljust(38, " ") + "YES\n"
                )
            else:
                report = (
                    report + "   - Completeness of iteration ".ljust(38, " ") + "NO\n"
                )
            report = (
                report
                + "   To check tree_hash use".ljust(38, " ")
                + "git log --pretty=raw -1\n"
            )
            report = (
                report
                + "   To validate use".ljust(38, " ")
                + "colrev validate --properties\n"
                + "".ljust(38, " ")
                + "--commit INSERT_COMMIT_HASH"
            )
        report = report + "\n"

        report = report + "\nSoftware"
        rt_version = version("colrev_core")
        report = report + "\n   - colrev_core:".ljust(33, " ") + "version " + rt_version
        version("colrev_hooks")
        report = (
            report
            + "\n   - colrev hooks:".ljust(33, " ")
            + "version "
            + version("colrev_hooks")
        )
        sys_v = sys.version
        report = (
            report
            + "\n   - Python:".ljust(33, " ")
            + "version "
            + sys_v[: sys_v.find(" ")]
        )

        stream = os.popen("git --version")
        git_v = stream.read()
        report = (
            report
            + "\n   - Git:".ljust(33, " ")
            + git_v.replace("git ", "").replace("\n", "")
        )
        stream = os.popen("docker --version")
        docker_v = stream.read()
        report = (
            report
            + "\n   - Docker:".ljust(33, " ")
            + docker_v.replace("Docker ", "").replace("\n", "")
        )
        if script_name is not None:
            ext_script = script_name.split(" ")[0]
            if ext_script != "colrev_core":
                try:
                    script_version = version(ext_script)
                    report = (
                        report
                        + f"\n   - {ext_script}:".ljust(33, " ")
                        + "version "
                        + script_version
                    )
                except importlib.metadata.PackageNotFoundError:
                    pass

        if "dirty" in report:
            report = (
                report + "\n    * created with a modified version (not reproducible)"
            )
        report = report + "\n"

        return report

    def __get_version_flag(self) -> str:
        flag = ""
        if "dirty" in version("colrev_core"):
            flag = "*"
        return flag

    def update_status_yaml(self) -> None:
        from colrev_core.status import Status

        STATUS = Status(self)

        status_freq = STATUS.get_status_freq()
        with open(self.paths["STATUS"], "w") as f:
            yaml.dump(status_freq, f, allow_unicode=True)

        self.REVIEW_DATASET.add_changes(self.paths["STATUS_RELATIVE"])

        return

    def get_status(self) -> dict:
        status_dict = {}
        with open(self.paths["STATUS"]) as stream:
            try:
                status_dict = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
                pass
        return status_dict

    def reset_log(self) -> None:

        self.report_logger.handlers[0].stream.close()  # type: ignore
        self.report_logger.removeHandler(self.report_logger.handlers[0])

        with open("report.log", "r+") as f:
            f.truncate(0)

        file_handler = logging.FileHandler("report.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.report_logger.addHandler(file_handler)

        return

    def reorder_log(self, IDs: list, criterion=None) -> None:
        """Reorder the report.log according to an ID list (after multiprocessing)"""

        # https://docs.python.org/3/howto/logging-cookbook.html
        # #logging-to-a-single-file-from-multiple-processes

        self.report_logger.handlers[0].stream.close()  # type: ignore
        self.report_logger.removeHandler(self.report_logger.handlers[0])

        firsts = []
        ordered_items = ""
        consumed_items = []
        with open("report.log") as r:
            items = []  # type: ignore
            item = ""
            for line in r.readlines():
                if any(
                    x in line
                    for x in [
                        "[INFO] Prepare",
                        "[INFO] Completed ",
                        "[INFO] Batch size",
                        "[INFO] Summary: Prepared",
                        "[INFO] Further instructions ",
                        "[INFO] To reset the metdatata",
                        "[INFO] Summary: ",
                        "[INFO] Continuing batch ",
                        "[INFO] Load references.bib",
                        "[INFO] Calculate statistics",
                        "[INFO] ReviewManager: run ",
                        "[INFO] Retrieve PDFs",
                        "[INFO] Statistics:",
                        "[INFO] Set ",
                    ]
                ):
                    firsts.append(line)
                    continue
                if re.search(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ", line):
                    # prep: only list "Dropped xy field" once
                    if "[INFO] Dropped " in line:
                        if any(
                            item[item.find("[INFO] Dropped ") :] in x for x in items
                        ):
                            continue
                    if item != "":
                        item = item.replace("\n\n", "\n").replace("\n\n", "\n")
                        items.append(item)
                        item = ""
                    item = line
                else:
                    item = item + line

            items.append(item.replace("\n\n", "\n").replace("\n\n", "\n"))

        if criterion is None:
            for ID in IDs:
                for item in items:
                    if f"({ID})" in item:
                        formatted_item = item
                        if "] prepare(" in formatted_item:
                            formatted_item = f"\n\n{formatted_item}"
                        ordered_items = ordered_items + formatted_item
                        consumed_items.append(item)

            for x in consumed_items:
                if x in items:
                    items.remove(x)

        if criterion == "descending_thresholds":
            item_details = []
            while items:
                item = items.pop()
                confidence_value = re.search(r"\(confidence: (\d.\d{0,3})\)", item)
                if confidence_value:
                    item_details.append([confidence_value.group(1), item])
                    consumed_items.append(item)
                else:
                    firsts.append(item)

            item_details.sort(key=lambda x: x[0])
            ordered_items = "".join([x[1] for x in item_details])

        if len(ordered_items) > 0 or len(items) > 0:
            formatted_report = (
                "".join(firsts)
                + "\nDetailed report\n"
                + ordered_items.lstrip("\n")
                + "\n\n"
                + "".join(items)
            )
        else:
            formatted_report = "".join(firsts)

        with open("report.log", "w") as f:
            f.write(formatted_report)

        file_handler = logging.FileHandler("report.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.report_logger.addHandler(file_handler)

        return

    def create_commit(
        self, msg: str, manual_author: bool = False, saved_args: dict = None
    ) -> bool:
        """Create a commit (including a commit report)"""

        if self.REVIEW_DATASET.has_changes():

            self.update_status_yaml()
            self.REVIEW_DATASET.add_changes(self.paths["STATUS_RELATIVE"])

            hook_skipping = False
            if not self.config["DEBUG_MODE"]:
                hook_skipping = True

            processing_report = ""
            if self.paths["REPORT"].is_file():

                # Reformat
                prefixes = [
                    "[('change', 'author',",
                    "[('change', 'title',",
                    "[('change', 'journal',",
                    "[('change', 'booktitle',",
                ]
                temp = tempfile.NamedTemporaryFile()
                self.paths["REPORT"].rename(temp.name)
                with open(temp.name) as reader, open(
                    self.paths["REPORT"], "w"
                ) as writer:
                    line = reader.readline()
                    while line:
                        if (
                            any(prefix in line for prefix in prefixes)
                            and "', '" in line[30:]
                        ):
                            split_pos = line.rfind("', '") + 2
                            indent = line.find("', (") + 3
                            writer.write(line[:split_pos] + "\n")
                            writer.write(" " * indent + line[split_pos:])
                        else:
                            writer.write(line)

                        line = reader.readline()

                with open("report.log") as f:
                    line = f.readline()
                    debug_part = False
                    while line:
                        # For more efficient debugging (loading of dict with Enum)
                        if "'status" == line.lstrip()[:7] and "<RecordState." in line:
                            line = line.replace("<RecordState", "RecordState")
                            line = line[: line.rfind(":")] + line[line.rfind(">") + 1 :]
                        if "[DEBUG]" in line or debug_part:
                            debug_part = True
                            if any(
                                x in line
                                for x in ["[INFO]", "[ERROR]", "[WARNING]", "[CRITICAL"]
                            ):
                                debug_part = False
                        if not debug_part:
                            processing_report = processing_report + line
                        line = f.readline()

                processing_report = "\nProcessing report\n" + "".join(processing_report)

            caller = sys._getframe(1)
            from inspect import stack

            script = (
                str(caller.f_globals["__name__"]).replace("-", "_").replace(".", " ")
                + " "
                + str(stack()[1].function)
            )
            if "Update pre-commit-config" in msg:
                script = "pre-commit autoupdate"
            # TODO: test and update the following
            if "__apply_correction" in script:
                script = "apply_corrections"

            if manual_author:
                git_author = git.Actor(self.config["GIT_ACTOR"], self.config["EMAIL"])
            else:
                git_author = git.Actor(f"script:{script}", "")
            # TODO: test and update the following
            if "apply_correction" in script:
                cmsg = msg
            else:
                cmsg = (
                    msg
                    + self.__get_version_flag()
                    + self.__get_commit_report(f"{script}", saved_args)
                    + processing_report
                )
            self.REVIEW_DATASET.create_commit(
                cmsg,
                author=git_author,
                committer=git.Actor(self.config["GIT_ACTOR"], self.config["EMAIL"]),
                hook_skipping=hook_skipping,
            )

            self.logger.info("Created commit")
            self.reset_log()
            if self.REVIEW_DATASET.has_changes():
                raise DirtyRepoAfterProcessingError
            return True
        else:
            return False


class MissingDependencyError(Exception):
    def __init__(self, dep):
        self.message = f"please install {dep}"
        super().__init__(self.message)


class SoftwareUpgradeError(Exception):
    def __init__(self, old, new):
        self.message = (
            f"Detected upgrade from {old} to {new}. To upgrade use\n     "
            "colrev config --upgrade"
        )
        super().__init__(self.message)


class GitConflictError(Exception):
    def __init__(self, path):
        self.message = f"please resolve git conflict in {path}"
        super().__init__(self.message)


class DirtyRepoAfterProcessingError(Exception):
    pass


class ConsistencyError(Exception):
    pass


class RepoSetupError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class SearchDetailsMissingError(Exception):
    def __init__(
        self,
        search_results_path,
    ):
        self.message = (
            "Search results path "
            + f"({search_results_path.name}) "
            + "is not in sources.yaml"
        )
        super().__init__(self.message)


if __name__ == "__main__":
    pass
