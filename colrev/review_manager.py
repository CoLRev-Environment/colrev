#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import pprint
import sys
import typing
from dataclasses import asdict
from datetime import timedelta
from enum import Enum
from importlib.metadata import version
from pathlib import Path
from subprocess import check_call
from subprocess import DEVNULL
from subprocess import STDOUT

import dacite
import git
import requests_cache
import yaml
from dacite import from_dict
from dacite.exceptions import MissingValueError
from git.exc import GitCommandError
from git.exc import InvalidGitRepositoryError

import colrev.dataset
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record
import colrev.settings

PASS, FAIL = 0, 1


class ReviewManager:
    """Class for managing individual CoLRev review project (repositories)"""

    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods
    # pylint: disable=import-outside-toplevel
    # pylint: disable=redefined-outer-name

    notified_next_process = None
    """ReviewManager was notified for the upcoming process and
    will provide access to the Dataset"""

    SETTINGS_RELATIVE = Path("settings.json")
    REPORT_RELATIVE = Path("report.log")
    CORRECTIONS_PATH_RELATIVE = Path(".corrections")
    PDF_DIRECTORY_RELATIVE = Path("pdfs")
    SEARCHDIR_RELATIVE = Path("search")
    README_RELATIVE = Path("readme.md")
    STATUS_RELATIVE = Path("status.yaml")

    __COLREV_HOOKS_URL = "https://github.com/geritwagner/colrev-hooks"

    dataset: colrev.dataset.Dataset
    """The review dataset object"""

    def __init__(
        self,
        *,
        path_str: str = None,
        force_mode: bool = False,
        debug_mode: bool = False,
    ) -> None:

        self.force_mode = force_mode
        """Force mode variable (bool)"""

        if path_str is not None:
            self.path = Path(path_str)
            """Path of the project repository"""
        else:
            self.path = Path.cwd()

        self.settings_path = self.path / self.SETTINGS_RELATIVE
        self.report_path = self.path / self.REPORT_RELATIVE
        self.corrections_path = self.path / self.CORRECTIONS_PATH_RELATIVE
        self.pdf_directory = self.path / self.PDF_DIRECTORY_RELATIVE
        self.search_dir = self.path / self.SEARCHDIR_RELATIVE
        self.readme = self.path / self.README_RELATIVE
        self.status = self.path / self.STATUS_RELATIVE

        if debug_mode:
            self.debug_mode = True
        else:
            self.debug_mode = False

        try:
            if self.debug_mode:
                self.report_logger = self.__setup_report_logger(level=logging.DEBUG)
                """Logger for the commit report"""
                self.logger = self.__setup_logger(level=logging.DEBUG)
                """Logger for processing information"""
            else:
                self.report_logger = self.__setup_report_logger(level=logging.INFO)
                self.logger = self.__setup_logger(level=logging.INFO)

            self.committer, self.email = self._get_global_git_vars()

            self.p_printer = pprint.PrettyPrinter(indent=4, width=140, compact=False)
            self.dataset = colrev.dataset.Dataset(review_manager=self)
            self.settings = self.load_settings()

        except Exception as exc:  # pylint: disable=broad-except
            if force_mode:
                print(exc)
            else:
                raise exc

        if self.debug_mode:
            print("\n\n")
            self.logger.debug("Created review manager instance")
            self.logger.debug("Settings:\n%s", self.settings)

    def _get_global_git_vars(self) -> tuple:
        environment_manager = self.get_environment_manager()
        global_git_vars = environment_manager.get_name_mail_from_git()
        if 2 != len(global_git_vars):
            raise colrev_exceptions.CoLRevException(
                "Global git variables (user name and email) not available."
            )
        return global_git_vars

    def load_settings(self) -> colrev.settings.Configuration:

        # https://tech.preferred.jp/en/blog/working-with-configuration-in-python/
        # possible extension : integrate/merge global, default settings
        # from colrev.environment import EnvironmentManager
        # def selective_merge(base_obj, delta_obj):
        #     if not isinstance(base_obj, dict):
        #         return delta_obj
        #     common_keys = set(base_obj).intersection(delta_obj)
        #     new_keys = set(delta_obj).difference(common_keys)
        #     for k in common_keys:
        #         base_obj[k] = selective_merge(base_obj[k], delta_obj[k])
        #     for k in new_keys:
        #         base_obj[k] = delta_obj[k]
        #     return base_obj
        # print(selective_merge(default_settings, project_settings))

        if not self.settings_path.is_file():
            filedata = colrev.env.utils.get_package_file_content(
                file_path=Path("template/settings.json")
            )
            if filedata:
                settings = json.loads(filedata.decode("utf-8"))
                with open(self.settings_path, "w", encoding="utf8") as file:
                    json.dump(settings, file, indent=4)

        with open(self.settings_path, encoding="utf-8") as file:
            loaded_settings = json.load(file)

        try:
            converters = {Path: Path, Enum: Enum}
            settings = from_dict(
                data_class=colrev.settings.Configuration,
                data=loaded_settings,
                config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
            )
        except (ValueError, MissingValueError) as exc:
            raise colrev_exceptions.InvalidSettingsError(msg=exc) from exc

        return settings

    def save_settings(self) -> None:
        def custom_asdict_factory(data):
            def convert_value(obj):
                if isinstance(obj, Enum):
                    return obj.value
                if isinstance(obj, Path):
                    return str(obj)
                return obj

            return {k: convert_value(v) for k, v in data}

        exported_dict = asdict(self.settings, dict_factory=custom_asdict_factory)
        with open("settings.json", "w", encoding="utf-8") as outfile:
            json.dump(exported_dict, outfile, indent=4)
        self.dataset.add_changes(path=Path("settings.json"))

    def __setup_logger(self, *, level=logging.INFO) -> logging.Logger:
        # for logger debugging:
        # from logging_tree import printout
        # printout()
        logger = logging.getLogger(f"colrev{str(self.path).replace('/', '_')}")
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

    def __setup_report_logger(self, *, level=logging.INFO) -> logging.Logger:
        report_logger = logging.getLogger(
            f"colrev_report{str(self.path).replace('/', '_')}"
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

    def reset_log(self) -> None:
        self.report_logger.handlers[0].stream.close()  # type: ignore
        self.report_logger.removeHandler(self.report_logger.handlers[0])

        with open("report.log", "r+", encoding="utf8") as file:
            file.truncate(0)

        file_handler = logging.FileHandler("report.log")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        self.report_logger.addHandler(file_handler)

    def get_colrev_versions(self) -> list[str]:
        current_colrev_version = version("colrev")
        last_colrev_version = current_colrev_version
        last_commit_message = self.dataset.get_commit_message(commit_nr=0)
        cmsg_lines = last_commit_message.split("\n")
        for cmsg_line in cmsg_lines[0:100]:
            if "colrev:" in cmsg_line and "version" in cmsg_line:
                last_colrev_version = cmsg_line[cmsg_line.find("version ") + 8 :]
        return [last_colrev_version, current_colrev_version]

    def __check_software(self) -> None:
        last_version, current_version = self.get_colrev_versions()
        if last_version != current_version:
            raise colrev_exceptions.CoLRevUpgradeError(last_version, current_version)

    def __lsremote(self, *, url: str) -> dict:
        remote_refs = {}
        git_repo = git.cmd.Git()
        for ref in git_repo.ls_remote(url).split("\n"):
            hash_ref_list = ref.split("\t")
            remote_refs[hash_ref_list[1]] = hash_ref_list[0]
        return remote_refs

    def __colrev_hook_up_to_date(self) -> bool:

        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)

        local_hooks_version = ""
        for repository in pre_commit_config["repos"]:
            if repository["repo"] == self.__COLREV_HOOKS_URL:
                local_hooks_version = repository["rev"]

        refs = self.__lsremote(url=self.__COLREV_HOOKS_URL)
        remote_sha = refs["HEAD"]
        if remote_sha == local_hooks_version:
            return True
        return False

    def __update_colrev_hooks(self) -> None:
        if self.__COLREV_HOOKS_URL not in self.__get_installed_repos():
            return
        try:
            if not self.__colrev_hook_up_to_date():
                self.logger.info("Updating pre-commit hooks")
                check_call(["pre-commit", "autoupdate"], stdout=DEVNULL, stderr=STDOUT)
                self.dataset.add_changes(path=Path(".pre-commit-config.yaml"))
        except GitCommandError:
            self.logger.warning(
                "No Internet connection, cannot check remote "
                "colrev-hooks repository for updates."
            )
        return

    def check_repository_setup(self) -> None:

        # 1. git repository?
        if not self.__is_git_repo():
            raise colrev_exceptions.RepoSetupError("no git repository. Use colrev init")

        # 2. colrev project?
        if not self.__is_colrev_project():
            raise colrev_exceptions.RepoSetupError(
                "No colrev repository."
                + "To retrieve a shared repository, use colrev init."
                + "To initalize a new repository, "
                + "execute the command in an empty directory."
            )

        # 3. Pre-commit hooks installed?
        self.__require_colrev_hooks_installed()

        # 4. Pre-commit hooks up-to-date?
        self.__update_colrev_hooks()

    def in_virtualenv(self) -> bool:
        def get_base_prefix_compat() -> str:
            return (
                getattr(sys, "base_prefix", None)
                or getattr(sys, "real_prefix", None)
                or sys.prefix
            )

        return get_base_prefix_compat() != sys.prefix

    def __check_git_conflicts(self) -> None:
        # Note: when check is called directly from the command line.
        # pre-commit hooks automatically notify on merge conflicts

        git_repo = self.dataset.get_repo()
        unmerged_blobs = git_repo.index.unmerged_blobs()

        for path, list_of_blobs in unmerged_blobs.items():
            for (stage, _) in list_of_blobs:
                if stage != 0:
                    raise colrev_exceptions.GitConflictError(path)

    def __is_git_repo(self) -> bool:
        try:
            _ = self.dataset.get_repo().git_dir
            return True
        except InvalidGitRepositoryError:
            return False

    def __is_colrev_project(self) -> bool:
        required_paths = [
            Path(".pre-commit-config.yaml"),
            Path(".gitignore"),
            Path("settings.json"),
        ]
        if not all((self.path / x).is_file() for x in required_paths):
            return False
        return True

    def __get_installed_hooks(self) -> list:
        installed_hooks = []
        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
        for repository in pre_commit_config["repos"]:
            installed_hooks.extend([hook["id"] for hook in repository["hooks"]])
        return installed_hooks

    def __get_installed_repos(self) -> list:
        installed_repos = []
        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
        for repository in pre_commit_config["repos"]:
            installed_repos.append(repository["repo"])
        return installed_repos

    def __require_colrev_hooks_installed(self) -> bool:
        required_hooks = [
            "colrev-hooks-check",
            "colrev-hooks-format",
            "colrev-hooks-report",
            "colrev-hooks-share",
        ]
        installed_hooks = self.__get_installed_hooks()
        hooks_activated = set(required_hooks).issubset(set(installed_hooks))
        if not hooks_activated:
            missing_hooks = [x for x in required_hooks if x not in installed_hooks]
            raise colrev_exceptions.RepoSetupError(
                f"missing hooks in .pre-commit-config.yaml ({', '.join(missing_hooks)})"
            )

        pch_file = Path(".git/hooks/pre-commit")
        if pch_file.is_file():
            with open(pch_file, encoding="utf8") as file:
                if "File generated by pre-commit" not in file.read(4096):
                    raise colrev_exceptions.RepoSetupError(
                        "pre-commit hooks not installed (use pre-commit install)"
                    )
        else:
            raise colrev_exceptions.RepoSetupError(
                "pre-commit hooks not installed (use pre-commit install)"
            )

        psh_file = Path(".git/hooks/pre-push")
        if psh_file.is_file():
            with open(psh_file, encoding="utf8") as file:
                if "File generated by pre-commit" not in file.read(4096):
                    raise colrev_exceptions.RepoSetupError(
                        "pre-commit push hooks not installed "
                        "(use pre-commit install --hook-type pre-push)"
                    )
        else:
            raise colrev_exceptions.RepoSetupError(
                "pre-commit push hooks not installed "
                "(use pre-commit install --hook-type pre-push)"
            )

        pcmh_file = Path(".git/hooks/prepare-commit-msg")
        if pcmh_file.is_file():
            with open(pcmh_file, encoding="utf8") as file:
                if "File generated by pre-commit" not in file.read(4096):
                    raise colrev_exceptions.RepoSetupError(
                        "pre-commit prepare-commit-msg hooks not installed "
                        "(use pre-commit install --hook-type prepare-commit-msg)"
                    )
        else:
            raise colrev_exceptions.RepoSetupError(
                "pre-commit prepare-commit-msg hooks not installed "
                "(use pre-commit install --hook-type prepare-commit-msg)"
            )

        return True

    def check_repo(self) -> dict:
        """Check whether the repository is in a consistent state
        Entrypoint for pre-commit hooks
        """

        # pylint: disable=not-a-mapping

        self.notified_next_process = colrev.process.ProcessType.check
        self.search_dir.mkdir(exist_ok=True)

        # We work with exceptions because each issue may be raised in different checks.
        # Currently, linting is limited for the scripts.

        environment_manager = self.get_environment_manager()
        check_scripts: list[dict[str, typing.Any]] = [
            {
                "script": environment_manager.check_git_installed,
                "params": [],
            },
            {
                "script": environment_manager.check_docker_installed,
                "params": [],
            },
            {
                "script": environment_manager.build_docker_images,
                "params": [],
            },
            {"script": self.__check_git_conflicts, "params": []},
            {"script": self.check_repository_setup, "params": []},
            {"script": self.__check_software, "params": []},
        ]

        if self.dataset.records_file.is_file():

            if self.dataset.records_file_in_history():
                prior = self.dataset.retrieve_prior()
                self.logger.debug("prior")
                self.logger.debug(self.p_printer.pformat(prior))
            else:  # if RECORDS_FILE not yet in git history
                prior = {}

            status_data = self.dataset.retrieve_status_data(prior=prior)

            main_refs_checks = [
                {"script": self.dataset.check_sources, "params": []},
                {
                    "script": self.dataset.check_main_records_duplicates,
                    "params": {"status_data": status_data},
                },
            ]

            if prior:  # if RECORDS_FILE in git history
                main_refs_checks.extend(
                    [
                        {
                            "script": self.dataset.check_persisted_id_changes,
                            "params": {"prior": prior, "status_data": status_data},
                        },
                        {
                            "script": self.dataset.check_main_records_origin,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.dataset.check_fields,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.dataset.check_status_transitions,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.dataset.check_main_records_screen,
                            "params": {"status_data": status_data},
                        },
                    ]
                )

            check_scripts.extend(main_refs_checks)

            data_operation = self.get_data_operation(
                notify_state_transition_operation=False
            )
            data_checks = [
                {
                    "script": data_operation.main,
                    "params": [],
                },
                {
                    "script": self.update_status_yaml,
                    "params": [],
                },
            ]

            check_scripts.extend(data_checks)

        failure_items = []
        for check_script in check_scripts:
            try:
                if not check_script["params"]:
                    self.logger.debug("%s() called", check_script["script"].__name__)
                    check_script["script"]()
                else:
                    self.logger.debug(
                        "%s(params) called", check_script["script"].__name__
                    )
                    if isinstance(check_script["params"], list):
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](**check_script["params"])
                self.logger.debug("%s: passed\n", check_script["script"].__name__)
            except (
                colrev_exceptions.MissingDependencyError,
                colrev_exceptions.GitConflictError,
                colrev_exceptions.PropagatedIDChange,
                colrev_exceptions.DuplicateIDsError,
                colrev_exceptions.OriginError,
                colrev_exceptions.FieldValueError,
                colrev_exceptions.StatusTransitionError,
                colrev_exceptions.UnstagedGitChangesError,
                colrev_exceptions.StatusFieldValueError,
            ) as exc:
                failure_items.append(f"{type(exc).__name__}: {exc}")

        if len(failure_items) > 0:
            return {"status": FAIL, "msg": "  " + "\n  ".join(failure_items)}
        return {"status": PASS, "msg": "Everything ok."}

    def report(self, *, msg_file: Path) -> dict:
        """Append commit-message report if not already available
        Entrypoint for pre-commit hooks)
        """
        import colrev.ops.commit
        import colrev.ops.correct

        with open(msg_file, encoding="utf8") as file:
            available_contents = file.read()

        with open(msg_file, "w", encoding="utf8") as file:
            file.write(available_contents)
            # Don't append if it's already there
            update = False
            if "Command" not in available_contents:
                update = True
            if "Properties" in available_contents:
                update = False
            if update:
                commit = colrev.ops.commit.Commit(
                    review_manager=self,
                    msg=available_contents,
                    manual_author=True,
                    script_name="MANUAL",
                )
                report = commit.get_commit_report()
                file.write(report)

        colrev.process.CheckProcess(review_manager=self)  # to notify
        corrections_operation = colrev.ops.correct.Corrections(review_manager=self)
        corrections_operation.check_corrections_of_curated_records()

        return {"msg": "TODO", "status": 0}

    def sharing(self) -> dict:
        """Check whether sharing requirements are met
        Entrypoint for pre-commit hooks)
        """

        advisor = self.get_advisor()
        sharing_advice = advisor.get_sharing_instructions()
        return sharing_advice

    def format_records_file(self) -> dict:
        """Format the records file Entrypoint for pre-commit hooks)"""

        if not self.dataset.records_file.is_file():
            return {"status": PASS, "msg": "Everything ok."}

        try:
            colrev.process.FormatProcess(review_manager=self)  # to notify
            changed = self.dataset.format_records_file()
            self.update_status_yaml()
            self.settings = self.load_settings()
            self.save_settings()
        except (
            colrev_exceptions.UnstagedGitChangesError,
            colrev_exceptions.StatusFieldValueError,
        ) as exc:
            return {"status": FAIL, "msg": f"{type(exc).__name__}: {exc}"}

        if changed:
            return {"status": FAIL, "msg": "records file formatted"}

        return {"status": PASS, "msg": "Everything ok."}

    def notify(self, *, process: colrev.process.Process, state_transition=True) -> None:
        """Notify the review_manager about the next process"""

        if state_transition:
            process.check_precondition()
        self.notified_next_process = process.type
        self.dataset.reset_log_if_no_changes()

    def update_status_yaml(self) -> None:
        status_stats = self.get_status_stats()
        exported_dict = asdict(status_stats)
        with open(self.status, "w", encoding="utf8") as file:
            yaml.dump(exported_dict, file, allow_unicode=True)
        self.dataset.add_changes(path=self.STATUS_RELATIVE)

    def create_commit(
        self,
        *,
        msg: str,
        manual_author: bool = False,
        script_call: str = "",
        saved_args: dict = None,
        realtime_override: bool = False,
    ) -> bool:
        """Create a commit (including a commit report)"""
        import colrev.ops.commit

        commit = colrev.ops.commit.Commit(
            review_manager=self,
            msg=msg,
            manual_author=manual_author,
            script_name=script_call,
            saved_args=saved_args,
            realtime_override=realtime_override,
        )
        ret = commit.create()
        return ret

    def upgrade_colrev(self) -> None:
        import colrev.ops.upgrade

        colrev.ops.upgrade.Upgrade(review_manager=self)

    def get_advisor(self) -> colrev.advisor.Advisor:
        import colrev.advisor

        return colrev.advisor.Advisor(review_manager=self)

    def get_status_stats(self) -> colrev.ops.status.StatusStats:
        import colrev.ops.status

        return colrev.ops.status.StatusStats(review_manager=self)

    def get_completeness_condition(self) -> bool:
        status_stats = self.get_status_stats()
        return status_stats.completeness_condition

    @classmethod
    def get_local_index(cls, **kwargs) -> colrev.env.local_index.LocalIndex:
        import colrev.env.local_index

        return colrev.env.local_index.LocalIndex(**kwargs)

    @classmethod
    def get_package_manager(cls, **kwargs) -> colrev.env.package_manager.PackageManager:
        import colrev.env.package_manager

        return colrev.env.package_manager.PackageManager(**kwargs)

    @classmethod
    def get_grobid_service(cls, **kwargs) -> colrev.env.grobid_service.GrobidService:
        import colrev.env.grobid_service

        return colrev.env.grobid_service.GrobidService(**kwargs)

    def get_tei(self, **kwargs) -> colrev.env.tei_parser.TEIParser:
        import colrev.env.tei_parser

        return colrev.env.tei_parser.TEIParser(**kwargs)

    @classmethod
    def get_environment_manager(
        cls, **kwargs
    ) -> colrev.env.environment_manager.EnvironmentManager:
        import colrev.env.environment_manager

        return colrev.env.environment_manager.EnvironmentManager(**kwargs)

    @classmethod
    def get_cached_session(cls) -> requests_cache.CachedSession:

        return requests_cache.CachedSession(
            str(colrev.env.environment_manager.EnvironmentManager.cache_path),
            backend="sqlite",
            expire_after=timedelta(days=30),
        )

    @classmethod
    def get_zotero_translation_service(
        cls, **kwargs
    ) -> colrev.env.zotero_translation_service.ZoteroTranslationService:
        import colrev.env.zotero_translation_service

        return colrev.env.zotero_translation_service.ZoteroTranslationService(**kwargs)

    @classmethod
    def get_screenshot_service(
        cls, **kwargs
    ) -> colrev.env.screenshot_service.ScreenshotService:
        import colrev.env.screenshot_service

        return colrev.env.screenshot_service.ScreenshotService(**kwargs)

    @classmethod
    def get_pdf_hash_service(
        cls, **kwargs
    ) -> colrev.env.pdf_hash_service.PDFHashService:
        import colrev.env.pdf_hash_service

        return colrev.env.pdf_hash_service.PDFHashService(**kwargs)

    @classmethod
    def get_resources(cls, **kwargs) -> colrev.env.resources.Resources:
        import colrev.env.resources

        return colrev.env.resources.Resources(**kwargs)

    @classmethod
    def check_init_precondition(cls):
        import colrev.ops.init

        return colrev.ops.init.Initializer.check_init_precondition()

    @classmethod
    def get_init_operation(cls, **kwargs) -> colrev.ops.init.Initializer:
        import colrev.ops.init

        return colrev.ops.init.Initializer(**kwargs)

    @classmethod
    def get_sync_operation(cls, **kwargs) -> colrev.ops.sync.Sync:
        import colrev.ops.sync

        return colrev.ops.sync.Sync(**kwargs)

    @classmethod
    def get_clone_operation(cls, **kwargs) -> colrev.ops.clone.Clone:
        import colrev.ops.clone

        return colrev.ops.clone.Clone(**kwargs)

    def get_search_operation(self, **kwargs) -> colrev.ops.search.Search:
        import colrev.ops.search

        return colrev.ops.search.Search(review_manager=self, **kwargs)

    def get_load_operation(self, **kwargs) -> colrev.ops.load.Load:
        import colrev.ops.load

        return colrev.ops.load.Load(review_manager=self, **kwargs)

    def get_prep_operation(self, **kwargs) -> colrev.ops.prep.Prep:
        import colrev.ops.prep

        return colrev.ops.prep.Prep(review_manager=self, **kwargs)

    def get_prep_man_operation(self, **kwargs) -> colrev.ops.prep_man.PrepMan:
        import colrev.ops.prep_man

        return colrev.ops.prep_man.PrepMan(review_manager=self, **kwargs)

    def get_dedupe_operation(self, **kwargs) -> colrev.ops.dedupe.Dedupe:
        import colrev.ops.dedupe

        return colrev.ops.dedupe.Dedupe(review_manager=self, **kwargs)

    def get_prescreen_operation(self, **kwargs) -> colrev.ops.prescreen.Prescreen:
        import colrev.ops.prescreen

        return colrev.ops.prescreen.Prescreen(review_manager=self, **kwargs)

    def get_pdf_get_operation(self, **kwargs) -> colrev.ops.pdf_get.PDFGet:
        import colrev.ops.pdf_get

        return colrev.ops.pdf_get.PDFGet(review_manager=self, **kwargs)

    def get_pdf_get_man_operation(self, **kwargs) -> colrev.ops.pdf_get_man.PDFGetMan:
        import colrev.ops.pdf_get_man

        return colrev.ops.pdf_get_man.PDFGetMan(review_manager=self, **kwargs)

    def get_pdf_prep_operation(self, **kwargs) -> colrev.ops.pdf_prep.PDFPrep:
        import colrev.ops.pdf_prep

        return colrev.ops.pdf_prep.PDFPrep(review_manager=self, **kwargs)

    def get_pdf_prep_man_operation(
        self, **kwargs
    ) -> colrev.ops.pdf_prep_man.PDFPrepMan:
        import colrev.ops.pdf_prep_man

        return colrev.ops.pdf_prep_man.PDFPrepMan(review_manager=self, **kwargs)

    def get_screen_operation(self, **kwargs) -> colrev.ops.screen.Screen:
        import colrev.ops.screen

        return colrev.ops.screen.Screen(review_manager=self, **kwargs)

    def get_data_operation(self, **kwargs) -> colrev.ops.data.Data:
        import colrev.ops.data

        return colrev.ops.data.Data(review_manager=self, **kwargs)

    def get_status_operation(self, **kwargs) -> colrev.ops.status.Status:
        import colrev.ops.status

        return colrev.ops.status.Status(review_manager=self, **kwargs)

    def get_validate_operation(self, **kwargs) -> colrev.ops.validate.Validate:
        import colrev.ops.validate

        return colrev.ops.validate.Validate(review_manager=self, **kwargs)

    def get_trace_operation(self, **kwargs) -> colrev.ops.trace.Trace:
        import colrev.ops.trace

        return colrev.ops.trace.Trace(review_manager=self, **kwargs)

    def get_paper_operation(self, **kwargs) -> colrev.ops.paper.Paper:
        import colrev.ops.paper

        return colrev.ops.paper.Paper(review_manager=self, **kwargs)

    def get_distribute_operation(self, **kwargs) -> colrev.ops.distribute.Distribute:
        import colrev.ops.distribute

        return colrev.ops.distribute.Distribute(review_manager=self, **kwargs)

    def get_push_operation(self, **kwargs) -> colrev.ops.push.Push:
        import colrev.ops.push

        return colrev.ops.push.Push(review_manager=self, **kwargs)

    def get_pull_operation(self, **kwargs) -> colrev.ops.pull.Pull:
        import colrev.ops.pull

        return colrev.ops.pull.Pull(review_manager=self, **kwargs)

    def get_service_operation(self, **kwargs) -> colrev.service.Service:
        import colrev.service

        return colrev.service.Service(review_manager=self, **kwargs)

    def get_review_manager(self, **kwargs) -> ReviewManager:
        return type(self)(**kwargs)


if __name__ == "__main__":
    pass
