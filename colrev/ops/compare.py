#!/usr/bin/env python3
"""Compare CoLRev projects."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation

if TYPE_CHECKING:
    import colrev.review_manager


# pylint: disable=too-few-public-methods


class Compare(colrev.operation.Operation):
    """Compare a CoLRev project"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
            notify_state_transition_operation=False,
        )

    def main(self, *, path: str) -> None:
        """Compare a CoLRev project (main entrypoint)"""

        # pylint: disable=too-many-branches

        self.review_manager.logger.warning("Compare is not fully implemented.")

        other_records = {}
        try:
            other_review_manager = colrev.review_manager.ReviewManager(path_str=path)

            colrev.operation.CheckOperation(review_manager=other_review_manager)
            other_records = other_review_manager.dataset.load_records_dict()
        except colrev_exceptions.CoLRevException:
            # Use the references.bib if path is not a CoLRev project
            references_bib = Path(path) / Path("references.bib")

            if not references_bib.is_file():
                return

            with open(references_bib, encoding="utf8") as target_db:
                other_records = self.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )
                for other_record in other_records.values():
                    other_record[
                        "colrev_status"
                    ] = colrev.record.RecordState.rev_synthesized

            if references_bib.is_file():
                with open(references_bib, encoding="utf8") as target_db:
                    other_records = self.review_manager.dataset.load_records_dict(
                        load_str=target_db.read()
                    )
                    for other_record in other_records.values():
                        other_record[
                            "colrev_status"
                        ] = colrev.record.RecordState.rev_synthesized
            else:
                return

        current_only = str(self.review_manager.path.name)
        other_only = str(Path(path).name)

        venn_stats: dict = {current_only: [], "both": [], other_only: []}

        included_states = [
            colrev.record.RecordState.rev_included,
            colrev.record.RecordState.rev_synthesized,
        ]

        # TODO : matching based on IDs is too simple!!
        # TODO : check/test the colrev_status conditions!
        # Vision: find LRs that have the highest sample overlap (to check/update)
        # Could also be applied to non-LRs?! / with "central" papers?!

        records = self.review_manager.dataset.load_records_dict()
        for record_id, record_dict in records.items():
            if record_dict["colrev_status"] not in included_states:
                continue

            if record_id in other_records:
                if other_records[record_id]["colrev_status"] in included_states:
                    venn_stats["both"].append(record_id)
            else:
                venn_stats[current_only].append(record_id)

        for record_id, record_dict in other_records.items():
            if record_dict["colrev_status"] not in included_states:
                continue

            if record_id not in records:
                venn_stats[other_only].append(record_id)

            elif records[record_id]["colrev_status"] not in included_states:
                venn_stats[other_only].append(record_id)

        print(
            f"only in {current_only}".ljust(30, " ")
            + f": {len(venn_stats[current_only])}"
        )
        print("in both ".ljust(30, " ") + f": {len(venn_stats['both'])}")
        print(
            f"only in {other_only} ".ljust(30, " ") + f": {len(venn_stats[other_only])}"
        )

        if self.review_manager.verbose_mode:
            print(venn_stats["both"])


if __name__ == "__main__":
    pass
