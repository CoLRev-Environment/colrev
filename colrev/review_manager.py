#!/usr/bin/env python3
"""The CoLRev review manager (main entrypoint)."""
from __future__ import annotations

import logging
import os
import pprint
import typing
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import git
import requests_cache
import yaml

import colrev.dataset
import colrev.exceptions as colrev_exceptions
import colrev.logger
import colrev.ops.check
import colrev.ops.checker
import colrev.process.operation
import colrev.record.qm.quality_model
import colrev.settings
from colrev.constants import Colors
from colrev.constants import Filepaths
from colrev.constants import OperationsType
from colrev.paths import PathManager


class ReviewManager:
    """Class for managing individual CoLRev review project (repositories)"""

    # pylint: disable=import-outside-toplevel
    # pylint: disable=redefined-outer-name
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-many-public-methods
    # pylint: disable=too-many-arguments

    notified_next_operation = None
    """ReviewManager was notified for the upcoming process and
    will provide access to the Dataset"""

    dataset: colrev.dataset.Dataset
    """The review dataset object"""

    path: Path
    """Path of the project repository"""

    shell_mode = False

    def __init__(
        self,
        *,
        path_str: typing.Optional[str] = None,
        force_mode: bool = False,
        verbose_mode: bool = False,
        high_level_operation: bool = False,
        navigate_to_home_dir: bool = True,
        exact_call: str = "",
        skip_upgrade: bool = True,
    ) -> None:
        self.force_mode = force_mode
        """Force mode variable (bool)"""
        self.verbose_mode = verbose_mode
        """Verbose mode variable (bool)"""
        self.high_level_operation = high_level_operation
        """A high-level operation was called (bool)"""
        # Note : mostly for formatting output

        if navigate_to_home_dir:
            self.path = self._get_project_home_dir(path_str=path_str)
        else:
            self.path = Path.cwd()

        self.paths = PathManager(self.path)

        self.exact_call = exact_call

        try:
            if self.paths.settings.is_file():
                self.paths.data.mkdir(parents=True, exist_ok=True)
                self.paths.search.mkdir(parents=True, exist_ok=True)
                self.paths.pdf.mkdir(parents=True, exist_ok=True)
                self.paths.output.mkdir(parents=True, exist_ok=True)

            report_logger, logger = self.get_loggers()
            self.report_logger = report_logger
            self.logger = logger

            self.environment_manager = self.get_environment_manager()

            self.p_printer = pprint.PrettyPrinter(indent=4, width=140, compact=False)
            # run update before settings/data (which may require changes/fail without update)
            if not skip_upgrade:  # pragma: no cover
                self._check_update()
            self.settings = self.load_settings()
            self.dataset = colrev.dataset.Dataset(review_manager=self)

        except Exception as exc:  # pylint: disable=broad-except

            if (self.path / Path(".git")).is_dir():
                if git.Repo().active_branch.name == "gh-pages":  # pragma: no cover
                    raise colrev_exceptions.RepoSetupError(
                        msg="Currently on gh-pages branch. Switch to main: "
                        + f"{Colors.ORANGE}git switch main{Colors.END}"
                    )

            if not force_mode:
                raise exc

    # pylint: disable=too-many-arguments
    def update_config(
        self,
        *,
        force_mode: bool = False,
        verbose_mode: bool = False,
        high_level_operation: bool = False,
        exact_call: str = "",
    ) -> None:
        """Update review_manager's state"""
        self.force_mode = force_mode
        self.verbose_mode = verbose_mode
        self.high_level_operation = high_level_operation
        self.exact_call = exact_call
        report_logger, logger = self.get_loggers()
        self.report_logger = report_logger
        self.logger = logger

    def get_loggers(self) -> typing.Tuple[logging.Logger, logging.Logger]:
        """return loggers"""
        if self.verbose_mode:
            return colrev.logger.setup_report_logger(
                review_manager=self, level=logging.DEBUG
            ), colrev.logger.setup_logger(review_manager=self, level=logging.DEBUG)
        return colrev.logger.setup_report_logger(
            review_manager=self, level=logging.INFO
        ), colrev.logger.setup_logger(review_manager=self, level=logging.INFO)

    def _check_update(self) -> None:
        # Once the following has run for all repositories,
        # it should only be called when the versions differ.
        # last_version, current_version = self.get_colrev_versions()
        # if last_version != current_version:
        upgrade_operation = self.get_upgrade()
        upgrade_operation.main()

    def get_committer(self) -> typing.Tuple[str, str]:
        """Get the committer name and email"""
        return self.environment_manager.get_name_mail_from_git()

    def _get_project_home_dir(self, *, path_str: typing.Optional[str] = None) -> Path:
        if path_str:
            original_dir = Path(path_str)
        else:
            original_dir = Path.cwd()

        while ".git" not in [f.name for f in original_dir.iterdir() if f.is_dir()]:
            if original_dir.parent == original_dir:  # reached root
                break
            original_dir = original_dir.parent

        if original_dir.parent == original_dir:  # reached root
            raise colrev.exceptions.RepoSetupError(
                "Failed to locate a .git directory. "
                "Ensure you are within a Git repository, "
                "or set navigate_to_home_dir=False for init."
            )

        return original_dir

    def load_settings(self) -> colrev.settings.Settings:
        """Load the settings"""
        self.settings = colrev.settings.load_settings(settings_path=self.paths.settings)
        return self.settings

    def save_settings(self) -> None:
        """Save the settings"""
        colrev.settings.save_settings(review_manager=self)

    def reset_report_logger(self) -> None:
        """Reset the report logger"""
        colrev.logger.reset_report_logger(review_manager=self)

    def check_repo(self) -> dict:
        """Check the repository"""
        checker = colrev.ops.checker.Checker(review_manager=self)
        return checker.check_repo()

    def in_virtualenv(self) -> bool:  # pragma: no cover
        """Check whether CoLRev operates in a virtual environment"""
        return colrev.ops.checker.Checker.in_virtualenv()

    def check_repository_setup(self) -> None:
        """Check the repository setup"""
        checker = colrev.ops.checker.Checker(review_manager=self)
        checker.check_repository_setup()

    def get_colrev_versions(self) -> list[str]:
        """Get the CoLRev versions"""
        checker = colrev.ops.checker.Checker(review_manager=self)
        return checker.get_colrev_versions()

    def report(self, *, msg_file: Path) -> None:
        """Append commit-message report if not already available
        (Entrypoint for pre-commit hooks)
        """
        import colrev.ops.commit
        import colrev.ops.correct

        with open(msg_file, encoding="utf8") as file:
            available_contents = file.read()

        with open(msg_file, "w", encoding="utf8") as file:
            file.write(available_contents)
            # Don't append if it's already there
            # update = False
            # if "Command" not in available_contents:
            #     update = True
            # if "Properties" in available_contents:
            #     update = False
            # if update:
            commit = colrev.ops.commit.Commit(
                review_manager=self,
                msg=available_contents,
                manual_author=True,
                script_name="MANUAL",
            )
            commit.update_report(msg_file=msg_file)

        if (
            not self.settings.is_curated_masterdata_repo()
            and self.dataset.records_changed()
        ):  # pragma: no cover
            colrev.ops.check.CheckOperation(self)  # to notify
            corrections_operation = colrev.ops.correct.Corrections(review_manager=self)
            corrections_operation.check_corrections_of_records()

    def sharing(self) -> dict:
        """Check whether sharing requirements are met
        (Entrypoint for pre-commit hooks)
        """

        self.notified_next_operation = OperationsType.check
        advisor = self.get_advisor()
        sharing_advice = advisor.get_sharing_instructions()
        return sharing_advice

    def update_status_yaml(
        self, *, add_to_git: bool = True, records: typing.Optional[dict] = None
    ) -> None:
        """Update the STATUS_FILE"""

        status_stats = self.get_status_stats(records=records)
        exported_dict = asdict(status_stats)
        with open(self.paths.status, "w", encoding="utf8") as file:
            yaml.dump(exported_dict, file, allow_unicode=True)
        if add_to_git:
            self.dataset.add_changes(self.paths.STATUS_FILE)

    def get_upgrade(self) -> colrev.ops.upgrade.Upgrade:  # pragma: no cover
        """Get an upgrade object"""

        import colrev.ops.upgrade

        return colrev.ops.upgrade.Upgrade(review_manager=self)

    def get_repare(self) -> colrev.ops.repare.Repare:  # pragma: no cover
        """Get a a repare object"""

        import colrev.ops.repare

        return colrev.ops.repare.Repare(review_manager=self)

    def get_remove_operation(self) -> colrev.ops.remove.Remove:  # pragma: no cover
        """Get a a remove object"""

        import colrev.ops.remove

        return colrev.ops.remove.Remove(review_manager=self)

    def get_merge_operation(self) -> colrev.ops.merge.Merge:  # pragma: no cover
        """Get a merge object"""

        import colrev.ops.merge

        return colrev.ops.merge.Merge(review_manager=self)

    def get_advisor(self) -> colrev.ops.advisor.Advisor:  # pragma: no cover
        """Get an advisor object"""

        import colrev.ops.advisor

        return colrev.ops.advisor.Advisor(review_manager=self)

    def get_checker(self) -> colrev.ops.checker.Checker:  # pragma: no cover
        """Get a checker object"""

        return colrev.ops.checker.Checker(review_manager=self)

    def get_qm(self) -> colrev.record.qm.quality_model.QualityModel:  # pragma: no cover
        """Get the quality model"""

        return colrev.record.qm.quality_model.QualityModel(
            defects_to_ignore=self.settings.prep.defects_to_ignore
        )

    def get_pdf_qm(
        self,
    ) -> colrev.record.qm.quality_model.QualityModel:  # pragma: no cover
        """Get the PDF quality model"""

        return colrev.record.qm.quality_model.QualityModel(
            defects_to_ignore=self.settings.pdf_get.defects_to_ignore, pdf_mode=True
        )

    def get_status_stats(
        self, *, records: typing.Optional[dict] = None
    ) -> colrev.process.status.StatusStats:  # pragma: no cover
        """Get a status stats object"""

        import colrev.process.status

        colrev.ops.check.CheckOperation(self)

        if records is None:
            records = self.dataset.load_records_dict()
        return colrev.process.status.StatusStats(review_manager=self, records=records)

    def get_completeness_condition(self) -> bool:
        """Get the completeness condition"""
        status_stats = self.get_status_stats()
        return status_stats.completeness_condition

    @classmethod
    def get_package_manager(
        cls,
    ) -> colrev.package_manager.package_manager.PackageManager:  # pragma: no cover
        """Get a package manager object"""

        import colrev.package_manager.package_manager

        return colrev.package_manager.package_manager.PackageManager()

    @classmethod
    def get_grobid_service(
        cls,
    ) -> colrev.env.grobid_service.GrobidService:  # pragma: no cover
        """Get a grobid service object"""
        import colrev.env.grobid_service

        environment_manager = cls.get_environment_manager()
        return colrev.env.grobid_service.GrobidService(
            environment_manager=environment_manager
        )

    def get_tei(
        self,
        *,
        pdf_path: typing.Optional[Path] = None,
        tei_path: typing.Optional[Path] = None,
    ) -> colrev.env.tei_parser.TEIParser:  # type: ignore # pragma: no cover
        """Get a tei object"""

        import colrev.env.tei_parser

        return colrev.env.tei_parser.TEIParser(
            environment_manager=self.environment_manager,
            pdf_path=self.path / pdf_path if pdf_path else None,
            tei_path=self.path / tei_path if tei_path else None,
        )

    @classmethod
    def get_environment_manager(
        cls,
    ) -> colrev.env.environment_manager.EnvironmentManager:  # pragma: no cover
        """Get an environment manager"""
        import colrev.env.environment_manager

        return colrev.env.environment_manager.EnvironmentManager()

    @classmethod
    def get_cached_session(cls) -> requests_cache.CachedSession:  # pragma: no cover
        """Get a cached session"""

        return requests_cache.CachedSession(
            str(Filepaths.PREP_REQUESTS_CACHE_FILE),
            backend="sqlite",
            expire_after=timedelta(days=30),
        )

    @classmethod
    def get_resources(cls) -> colrev.env.resources.Resources:  # pragma: no cover
        """Get a resources object"""
        import colrev.env.resources

        return colrev.env.resources.Resources()

    def get_search_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.search.Search:  # pragma: no cover
        """Get a search operation object"""
        import colrev.ops.search

        return colrev.ops.search.Search(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_load_operation(
        self,
        notify_state_transition_operation: bool = True,
        hide_load_explanation: bool = False,
    ) -> colrev.ops.load.Load:  # pragma: no cover
        """Get a load operation object"""
        import colrev.ops.load

        return colrev.ops.load.Load(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
            hide_load_explanation=hide_load_explanation,
        )

    def get_prep_operation(
        self,
        *,
        notify_state_transition_operation: bool = True,
        polish: bool = False,
        cpu: int = 4,
        debug: bool = False,
    ) -> colrev.ops.prep.Prep:  # pragma: no cover
        """Get a prep operation object"""
        if debug:
            import colrev.ops.prep_debug

            return colrev.ops.prep_debug.PrepDebug(
                review_manager=self,
                notify_state_transition_operation=notify_state_transition_operation,
                polish=polish,
            )

        import colrev.ops.prep

        return colrev.ops.prep.Prep(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
            polish=polish,
            cpu=cpu,
        )

    def get_prep_man_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.prep_man.PrepMan:  # pragma: no cover
        """Get a prep-man operation object"""
        import colrev.ops.prep_man

        return colrev.ops.prep_man.PrepMan(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_dedupe_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.dedupe.Dedupe:  # pragma: no cover
        """Get a dedupe operation object"""
        import colrev.ops.dedupe

        return colrev.ops.dedupe.Dedupe(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_prescreen_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.prescreen.Prescreen:  # pragma: no cover
        """Get a prescreen operation object"""

        import colrev.ops.prescreen

        return colrev.ops.prescreen.Prescreen(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_pdf_get_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.pdf_get.PDFGet:  # pragma: no cover
        """Get a pdf-get operation object"""
        import colrev.ops.pdf_get

        return colrev.ops.pdf_get.PDFGet(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_pdf_get_man_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.pdf_get_man.PDFGetMan:  # pragma: no cover
        """Get a pdf-get-man operation object"""
        import colrev.ops.pdf_get_man

        return colrev.ops.pdf_get_man.PDFGetMan(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_pdf_prep_operation(
        self, *, reprocess: bool = False, notify_state_transition_operation: bool = True
    ) -> colrev.ops.pdf_prep.PDFPrep:  # pragma: no cover
        """Get a pdfprep operation object"""
        import colrev.ops.pdf_prep

        return colrev.ops.pdf_prep.PDFPrep(
            review_manager=self,
            reprocess=reprocess,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_pdf_prep_man_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.pdf_prep_man.PDFPrepMan:  # pragma: no cover
        """Get a pdf-prep-man operation object"""
        import colrev.ops.pdf_prep_man

        return colrev.ops.pdf_prep_man.PDFPrepMan(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_screen_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.screen.Screen:  # pragma: no cover
        """Get a screen operation object"""
        import colrev.ops.screen

        return colrev.ops.screen.Screen(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_data_operation(
        self, *, notify_state_transition_operation: bool = True
    ) -> colrev.ops.data.Data:  # pragma: no cover
        """Get a data operation object"""
        import colrev.ops.data

        return colrev.ops.data.Data(
            review_manager=self,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_status_operation(self) -> colrev.ops.status.Status:  # pragma: no cover
        """Get a status operation object"""

        import colrev.ops.status

        return colrev.ops.status.Status(review_manager=self)

    def get_validate_operation(
        self,
    ) -> colrev.ops.validate.Validate:  # pragma: no cover
        """Get a validate operation object"""
        import colrev.ops.validate

        return colrev.ops.validate.Validate(review_manager=self)

    def get_trace_operation(self) -> colrev.ops.trace.Trace:  # pragma: no cover
        """Get a trace operation object"""
        import colrev.ops.trace

        return colrev.ops.trace.Trace(review_manager=self)

    def get_distribute_operation(
        self,
    ) -> colrev.ops.distribute.Distribute:  # pragma: no cover
        """Get a distribute operation object"""

        import colrev.ops.distribute

        return colrev.ops.distribute.Distribute(review_manager=self)

    # pylint: disable=line-too-long
    def get_push_operation(self, **kwargs) -> colrev.ops.push.Push:  # type: ignore # pragma: no cover
        """Get a push operation object"""

        import colrev.ops.push

        return colrev.ops.push.Push(review_manager=self, **kwargs)

    def get_pull_operation(self) -> colrev.ops.pull.Pull:  # pragma: no cover
        """Get a pull operation object"""

        import colrev.ops.pull

        return colrev.ops.pull.Pull(review_manager=self)

    def get_connecting_review_manager(
        self,
        *,
        path_str: typing.Optional[str] = None,
        force_mode: bool = False,
        verbose_mode: bool = False,
    ) -> ReviewManager:  # pragma: no cover
        """Get a (connecting) ReviewManager object for another CoLRev repository"""
        return type(self)(
            path_str=path_str, force_mode=force_mode, verbose_mode=verbose_mode
        )

    @classmethod
    def in_test_environment(cls) -> bool:
        """Check whether CoLRev runs in a test environment"""

        return "pytest" in os.getcwd()

    @classmethod
    def in_ci_environment(
        cls,
    ) -> bool:
        """Check whether CoLRev runs in a continuous-integration environment"""

        identifier_list = [
            "GITHUB_ACTIONS",
            "CIRCLECI",
            "TRAVIS",
            "GITLAB_CI",
        ]
        return any("true" == os.getenv(x) for x in identifier_list)
