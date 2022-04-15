#! /usr/bin/env python
import csv
import typing
from pathlib import Path

import pandas as pd

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class Prescreen(Process):
    def __init__(self, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER,
            ProcessType.prescreen,
            notify_state_transition_process=notify_state_transition_process,
        )

    def export_table(self, export_table_format: str) -> None:
        self.REVIEW_MANAGER.logger.info("Loading records for export")
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        tbl = []
        for record in records.vaules():

            if record["status"] in [
                RecordState.md_imported,
                RecordState.md_retrieved,
                RecordState.md_needs_manual_preparation,
                RecordState.md_prepared,
            ]:
                continue

            inclusion_1, inclusion_2 = "NA", "NA"

            if RecordState.md_processed == record["status"]:
                inclusion_1 = "TODO"
            elif RecordState.rev_prescreen_excluded == record["status"]:
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

            # excl_criteria = {}
            # if "excl_criteria" in record:
            #     for ecrit in record["excl_criteria"].split(";"):
            #         criteria = {ecrit.split("=")[0]: ecrit.split("=")[1]}
            #         excl_criteria.update(criteria)

            excl_criteria = record.get("excl_criteria", "NA")
            if excl_criteria == "NA" and inclusion_2 == "yes":
                excl_criteria = "TODO"

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
                "excl_criteria": excl_criteria,
            }
            # row.update    (excl_criteria)
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("screen_table.csv", index=False, quoting=csv.QUOTE_ALL)
            self.REVIEW_MANAGER.logger.info("Created screen_table (csv)")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("screen_table.xlsx", index=False, sheet_name="screen")
            self.REVIEW_MANAGER.logger.info("Created screen_table (xlsx)")

        return

    def import_table(self, import_table_path: str) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        if not Path(import_table_path).is_file():
            self.REVIEW_MANAGER.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        self.REVIEW_MANAGER.logger.warning(
            "import_table not completed (exclusion_criteria not yet imported)"
        )

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record = records[screened_record.get("ID", "")]
                if "no" == screened_record.get("inclusion_1", ""):
                    record["status"] = RecordState.rev_prescreen_excluded
                if "yes" == screened_record.get("inclusion_1", ""):
                    record["status"] = RecordState.rev_prescreen_included
                if "no" == screened_record.get("inclusion_2", ""):
                    record["status"] = RecordState.rev_excluded
                if "yes" == screened_record.get("inclusion_2", ""):
                    record["status"] = RecordState.rev_included
                if "" != screened_record.get("excl_criteria", ""):
                    record["excl_criteria"] = screened_record.get("excl_criteria", "")

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)

        return

    def include_all_in_prescreen(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50
        for record in records.values():
            if record["status"] != RecordState.md_processed:
                continue
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "Included in prescreen (automatically)"
            )
            record.update(status=RecordState.rev_prescreen_included)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
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
            conditions=[{"status": RecordState.md_processed}]
        )
        prescreen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prescreen_data))
        return prescreen_data

    def set_data(self, record: dict, prescreen_inclusion: bool, PAD: int = 40) -> None:

        if prescreen_inclusion:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Included in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                [record["ID"]], "status", str(RecordState.rev_prescreen_included)
            )
        else:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Excluded in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                [record["ID"]], "status", str(RecordState.rev_prescreen_excluded)
            )

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def create_prescreen_split(self, create_split: int) -> list:
        import math

        prescreen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.REVIEW_MANAGER.report_logger.info(
            f"Creating prescreen splits for {create_split} researchers "
            f"({nrecs} each)"
        )

        for i in range(0, create_split):
            added: typing.List[str] = []
            while len(added) < nrecs:
                added.append(next(data["items"])["ID"])
            prescreen_splits.append("colrev prescreen --split " + ",".join(added))

        return prescreen_splits


if __name__ == "__main__":
    pass
