#! /usr/bin/env python
"""CoLRev debug prep operation."""
from __future__ import annotations

import logging
import time
import typing
from multiprocessing import Value

from requests.exceptions import ConnectionError as requests_ConnectionError

import colrev.exceptions as colrev_exceptions
import colrev.ops.prep
import colrev.process.operation
import colrev.record.record_prep
from colrev.constants import Colors
from colrev.constants import Fields

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.package_manager.package_base_classes as base_classes
    import colrev.review_manager

# logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("requests_cache").setLevel(logging.ERROR)

PREP_COUNTER = Value("i", 0)


# pylint: disable=too-many-instance-attributes
class PrepDebug(colrev.ops.prep.Prep):
    """Debug prepare records (metadata)"""

    debug_ids: typing.List[str]
    commit_sha: str

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool,
        polish: bool,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            notify_state_transition_operation=notify_state_transition_operation,
            polish=polish,
            cpu=1,
        )

    # Overrides parent method
    def _print_diffs_for_debug(
        self,
        *,
        prior: colrev.record.record_prep.PrepRecord,
        preparation_record: colrev.record.record_prep.PrepRecord,
        prep_package_endpoint: base_classes.PrepPackageBaseClass,
    ) -> None:

        diffs = prior.get_diff(preparation_record)

        if diffs:
            change_report = (
                f"{prep_package_endpoint} changed:\n"
                f"{Colors.ORANGE}{self.review_manager.p_printer.pformat(diffs)}{Colors.END}\n"
            )

            self.review_manager.logger.info(change_report)
            self.review_manager.logger.info(
                "To correct errors in the endpoint,"
                " open an issue at "
                "https://github.com/CoLRev-Environment/colrev/issues"
            )
            self.review_manager.logger.info(
                "To correct potential errors at source,"
                f" {prep_package_endpoint.source_correction_hint}"
            )
        else:
            self.review_manager.logger.info(f"{prep_package_endpoint} changed: -")
            time.sleep(0.1)
        print("\n")

    def _retrieve_records_from_history(self, original_records: list[dict]) -> list:
        git_repo = self.review_manager.dataset.get_repo()

        if self.commit_sha == "":
            self.commit_sha = git_repo.git.rev_parse("HEAD")

        # get the commit_sha preceding commit_sha
        preceding_commit_sha = git_repo.git.rev_parse(self.commit_sha + "^")

        prior_records = next(
            self.review_manager.dataset.load_records_from_history(
                commit_sha=preceding_commit_sha
            )
        )

        original_records_ids = [r["ID"] for r in original_records]
        return [r for r in prior_records.values() if r["ID"] in original_records_ids]

    def _load_temp_prep_to_resume(self, prepare_data: dict) -> None:
        pass

    # overrides _load_prep_data
    def _load_prep_data(self) -> dict:

        records = []
        original_records = list(
            self.review_manager.dataset.read_next_record(
                conditions=[{Fields.ID: ID} for ID in self.debug_ids]
            )
        )
        records = self._retrieve_records_from_history(original_records)
        if len(records) == 0:
            prep_data = {"nr_tasks": 0, "PAD": 0, "items": []}
        else:
            prep_data = {
                "nr_tasks": len(self.debug_ids),
                "PAD": len(self.debug_ids),
                "items": records,
            }
        return prep_data

    @colrev.process.operation.Operation.decorate()
    def run_debug(self, *, debug_ids: str = "NA") -> None:
        """Preparation of records (main entrypoint)"""

        self.debug_ids = debug_ids.split(",")

        self.review_manager.logger.info("Start debug prep")
        self.review_manager.logger.info(
            "The debugger will replay the preparation procedures"
            " step-by-step, allow you to identify potential errors, trace them to "
            "their colrev_origin and correct them."
        )

        self.polish = input("Polish mode (y/n)?") == "y"
        self.commit_sha = input(
            "Commit in which the error occurred (press Enter to select the most recent commit):"
        )

        try:
            for i, prep_round in enumerate(
                self.review_manager.settings.prep.prep_rounds
            ):
                self._setup_prep_round(i=i, prep_round=prep_round)
                preparation_data = self._get_prep_data_tasks(prep_round)

                if len(preparation_data) == 0 and not self.temp_records.is_file():
                    self.review_manager.logger.info("No records to prepare.")
                    print()
                    return
                self.review_manager.logger.info("Loaded data. Start preparation.")
                for item in preparation_data:
                    record = self.prepare(item)
                    self.review_manager.logger.info(
                        f"Result:\n" f"{self.review_manager.p_printer.pformat(record)}"
                    )
        except requests_ConnectionError as exc:
            if "OSError(24, 'Too many open files" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Too many files opened (OSError, Errno24). "
                    "To use a smaller number of parallel processes, run colrev prep --cpu 1"
                ) from exc
            raise exc

        except OSError as exc:
            if 24 == exc.errno:
                raise colrev_exceptions.ServiceNotAvailableException(
                    "Too many files opened (OSError, Errno24). "
                    "To use a smaller number of parallel processes, run colrev prep --cpu 1"
                ) from exc
            raise exc
