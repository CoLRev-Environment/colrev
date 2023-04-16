#! /usr/bin/env python
"""Screen based on a table"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.screen.utils as util_cli_screen
import colrev.record
import colrev.settings

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.screen


@zope.interface.implementer(colrev.env.package_manager.ScreenPackageEndpointInterface)
@dataclass
class TableScreen(JsonSchemaMixin):
    """Screen documents using tables (exported and imported)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False
    export_todos_only: bool = True

    screen_table_path = Path("screen/screen.csv")

    def __init__(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __create_screening_table(
        self, *, screen_operation: colrev.ops.screen.Screen, records: dict, split: list
    ) -> list:
        # pylint: disable=too-many-branches
        screen_operation.review_manager.logger.info("Loading records for export")

        screening_criteria = util_cli_screen.get_screening_criteria_from_user_input(
            screen_operation=screen_operation, records=records
        )

        tbl = []
        for record in records.values():
            if record["colrev_status"] not in [
                colrev.record.RecordState.pdf_prepared,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            inclusion_2 = "NA"

            if colrev.record.RecordState.pdf_prepared == record["colrev_status"]:
                inclusion_2 = "TODO"
            elif self.export_todos_only:
                continue
            if colrev.record.RecordState.rev_excluded == record["colrev_status"]:
                inclusion_2 = "out"
            if record["colrev_status"] in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                inclusion_2 = "in"

            # pylint: disable=duplicate-code
            row = {
                "ID": record["ID"],
                "author": record.get("author", ""),
                "title": record.get("title", ""),
                "journal": record.get("journal", ""),
                "booktitle": record.get("booktitle", ""),
                "year": record.get("year", ""),
                "volume": record.get("volume", ""),
                "number": record.get("number", ""),
                "pages": record.get("pages", ""),
                "doi": record.get("doi", ""),
                "abstract": record.get("abstract", ""),
            }

            if len(screening_criteria) == 0:
                # No criteria: code inclusion directly
                row["screen_inclusion"] = inclusion_2

            else:
                # Code criteria
                screening_criteria_field = record.get("screening_criteria", "")
                if screening_criteria_field == "":
                    # and inclusion_2 == "in"
                    for criterion_name in screening_criteria.keys():
                        row[criterion_name] = "TODO (in/out)"
                else:
                    for criterion_name, decision in screening_criteria_field.split(";"):
                        row[criterion_name] = decision

            tbl.append(row)

        return tbl

    def export_table(
        self,
        screen_operation: colrev.ops.screen.Screen,
        records: dict,
        split: list,
        export_table_format: str = "csv",
    ) -> None:
        """Export a screening table"""

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/73
        # add delta (records not yet in the table)
        # instead of overwriting
        # export_table_format as a settings parameter

        if self.screen_table_path.is_file():
            print("File already exists. Please rename it.")
            return

        tbl = self.__create_screening_table(
            screen_operation=screen_operation, records=records, split=split
        )

        self.screen_table_path.parents[0].mkdir(parents=True, exist_ok=True)

        if export_table_format.lower() == "csv":
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv(self.screen_table_path, index=False, quoting=csv.QUOTE_ALL)
            screen_operation.review_manager.logger.info(
                f"Created {self.screen_table_path}"
            )

        if export_table_format.lower() == "xlsx":
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel(
                self.screen_table_path.with_suffix(".xlsx"),
                index=False,
                sheet_name="screen",
            )
            screen_operation.review_manager.logger.info(
                f"Created {self.screen_table_path.with_suffix('.xlsx')}"
            )

        return

    def import_table(
        self,
        screen_operation: colrev.ops.screen.Screen,
        records: dict,
        import_table_path: Optional[Path] = None,
    ) -> None:
        """Import a screening table"""

        # pylint: disable=duplicate-code
        if import_table_path is None:
            import_table_path = self.screen_table_path

        if not Path(import_table_path).is_file():
            screen_operation.review_manager.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return

        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        screening_criteria = screen_operation.review_manager.settings.screen.criteria

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record_dict = records[screened_record.get("ID", "")]
                record = colrev.record.Record(data=record_dict)
                if "screen_inclusion" in screened_record:
                    if screened_record["screen_inclusion"] == "in":
                        record.set_status(
                            target_state=colrev.record.RecordState.rev_included
                        )
                    elif screened_record["screen_inclusion"] == "out":
                        record.set_status(
                            target_state=colrev.record.RecordState.rev_excluded
                        )
                    else:
                        print(
                            f"Invalid choice: {screened_record['screen_inclusion']} "
                            f"({screened_record['ID']})"
                        )
                    continue
                screening_criteria_field = ""
                for screening_criterion in screening_criteria.keys():
                    assert screened_record[screening_criterion] in ["in", "out"]
                    screening_criteria_field += (
                        screening_criterion
                        + "="
                        + screened_record[screening_criterion]
                        + ";"
                    )
                screening_criteria_field = screening_criteria_field.rstrip(";")
                record.data["screening_criteria"] = screening_criteria_field
                if "=out" in screening_criteria_field:
                    record.set_status(
                        target_state=colrev.record.RecordState.rev_excluded
                    )
                else:
                    record.set_status(
                        target_state=colrev.record.RecordState.rev_included
                    )

        screen_operation.review_manager.dataset.save_records_dict(records=records)
        screen_operation.review_manager.dataset.add_record_changes()

    def run_screen(
        self, screen_operation: colrev.ops.screen.Screen, records: dict, split: list
    ) -> dict:
        """Screen records based on screening tables"""

        if input("create screen table [y,n]?") == "y":
            self.export_table(screen_operation, records, split)

        if input("import screen table [y,n]?") == "y":
            self.import_table(screen_operation, records)

        if screen_operation.review_manager.dataset.has_changes():
            if input("create commit [y,n]?") == "y":
                screen_operation.review_manager.create_commit(
                    msg="Screen", manual_author=True
                )
        return records


if __name__ == "__main__":
    pass
