#! /usr/bin/env python
from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from dacite import from_dict

import colrev.cli_colors as colors
import colrev.process
import colrev.record
import colrev.settings

if TYPE_CHECKING:
    import colrev.screen.Screen


@zope.interface.implementer(colrev.process.ScreenEndpoint)
class CoLRevCLIScreenEndpoint:
    def __init__(
        self, *, screen_operation: colrev.screen.Screen, settings: dict
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @classmethod
    def get_screening_criteria(
        cls, *, screen_operation: colrev.screen.Screen, records: dict
    ) -> dict:

        screening_criteria = screen_operation.review_manager.settings.screen.criteria
        if len(screening_criteria) == 0 and 0 == len(
            [
                r
                for r in records.values()
                if r["colrev_status"]
                in [
                    colrev.record.RecordState.rev_included,
                    colrev.record.RecordState.rev_excluded,
                    colrev.record.RecordState.rev_synthesized,
                ]
            ]
        ):

            screening_criteria = {}
            while "y" == input("Add screening criterion [y,n]?"):
                short_name = input("Provide a short name: ")
                if "i" == input("Inclusion or exclusion criterion [i,e]?: "):
                    criterion_type = (
                        colrev.settings.ScreenCriterionType.inclusion_criterion
                    )
                else:
                    criterion_type = (
                        colrev.settings.ScreenCriterionType.exclusion_criterion
                    )
                explanation = input("Provide a short explanation: ")

                screening_criteria[short_name] = colrev.settings.ScreenCriterion(
                    explanation=explanation, criterion_type=criterion_type, comment=""
                )

            screen_operation.set_screening_criteria(
                screening_criteria=screening_criteria
            )

        return screening_criteria

    def screen_cli(self, screen_operation: colrev.screen.Screen, split: list) -> dict:

        screen_data = screen_operation.get_data()
        stat_len = screen_data["nr_tasks"]

        i, quit_pressed = 0, False

        screen_operation.review_manager.logger.info("Start screen")

        if 0 == stat_len:
            screen_operation.review_manager.logger.info("No records to prescreen")

        records = screen_operation.review_manager.dataset.load_records_dict()

        screening_criteria = self.get_screening_criteria(
            screen_operation=screen_operation, records=records
        )

        print("\n\nIn the screen, the following criteria are applied:\n")
        for (
            criterion_name,
            criterion_settings,
        ) in screen_operation.review_manager.settings.screen.criteria.items():
            color = colors.GREEN
            if (
                colrev.settings.ScreenCriterionType.exclusion_criterion
                == criterion_settings.criterion_type
            ):
                color = colors.RED
            print(
                f" - {criterion_name} "
                f"({color}{criterion_settings.criterion_type}{colors.END}): "
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

            screen_record = colrev.record.ScreenRecord(data=record)
            abstract_from_tei = False
            if "abstract" not in screen_record.data:
                abstract_from_tei = True
                tei = screen_operation.review_manager.get_tei(
                    pdf_path=Path(screen_record.data["file"]),
                    tei_path=screen_record.get_tei_filename(),
                )
                screen_record.data["abstract"] = tei.get_abstract()

            print(screen_record)
            if abstract_from_tei:
                del screen_record.data["abstract"]

            if criteria_available:
                decisions = []

                for criterion_name, criterion_settings in screening_criteria.items():

                    decision, ret = "NA", "NA"
                    while ret not in ["y", "n", "q", "s"]:
                        color = colors.GREEN
                        if (
                            colrev.settings.ScreenCriterionType.exclusion_criterion
                            == criterion_settings.criterion_type
                        ):
                            color = colors.RED

                        ret = input(
                            # is relevant / should be in the sample / should be retained
                            f"({i}/{stat_len}) Record should be included according to"
                            f" {criterion_settings.criterion_type}"
                            f" {color}{criterion_name}{colors.END}"
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
                    screen_operation.review_manager.logger.info("Stop screen")
                    break

                c_field = ""
                for criterion_name, decision in decisions:
                    c_field += f";{criterion_name}={decision}"
                c_field = c_field.replace(" ", "").lstrip(";")

                screen_inclusion = all(decision == "in" for _, decision in decisions)

                screen_record.screen(
                    review_manager=screen_operation.review_manager,
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
                    screen_operation.review_manager.logger.info("Stop screen")
                    break

                if decision == "y":
                    screen_record.screen(
                        review_manager=screen_operation.review_manager,
                        screen_inclusion=True,
                        screening_criteria="NA",
                    )
                if decision == "n":
                    screen_record.screen(
                        review_manager=screen_operation.review_manager,
                        screen_inclusion=False,
                        screening_criteria="NA",
                        PAD=screen_data["PAD"],
                    )

            if quit_pressed:
                screen_operation.review_manager.logger.info("Stop screen")
                break

        if stat_len == 0:
            screen_operation.review_manager.logger.info("No records to screen")
            return records

        screen_operation.review_manager.dataset.add_record_changes()

        if i < stat_len:  # if records remain for screening
            if "y" != input("Create commit (y/n)?"):
                return records

        screen_operation.review_manager.create_commit(
            msg="Screening (manual)", manual_author=True, saved_args=None
        )
        return records

    def run_screen(self, screen_operation, records: dict, split: list) -> dict:

        records = self.screen_cli(screen_operation, split)

        return records


@zope.interface.implementer(colrev.process.ScreenEndpoint)
class SpreadsheetScreenEndpoint:
    spreadsheet_path = Path("screen/screen.csv")

    def __init__(
        self, *, screen_operation: colrev.screen.Screen, settings: dict
    ) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    def export_table(
        self,
        screen_operation: colrev.screen.Screen,
        records: dict,
        split: list,
        export_table_format: str = "csv",
    ) -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter

        if self.spreadsheet_path.is_file():
            print("File already exists. Please rename it.")
            return

        screen_operation.review_manager.logger.info("Loading records for export")

        screening_criteria = CoLRevCLIScreenEndpoint.get_screening_criteria(
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
                inclusion_2 = "TODO (yes/no)"
            if colrev.record.RecordState.rev_excluded == record["colrev_status"]:
                inclusion_2 = "no"
            if record["colrev_status"] in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                inclusion_2 = "yes"

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
            screen_operation.review_manager.logger.info(
                f"Created {self.spreadsheet_path}"
            )

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel(
                self.spreadsheet_path.with_suffix(".xlsx"),
                index=False,
                sheet_name="screen",
            )
            screen_operation.review_manager.logger.info(
                f"Created {self.spreadsheet_path.with_suffix('.xlsx')}"
            )

        return

    def import_table(
        self,
        screen_operation: colrev.screen.Screen,
        records: dict,
        import_table_path: Path = None,
    ) -> None:

        # pylint: disable=duplicate-code
        if import_table_path is None:
            import_table_path = self.spreadsheet_path

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
                record = records[screened_record.get("ID", "")]
                if "screen_inclusion" in screened_record:
                    if "yes" == screened_record["screen_inclusion"]:
                        record["colrev_status"] = colrev.record.RecordState.rev_included
                    elif "no" == screened_record["screen_inclusion"]:
                        record["colrev_status"] = colrev.record.RecordState.rev_excluded
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
                    record["colrev_status"] = colrev.record.RecordState.rev_excluded
                else:
                    record["colrev_status"] = colrev.record.RecordState.rev_included

        screen_operation.review_manager.dataset.save_records_dict(records=records)
        screen_operation.review_manager.dataset.add_record_changes()

    def run_screen(
        self, screen_operation: colrev.screen.Screen, records: dict, split: list
    ) -> dict:

        if "y" == input("create screen spreadsheet [y,n]?"):
            self.export_table(screen_operation, records, split)

        if "y" == input("import screen spreadsheet [y,n]?"):
            self.import_table(screen_operation, records)

        if screen_operation.review_manager.dataset.has_changes():
            if "y" == input("create commit [y,n]?"):
                screen_operation.review_manager.create_commit(
                    msg="Screen", manual_author=True, script_call="colrev screen"
                )
        return records
