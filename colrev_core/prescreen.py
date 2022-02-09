#! /usr/bin/env python
import csv
from pathlib import Path

import pandas as pd

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class Prescreen(Process):
    def __init__(self):
        super().__init__(ProcessType.prescreen)
        self.REVIEW_MANAGER.notify(self)

    def export_table(self, export_table_format: str) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        tbl = []
        for record in records:

            inclusion_1, inclusion_2 = "NA", "NA"

            if RecordState.md_retrieved == record["status"]:
                inclusion_1 = "TODO"
            if RecordState.rev_prescreen_excluded == record["status"]:
                inclusion_1 = "no"
            else:
                inclusion_1 = "yes"
                inclusion_2 = "TODO"
                if RecordState.rev_excluded == record["status"]:
                    inclusion_2 = "no"
                if record["status"] in [
                    RecordState.rev_included,
                    RecordState.rev_synthesized,
                ]:
                    inclusion_2 = "yes"

            excl_criteria = {}
            if "excl_criteria" in record:
                for ecrit in record["excl_criteria"].split(";"):
                    criteria = {ecrit.split("=")[0]: ecrit.split("=")[1]}
                    excl_criteria.update(criteria)

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
                "inclusion_1": inclusion_1,
                "inclusion_2": inclusion_2,
            }
            row.update(excl_criteria)
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("screen_table.csv", index=False, quoting=csv.QUOTE_ALL)
            self.logger.info("Created screen_table (csv)")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("screen_table.xlsx", index=False, sheet_name="screen")
            self.logger.info("Created screen_table (xlsx)")

        return

    def import_table(self, import_table_path: str) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        if not Path(import_table_path).is_file():
            self.logger.error(f"Did not find {import_table_path} - exiting.")
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        records = screen_df.to_dict("records")

        self.logger.warning(
            "import_table not completed (exclusion_criteria not yet imported)"
        )

        for x in [
            [x.get("ID", ""), x.get("inclusion_1", ""), x.get("inclusion_2", "")]
            for x in records
        ]:
            record_list = [e for e in records if e["ID"] == x[0]]
            if len(record_list) == 1:
                record: dict = record_list.pop()
                if x[1] == "no":
                    record["status"] = RecordState.rev_prescreen_excluded
                if x[1] == "yes":
                    record["status"] = RecordState.rev_prescreen_included
                if x[2] == "no":
                    record["status"] = RecordState.rev_excluded
                if x[2] == "yes":
                    record["status"] = RecordState.rev_included
                # TODO: exclusion-criteria

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)

        return

    def include_all_in_prescreen(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50  # TODO
        for record in records:
            if record["status"] != RecordState.md_processed:
                continue
            self.report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "Included in prescreen (automatically)"
            )
            record.update(status=RecordState.rev_prescreen_included)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            "Pre-screen (include_all)", manual_author=False, saved_args=saved_args
        )

        return

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [x for x in record_state_list if str(RecordState.md_processed) == x[1]]
        )
        PAD = min((max(len(x[0]) for x in record_state_list) + 2), 40)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions={"status": RecordState.md_processed}
        )
        prescreen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.logger.debug(self.pp.pformat(prescreen_data))
        return prescreen_data

    def set_data(self, record: dict, prescreen_inclusion: bool, PAD: int = 40) -> None:

        if prescreen_inclusion:
            self.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Included in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                [record["ID"]], "status", str(RecordState.rev_prescreen_included)
            )
        else:
            self.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Excluded in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                [record["ID"]], "status", str(RecordState.rev_prescreen_excluded)
            )

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return


if __name__ == "__main__":
    pass
