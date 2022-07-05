#! /usr/bin/env python
from pathlib import Path

import zope.interface

from colrev_core.process import ScreenEndpoint
from colrev_core.record import RecordState


@zope.interface.implementer(ScreenEndpoint)
class CoLRevCLIScreenEndpoint:
    def run_screen(self, SCREEN, records: dict, split: list) -> dict:
        from colrev.cli import screen_cli

        records = screen_cli(SCREEN, split)

        return records


@zope.interface.implementer(ScreenEndpoint)
class SpreadsheetScreenEndpoint:
    def export_table(self, SCREEN, records, split, export_table_format="csv") -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter
        import csv
        import pandas as pd

        SCREEN.REVIEW_MANAGER.logger.info("Loading records for export")

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            inclusion_2 = "NA"

            if RecordState.pdf_prepared == record["colrev_status"]:
                inclusion_2 = "TODO"
            if RecordState.rev_excluded == record["colrev_status"]:
                inclusion_2 = "no"
            if record["colrev_status"] in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                inclusion_2 = "yes"

            exclusion_criteria = record.get("exclusion_criteria", "NA")
            if exclusion_criteria == "NA" and inclusion_2 == "yes":
                exclusion_criteria = "TODO"

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
                "screen_inclusion": inclusion_2,
                "exclusion_criteria": exclusion_criteria,
            }
            # row.update    (exclusion_criteria)
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("screen.csv", index=False, quoting=csv.QUOTE_ALL)
            SCREEN.REVIEW_MANAGER.logger.info("Created screen.csv")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("screen.xlsx", index=False, sheet_name="screen")
            SCREEN.REVIEW_MANAGER.logger.info("Created screen.xlsx")

        return

    def import_table(self, SCREEN, records, import_table_path="screen.csv") -> None:
        import pandas as pd

        if not Path(import_table_path).is_file():
            SCREEN.REVIEW_MANAGER.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        SCREEN.REVIEW_MANAGER.logger.warning(
            "import_table not completed (exclusion_criteria not yet imported)"
        )

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record = records[screened_record.get("ID", "")]
                if "no" == screened_record.get("inclusion_1", ""):
                    record["colrev_status"] = RecordState.rev_prescreen_excluded
                if "yes" == screened_record.get("inclusion_1", ""):
                    record["colrev_status"] = RecordState.rev_prescreen_included
                if "no" == screened_record.get("inclusion_2", ""):
                    record["colrev_status"] = RecordState.rev_excluded
                if "yes" == screened_record.get("inclusion_2", ""):
                    record["colrev_status"] = RecordState.rev_included
                if "" != screened_record.get("exclusion_criteria", ""):
                    record["exclusion_criteria"] = screened_record.get(
                        "exclusion_criteria", ""
                    )

        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        return

    def run_screen(self, SCREEN, records: dict, split: list) -> dict:

        if "y" == input("create screen spreadsheet [y,n]?"):
            self.export_table(SCREEN, records, split)

        if "y" == input("import screen spreadsheet [y,n]?"):
            self.import_table(SCREEN, records)

        if SCREEN.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            if "y" == input("create commit [y,n]?"):
                SCREEN.REVIEW_MANAGER.create_commit(msg="Screen", manual_author=True)
        return records
