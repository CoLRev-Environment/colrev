#!/usr/bin/env python3
"""The CoLRev review manager (main entrypoint)."""
from __future__ import annotations

import logging
import pprint
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

import requests_cache
import yaml

import colrev.checker
import colrev.dataset
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.logger
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
    REPORT_RELATIVE = Path(".report.log")
    CORRECTIONS_PATH_RELATIVE = Path(".corrections")
    PDF_DIR_RELATIVE = Path("data/pdfs")
    SEARCHDIR_RELATIVE = Path("data/search")
    README_RELATIVE = Path("readme.md")
    STATUS_RELATIVE = Path("status.yaml")
    OUTPUT_DIR_RELATIVE = Path("output")
    DATA_DIR_RELATIVE = Path("data")

    dataset: colrev.dataset.Dataset
    """The review dataset object"""

    path: Path
    """Path of the project repository"""

    def __init__(
        self,
        *,
        path_str: str = None,
        force_mode: bool = False,
        debug_mode: bool = False,
    ) -> None:

        self.force_mode = force_mode
        """Force mode variable (bool)"""

        self.path = Path(path_str) if path_str is not None else Path.cwd()

        self.settings_path = self.path / self.SETTINGS_RELATIVE
        self.report_path = self.path / self.REPORT_RELATIVE
        self.corrections_path = self.path / self.CORRECTIONS_PATH_RELATIVE
        self.pdf_dir = self.path / self.PDF_DIR_RELATIVE
        self.search_dir = self.path / self.SEARCHDIR_RELATIVE
        self.readme = self.path / self.README_RELATIVE
        self.status = self.path / self.STATUS_RELATIVE
        self.output_dir = self.path / self.OUTPUT_DIR_RELATIVE
        self.data_dir = self.path / self.DATA_DIR_RELATIVE

        self.data_dir.mkdir(exist_ok=True)
        self.search_dir.mkdir(exist_ok=True)
        self.pdf_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        self.debug_mode = debug_mode

        # Start LocalIndex to prevent waiting times
        self.get_local_index(startup_without_waiting=True)

        try:
            if self.debug_mode:
                self.report_logger = colrev.logger.setup_report_logger(
                    review_manager=self, level=logging.DEBUG
                )
                """Logger for the commit report"""
                self.logger = colrev.logger.setup_logger(
                    review_manager=self, level=logging.DEBUG
                )
                """Logger for processing information"""
            else:
                self.report_logger = colrev.logger.setup_report_logger(
                    review_manager=self, level=logging.INFO
                )
                self.logger = colrev.logger.setup_logger(
                    review_manager=self, level=logging.INFO
                )

            environment_manager = self.get_environment_manager()
            self.committer, self.email = environment_manager.get_name_mail_from_git()

            self.p_printer = pprint.PrettyPrinter(indent=4, width=140, compact=False)
            self.dataset = colrev.dataset.Dataset(review_manager=self)
            self.settings = self.load_settings()

        except Exception as exc:  # pylint: disable=broad-except
            if force_mode:
                self.logger.debug(exc)
            else:
                raise exc

        if self.debug_mode:
            print("\n\n")
            self.logger.debug("Created review manager instance")
            self.logger.debug("Settings:\n%s", self.settings)

    def load_settings(self) -> colrev.settings.Settings:
        return colrev.settings.load_settings(review_manager=self)

    def save_settings(self) -> None:
        colrev.settings.save_settings(review_manager=self)

    def reset_log(self) -> None:
        colrev.logger.reset_log(review_manager=self)

    def check_repo(self) -> dict:
        checker = colrev.checker.Checker(review_manager=self)
        return checker.check_repo()

    def in_virtualenv(self) -> bool:
        checker = colrev.checker.Checker(review_manager=self)
        return checker.in_virtualenv()

    def check_repository_setup(self) -> None:
        checker = colrev.checker.Checker(review_manager=self)
        checker.check_repository_setup()

    def get_colrev_versions(self) -> list[str]:
        checker = colrev.checker.Checker(review_manager=self)
        return checker.get_colrev_versions()

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
                commit.update_report(msg_file=msg_file)

        colrev.process.CheckProcess(review_manager=self)  # to notify
        corrections_operation = colrev.ops.correct.Corrections(review_manager=self)
        corrections_operation.check_corrections_of_curated_records()

        return {"msg": "TODO", "status": 0}

    def sharing(self) -> dict:
        """Check whether sharing requirements are met
        Entrypoint for pre-commit hooks)
        """

        self.notified_next_process = colrev.process.ProcessType.check
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

        try:
            if state_transition:
                process.check_precondition()
            self.notified_next_process = process.type
            self.dataset.reset_log_if_no_changes()
        except AttributeError as exc:
            if self.force_mode:
                pass
            else:
                raise exc

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

    def get_upgrade(self) -> colrev.ops.upgrade.Upgrade:
        import colrev.ops.upgrade

        return colrev.ops.upgrade.Upgrade(review_manager=self)

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

    def get_search_sources(self, **kwargs) -> colrev.ops.search_sources.SearchSources:
        import colrev.ops.search_sources

        return colrev.ops.search_sources.SearchSources(review_manager=self, **kwargs)

    def get_review_types(self, **kwargs) -> colrev.ops.review_types.ReviewTypes:
        import colrev.ops.review_types

        return colrev.ops.review_types.ReviewTypes(review_manager=self, **kwargs)

    def get_review_manager(self, **kwargs) -> ReviewManager:
        return type(self)(**kwargs)


if __name__ == "__main__":
    pass
