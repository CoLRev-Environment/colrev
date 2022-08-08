#! /usr/bin/env python
import csv
from pathlib import Path

import pandas as pd
import zope.interface
from dacite import from_dict

import colrev_core.environment
import colrev_core.process
import colrev_core.record
import colrev_core.settings


@zope.interface.implementer(colrev_core.process.ScreenEndpoint)
class CoLRevCLIScreenEndpoint:
    def __init__(self, *, SCREEN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @classmethod
    def get_screening_criteria(cls, *, SCREEN, records):

        screening_criteria = SCREEN.REVIEW_MANAGER.settings.screen.criteria
        if len(screening_criteria) == 0 and 0 == len(
            [
                r
                for r in records.values()
                if r["colrev_status"]
                in [
                    colrev_core.record.RecordState.rev_included,
                    colrev_core.record.RecordState.rev_excluded,
                    colrev_core.record.RecordState.rev_synthesized,
                ]
            ]
        ):

            screening_criteria = {}
            while "y" == input("Add screening criterion [y,n]?"):
                short_name = input("Provide a short name: ")
                if "i" == input("Inclusion or exclusion criterion [i,e]?: "):
                    criterion_type = (
                        colrev_core.settings.ScreenCriterionType.inclusion_criterion
                    )
                else:
                    criterion_type = (
                        colrev_core.settings.ScreenCriterionType.exclusion_criterion
                    )
                explanation = input("Provide a short explanation: ")

                screening_criteria[short_name] = colrev_core.settings.ScreenCriterion(
                    explanation=explanation, criterion_type=criterion_type, comment=""
                )

            SCREEN.set_screening_criteria(screening_criteria=screening_criteria)

        return screening_criteria

    def screen_cli(self, SCREEN, split) -> dict:

        screen_data = SCREEN.get_data()
        stat_len = screen_data["nr_tasks"]

        i, quit_pressed = 0, False

        SCREEN.REVIEW_MANAGER.logger.info("Start screen")

        if 0 == stat_len:
            SCREEN.REVIEW_MANAGER.logger.info("No records to prescreen")

        records = SCREEN.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        screening_criteria = self.get_screening_criteria(SCREEN=SCREEN, records=records)

        print("\n\nIn the screen, the following criteria are applied:\n")
        for (
            criterion_name,
            criterion_settings,
        ) in SCREEN.REVIEW_MANAGER.settings.screen.criteria.items():
            color = "\033[92m"
            if (
                colrev_core.settings.ScreenCriterionType.exclusion_criterion
                == criterion_settings.criterion_type
            ):
                color = "\033[91m"
            print(
                f" - {criterion_name} "
                f"({color}{criterion_settings.criterion_type}\033[0m): "
                f"{criterion_settings.explanation}"
            )
            if criterion_settings.comment != "":
                print(f"   {criterion_settings.comment}")

        criteria_available = len(screening_criteria.keys())

        for record in screen_data["items"]:
            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            print("\n\n")
            i += 1
            skip_pressed = False

            SCREEN_RECORD = colrev_core.record.ScreenRecord(data=record)
            abstract_from_tei = False
            if "abstract" not in SCREEN_RECORD.data:
                abstract_from_tei = True
                TEI = colrev_core.environment.TEIParser(
                    pdf_path=Path(SCREEN_RECORD.data["file"]),
                    tei_path=SCREEN_RECORD.get_tei_filename(),
                )
                SCREEN_RECORD.data["abstract"] = TEI.get_abstract()

            print(SCREEN_RECORD)
            if abstract_from_tei:
                del SCREEN_RECORD.data["abstract"]

            if criteria_available:
                decisions = []

                for criterion_name, criterion_settings in screening_criteria.items():

                    decision, ret = "NA", "NA"
                    while ret not in ["y", "n", "q", "s"]:
                        color = "\033[92m"
                        if (
                            colrev_core.settings.ScreenCriterionType.exclusion_criterion
                            == criterion_settings.criterion_type
                        ):
                            color = "\033[91m"

                        ret = input(
                            # is relevant / should be in the sample / should be retained
                            f"({i}/{stat_len}) Record should be included according to"
                            f" {criterion_settings.criterion_type}"
                            f" {color}{criterion_name}\033[0m"
                            " [y,n,q,s]? "
                        )
                        if "q" == ret:
                            quit_pressed = True
                        elif "s" == ret:
                            skip_pressed = True
                            continue
                        elif ret in ["y", "n"]:
                            decision = ret

                    if quit_pressed or skip_pressed:
                        break

                    decision = decision.replace("n", "out").replace("y", "in")
                    decisions.append([criterion_name, decision])

                if skip_pressed:
                    continue
                if quit_pressed:
                    SCREEN.REVIEW_MANAGER.logger.info("Stop screen")
                    break

                c_field = ""
                for criterion_name, decision in decisions:
                    c_field += f";{criterion_name}={decision}"
                c_field = c_field.replace(" ", "").lstrip(";")

                screen_inclusion = all(decision == "in" for _, decision in decisions)

                SCREEN_RECORD.screen(
                    REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                    screen_inclusion=screen_inclusion,
                    screening_criteria=c_field,
                    PAD=screen_data["PAD"],
                )

            else:

                decision, ret = "NA", "NA"
                while ret not in ["y", "n", "q", "s"]:
                    ret = input(f"({i}/{stat_len}) Include [y,n,q,s]? ")
                    if "q" == ret:
                        quit_pressed = True
                    elif "s" == ret:
                        skip_pressed = True
                        continue
                    elif ret in ["y", "n"]:
                        decision = ret

                if quit_pressed:
                    SCREEN.REVIEW_MANAGER.logger.info("Stop screen")
                    break

                if decision == "y":
                    SCREEN_RECORD.screen(
                        REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                        screen_inclusion=True,
                        screening_criteria="NA",
                    )
                if decision == "n":
                    SCREEN_RECORD.screen(
                        REVIEW_MANAGER=SCREEN.REVIEW_MANAGER,
                        screen_inclusion=False,
                        screening_criteria="NA",
                        PAD=screen_data["PAD"],
                    )

            if quit_pressed:
                SCREEN.REVIEW_MANAGER.logger.info("Stop screen")
                break

        if stat_len == 0:
            SCREEN.REVIEW_MANAGER.logger.info("No records to screen")
            return records

        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        if i < stat_len:  # if records remain for screening
            if "y" != input("Create commit (y/n)?"):
                return records

        SCREEN.REVIEW_MANAGER.create_commit(
            msg="Screening (manual)", manual_author=True, saved_args=None
        )
        return records

    def run_screen(self, SCREEN, records: dict, split: list) -> dict:

        records = self.screen_cli(SCREEN, split)

        return records


@zope.interface.implementer(colrev_core.process.ScreenEndpoint)
class SpreadsheetScreenEndpoint:
    spreadsheet_path = Path("screen/screen.csv")

    def __init__(self, *, SCREEN, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    def export_table(self, SCREEN, records, split, export_table_format="csv") -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter

        if self.spreadsheet_path.is_file():
            print("File already exists. Please rename it.")
            return

        SCREEN.REVIEW_MANAGER.logger.info("Loading records for export")

        screening_criteria = CoLRevCLIScreenEndpoint.get_screening_criteria(
            SCREEN=SCREEN, records=records
        )

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                colrev_core.record.RecordState.pdf_prepared,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            inclusion_2 = "NA"

            if colrev_core.record.RecordState.pdf_prepared == record["colrev_status"]:
                inclusion_2 = "TODO (yes/no)"
            if colrev_core.record.RecordState.rev_excluded == record["colrev_status"]:
                inclusion_2 = "no"
            if record["colrev_status"] in [
                colrev_core.record.RecordState.rev_included,
                colrev_core.record.RecordState.rev_synthesized,
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
                        record[
                            "colrev_status"
                        ] = colrev_core.record.RecordState.rev_included
                    elif "no" == screened_record["screen_inclusion"]:
                        record[
                            "colrev_status"
                        ] = colrev_core.record.RecordState.rev_excluded
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
                record["screening_criteria"] = screening_criteria_field
                if "=out" in screening_criteria_field:
                    record[
                        "colrev_status"
                    ] = colrev_core.record.RecordState.rev_excluded
                else:
                    record[
                        "colrev_status"
                    ] = colrev_core.record.RecordState.rev_included

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
