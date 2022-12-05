#!/usr/bin/env python3
"""Repare CoLRev projects."""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.operation

if TYPE_CHECKING:
    import colrev.review_manager


# pylint: disable=too-few-public-methods


class Repare(colrev.operation.Operation):
    """Repare a CoLRev project"""

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
        """Repare a CoLRev project (main entrypoint)"""

        # pylint: disable=too-many-nested-blocks
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements

        self.review_manager.logger.warning("Repare is not fully implemented.")

        # Try: open settings, except: notify & start Repare

        # Try: open records, except: notify & start Repare

        separated_records = {}  # type: ignore
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
                    else:
                        separated_records = {**separated_records, **records}
                    record_str = ""
                record_str += line
                line = file.readline()
        self.review_manager.dataset.save_records_dict_to_file(
            records=separated_records, save_path=Path("extracted.bib")
        )

        # TODO : save backup of records before?
        # This may remove contents if the records file is broken...
        # fix file no longer available
        try:
            local_index = self.review_manager.get_local_index()
            pdf_get_operation = self.review_manager.get_pdf_get_operation()

            records = self.review_manager.dataset.load_records_dict()
            for record_dict in records.values():
                if "file" not in record_dict:
                    continue
                full_path = self.review_manager.path / Path(record_dict["file"])

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
                    if record_dict["file"].replace("  ", " ") == str(
                        same_dir_pdf
                    ).replace("  ", " "):
                        same_dir_pdf.rename(str(same_dir_pdf).replace("  ", " "))
                        record_dict["file"] = record_dict["file"].replace("  ", " ")

                full_path = self.review_manager.path / Path(record_dict["file"])

                if not full_path.is_file():
                    # Fix broken symlinks based on local_index

                    if os.path.islink(full_path) and not os.path.exists(full_path):
                        full_path.unlink()

                    try:
                        record = colrev.record.Record(data=record_dict)
                        retrieved_record = local_index.retrieve(
                            record_dict=record.data, include_file=True
                        )
                        if "file" in retrieved_record:
                            record.update_field(
                                key="file",
                                value=str(retrieved_record["file"]),
                                source="local_index",
                            )
                            pdf_get_operation.import_file(record=record)
                            if "fulltext" in retrieved_record:
                                del retrieved_record["fulltext"]
                            self.review_manager.logger.info(
                                f" fix broken symlink: {record_dict['ID']}"
                            )

                    except colrev_exceptions.RecordNotInIndexException:
                        pass

                if full_path.is_file():
                    continue

                record_dict["colrev_status_backup"] = record_dict["colrev_status"]
                del record_dict["file"]
                record_dict[
                    "colrev_status"
                ] = colrev.record.RecordState.rev_prescreen_included

        except AttributeError:

            print("Could not read bibtex file")

        self.review_manager.dataset.save_records_dict(records=records)


if __name__ == "__main__":
    pass
