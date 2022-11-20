#!/usr/bin/env python3
"""Repair CoLRev projects."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import colrev.env.utils
import colrev.operation

if TYPE_CHECKING:
    import colrev.review_manager


# pylint: disable=too-few-public-methods


class Repair(colrev.operation.Operation):
    """Repair a CoLRev project"""

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

    def main(self) -> None:
        """Repair a CoLRev project (main entrypoint)"""

        self.review_manager.logger.warning("Repair is not fully implemented.")

        # Try: open settings, except: notify & start repair

        # Try: open records, except: notify & start repair

        with open(self.review_manager.dataset.records_file, encoding="utf-8") as file:
            record_str = ""
            line = file.readline()

            while line:
                if line == "\n":
                    records = self.review_manager.dataset.load_records_dict(
                        load_str=record_str
                    )
                    if len(records) != 1:
                        print(record_str)
                    record_str = ""
                record_str += line
                line = file.readline()

        # fix file no longer available
        try:
            records = self.review_manager.dataset.load_records_dict()
            for record in records.values():
                if "file" not in record:
                    continue
                full_path = self.review_manager.path / Path(record["file"])
                if full_path.is_file():
                    continue
                if Path(str(full_path) + ".pdf").is_file():
                    Path(str(full_path) + ".pdf").rename(full_path)

                # Check / replace multiple blanks in file and filename
                parent_dir = full_path.parent
                same_dir_pdfs = [
                    x.relative_to(self.review_manager.path)
                    for x in parent_dir.glob("*.pdf")
                ]
                for same_dir_pdf in same_dir_pdfs:
                    if record["file"].replace("  ", " ") == str(same_dir_pdf).replace(
                        "  ", " "
                    ):
                        same_dir_pdf.rename(str(same_dir_pdf).replace("  ", " "))
                        record["file"] = record["file"].replace("  ", " ")

                full_path = self.review_manager.path / Path(record["file"])
                if full_path.is_file():
                    continue

                record["colrev_status_backup"] = record["colrev_status"]
                del record["file"]
                record[
                    "colrev_status"
                ] = colrev.record.RecordState.rev_prescreen_included

        except AttributeError:
            print("Could not read bibtex file")

        self.review_manager.dataset.save_records_dict(records=records)


if __name__ == "__main__":
    pass
