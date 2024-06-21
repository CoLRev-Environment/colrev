#!/usr/bin/env python3
"""Merge branches of CoLRev projects."""
from __future__ import annotations

import copy

from dictdiffer import diff
from git.exc import GitCommandError

import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import OperationsType

# pylint: disable=too-few-public-methods


class Merge(colrev.process.operation.Operation):
    """Merge branches of CoLRev project"""

    type = OperationsType.check

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=False,
        )

    def _get_non_status_changes(
        self,
        *,
        current_branch_records: dict,
        other_branch_records: dict,
        current_branch_name: str,
        other_branch_name: str,
    ) -> list:
        non_status_changes = []

        records_missing_in_current_branch = [
            rid for rid in other_branch_records if rid not in current_branch_records
        ]
        if records_missing_in_current_branch:
            non_status_changes.append(
                {
                    f"records missing in {current_branch_name}": records_missing_in_current_branch
                }
            )

        records_missing_in_other_branch = [
            rid for rid in current_branch_records if rid not in other_branch_records
        ]
        if records_missing_in_other_branch:
            non_status_changes.append(
                {
                    f"records missing in {other_branch_name}:": records_missing_in_other_branch
                }
            )

        changed_records = []
        for current_record_id, current_record in current_branch_records.items():
            if current_record_id not in other_branch_records:
                continue
            other_record = other_branch_records[current_record_id]

            comparison_current_record = current_record.copy()
            del comparison_current_record[Fields.STATUS]
            comparison_other_record = other_record.copy()
            del comparison_other_record[Fields.STATUS]

            if comparison_current_record != comparison_other_record:
                comparison_diff = self.review_manager.p_printer.pformat(
                    list(diff(comparison_current_record, comparison_other_record))
                )
                changed_records.append(f"{current_record_id}: " f"{comparison_diff}")
        if changed_records:
            non_status_changes.append({"changed record fields:": changed_records})

        return non_status_changes

    @colrev.process.operation.Operation.decorate()
    def main(self, *, branch: str) -> None:
        """Merge branches of a CoLRev project (main entrypoint)"""

        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements

        git_repo = self.review_manager.dataset.get_repo()
        # our_index  = git_repo.index

        for remote in git_repo.remotes:
            remote.fetch()

        branches = git_repo.heads
        assert branch in [b.name for b in branches]

        git_branch = [b for b in branches if b.name == branch][0]
        merging_branch_author = git_branch.commit.author
        current_branch = git_repo.active_branch.name

        try:
            git_repo.git.merge(branch)
            self.review_manager.logger.info("Merged without conflicts.")
            return
        except GitCommandError:
            self.review_manager.logger.info("Detected changes in both branches.")

        unmerged_blobs = git_repo.index.unmerged_blobs()

        # Note : only two-way merges supported for now.
        assert all(len(v) == 3 for k, v in unmerged_blobs.items())

        # Ensure the path uses forward slashes, which is compatible with Git's path handling
        if self.review_manager.paths.RECORDS_FILE_GIT in unmerged_blobs:
            current_branch_records = {}
            other_branch_records = {}
            for stage, blob in unmerged_blobs[
                self.review_manager.paths.RECORDS_FILE_GIT
            ]:
                # stage == 1: common ancestor (often md_processed for prescreen)
                # stage == 2: own branch
                # stage == 3: other branch
                if 2 == stage:

                    current_branch_records = colrev.loader.load_utils.loads(
                        load_string=blob.data_stream.read().decode("utf-8"),
                        implementation="bib",
                        logger=self.review_manager.logger,
                    )

                elif 3 == stage:
                    other_branch_records = colrev.loader.load_utils.loads(
                        load_string=blob.data_stream.read().decode("utf-8"),
                        implementation="bib",
                        logger=self.review_manager.logger,
                    )

        else:
            self.review_manager.logger.info(
                f"No conflicts to reconcile in {self.review_manager.paths.records}."
            )
            return

        # There may be removed records / renamed IDs, changed fields...
        # if so: print, ask to resolve and exit
        non_status_changes = self._get_non_status_changes(
            current_branch_records=current_branch_records,
            other_branch_records=other_branch_records,
            current_branch_name=current_branch,
            other_branch_name=branch,
        )
        if non_status_changes:
            print(
                "Resolve non-status changes before merging "
                "(abort merge using git merge --abort):"
            )
            print(non_status_changes)
            return

        self.review_manager.logger.info("Reconciling changes in colrev_status.")
        # Note : reconciliation of other changes not supported yet

        (
            current_branch_author,
            _,
        ) = self.review_manager.environment_manager.get_name_mail_from_git()

        self.review_manager.logger.info(
            "Start merge reconciliation: "
            f"branch {current_branch} ({current_branch_author}) <-> "
            f"branch {branch} ({merging_branch_author})"
        )

        # Copy: for statistics
        current_branch_records_prior = copy.deepcopy(current_branch_records)

        print()
        nr_to_reconcile = len(
            [
                r
                for r in current_branch_records.values()
                if other_branch_records[r[Fields.ID]][Fields.STATUS] != r[Fields.STATUS]
            ]
        )
        i = 0
        for (
            current_branch_record_id,
            current_branch_record_dict,
        ) in current_branch_records.items():
            other_branch_record = other_branch_records[current_branch_record_id]

            if (
                current_branch_record_dict[Fields.STATUS]
                != other_branch_record[Fields.STATUS]
            ):
                i += 1
                print(f"{i}/{nr_to_reconcile}")
                copied_rec = current_branch_record_dict.copy()
                copied_rec.pop(Fields.STATUS)
                print(colrev.record.record.Record(copied_rec).format_bib_style())
                print(
                    f"1 - {current_branch_author} coded on {current_branch}".ljust(
                        40, " "
                    )
                    + f": {current_branch_record_dict['colrev_status']}"
                )
                print(
                    f"2 - {merging_branch_author} coded on {branch}".ljust(40, " ")
                    + f": {other_branch_record['colrev_status']}"
                )
                resolution_nr = input("Enter resolution: (1 or 2)")
                if resolution_nr == "1":
                    self.review_manager.report_logger.info(
                        f"Reconciliation for {current_branch_record_id}: "
                        f"{current_branch_record_dict['colrev_status']}"
                    )
                    resolution = current_branch_record_dict[Fields.STATUS]
                else:
                    self.review_manager.report_logger.info(
                        f"Reconciliation for {current_branch_record_id}: "
                        f"{other_branch_record['colrev_status']}"
                    )
                    resolution = other_branch_record[Fields.STATUS]
                current_branch_record = colrev.record.record.Record(
                    current_branch_record_dict
                )
                current_branch_record.set_status(resolution)
                print("\n\n\n")

        self.review_manager.dataset.save_records_dict(current_branch_records)

        self.review_manager.update_status_yaml(add_to_git=False)

        validate_operation = self.review_manager.get_validate_operation()
        validation_details = validate_operation.validate_merge_prescreen_screen(
            current_branch_records=current_branch_records_prior,
            other_branch_records=other_branch_records,
            records_reconciled=current_branch_records,
        )
        print("Statistics:")
        self.review_manager.p_printer.pprint(validation_details["statistics"])

        print(
            f"\n{Colors.ORANGE}Please add (git add .) and commit (git commit){Colors.END}"
        )

        # Note : cannot add/create commit yet - not yet supported by gitpython:
        # https://github.com/gitpython-developers/GitPython/issues/1185
        # our_index.write(ignore_extension_data=True)
