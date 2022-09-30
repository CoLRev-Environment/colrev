#! /usr/bin/env python
"""Prescreen based on a spreadsheet"""
from __future__ import annotations

import csv
import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record

if typing.TYPE_CHECKING:
    import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class SpreadsheetPrescreen(JsonSchemaMixin):

    """Prescreen based on a spreadsheet (exported and imported)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def export_table(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
        export_table_format: str = "csv",
    ) -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter

        prescreen_operation.review_manager.logger.info("Loading records for export")

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                colrev.record.RecordState.md_processed,
                colrev.record.RecordState.rev_prescreen_excluded,
                colrev.record.RecordState.rev_prescreen_included,
                colrev.record.RecordState.pdf_needs_manual_retrieval,
                colrev.record.RecordState.pdf_imported,
                colrev.record.RecordState.pdf_not_available,
                colrev.record.RecordState.pdf_needs_manual_preparation,
                colrev.record.RecordState.pdf_prepared,
                colrev.record.RecordState.rev_excluded,
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            if colrev.record.RecordState.md_processed == record["colrev_status"]:
                inclusion_1 = "TODO"
            elif (
                colrev.record.RecordState.rev_prescreen_excluded
                == record["colrev_status"]
            ):
                inclusion_1 = "no"
            else:
                inclusion_1 = "yes"

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
                "presceen_inclusion": inclusion_1,
            }
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("prescreen.csv", index=False, quoting=csv.QUOTE_ALL)
            prescreen_operation.review_manager.logger.info("Created prescreen.csv")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("prescreen.xlsx", index=False, sheet_name="screen")
            prescreen_operation.review_manager.logger.info("Created prescreen.xlsx")

    def import_table(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        import_table_path: str = "prescreen.csv",
    ) -> None:
        # pylint: disable=duplicate-code
        if not Path(import_table_path).is_file():
            prescreen_operation.review_manager.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        prescreen_operation.review_manager.logger.warning("import_table not completed")

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record = records[screened_record.get("ID", "")]
                if "no" == screened_record.get("inclusion_1", ""):
                    record[
                        "colrev_status"
                    ] = colrev.record.RecordState.rev_prescreen_excluded
                if "yes" == screened_record.get("inclusion_1", ""):
                    record[
                        "colrev_status"
                    ] = colrev.record.RecordState.rev_prescreen_included

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()
        return

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
    ) -> dict:

        if "y" == input("create prescreen spreadsheet [y,n]?"):
            self.export_table(
                prescreen_operation=prescreen_operation, records=records, split=split
            )

        if "y" == input("import prescreen spreadsheet [y,n]?"):
            self.import_table(prescreen_operation=prescreen_operation, records=records)

        if prescreen_operation.review_manager.dataset.has_changes():
            if "y" == input("create commit [y,n]?"):
                prescreen_operation.review_manager.create_commit(
                    msg="Pre-screen (spreadsheets)",
                    manual_author=True,
                    script_call="colrev prescreen",
                )
        return records


if __name__ == "__main__":
    pass
