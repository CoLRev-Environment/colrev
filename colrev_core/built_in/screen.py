#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict

from colrev_core.process import DefaultSettings
from colrev_core.process import ScreenEndpoint
from colrev_core.record import RecordState


@zope.interface.implementer(ScreenEndpoint)
class CoLRevCLIScreenEndpoint:
    def __init__(self, *, SCREEN, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def run_screen(self, SCREEN, records: dict, split: list) -> dict:
        from colrev.cli import screen_cli

        records = screen_cli(SCREEN, split)

        return records


@zope.interface.implementer(ScreenEndpoint)
class SpreadsheetScreenEndpoint:
    spreadsheet_path = Path("screen/screen.csv")

    def __init__(self, *, SCREEN, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def export_table(self, SCREEN, records, split, export_table_format="csv") -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter
        import csv
        import pandas as pd
        from colrev.cli import get_screening_criteria

        if self.spreadsheet_path.is_file():
            print("File already exists. Please rename it.")
            return

        SCREEN.REVIEW_MANAGER.logger.info("Loading records for export")

        screening_criteria = get_screening_criteria(SCREEN=SCREEN, records=records)

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                RecordState.pdf_prepared,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            inclusion_2 = "NA"

            if RecordState.pdf_prepared == record["colrev_status"]:
                inclusion_2 = "TODO (yes/no)"
            if RecordState.rev_excluded == record["colrev_status"]:
                inclusion_2 = "no"
            if record["colrev_status"] in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                inclusion_2 = "yes"

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
                    # and inclusion_2 == "yes"
                    for criterion_name in screening_criteria.keys():
                        row[criterion_name] = "TODO (in/out)"
                else:
                    for criterion_name, decision in screening_criteria_field.split(";"):
                        row[criterion_name] = decision

            tbl.append(row)

        self.spreadsheet_path.parents[0].mkdir(parents=True, exist_ok=True)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv(self.spreadsheet_path, index=False, quoting=csv.QUOTE_ALL)
            SCREEN.REVIEW_MANAGER.logger.info(f"Created {self.spreadsheet_path}")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel(
                self.spreadsheet_path.with_suffix(".xlsx"),
                index=False,
                sheet_name="screen",
            )
            SCREEN.REVIEW_MANAGER.logger.info(
                f"Created {self.spreadsheet_path.with_suffix('.xlsx')}"
            )

        return

    def import_table(self, SCREEN, records, import_table_path=None) -> None:
        import pandas as pd

        if import_table_path is None:
            import_table_path = self.spreadsheet_path

        if not Path(import_table_path).is_file():
            SCREEN.REVIEW_MANAGER.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return

        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        screening_criteria = SCREEN.REVIEW_MANAGER.settings.screen.criteria

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record = records[screened_record.get("ID", "")]
                if "screen_inclusion" in screened_record:
                    if "yes" == screened_record["screen_inclusion"]:
                        record["colrev_status"] = RecordState.rev_included
                    elif "no" == screened_record["screen_inclusion"]:
                        record["colrev_status"] = RecordState.rev_excluded
                    else:
                        print(
                            f"Invalid choice: {screened_record['screen_inclusion']} "
                            f"({screened_record['ID']})"
                        )
                    continue
                else:
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
                    record["screening_criteria"] = screening_criteria_field
                    if "=out" in screening_criteria_field:
                        record["colrev_status"] = RecordState.rev_excluded
                    else:
                        record["colrev_status"] = RecordState.rev_included

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
                SCREEN.REVIEW_MANAGER.create_commit(
                    msg="Screen", manual_author=True, script_call="colrev screen"
                )
        return records
