#! /usr/bin/env python
import csv
import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


@dataclass
class PrescreenConfiguration:
    plugin: typing.Optional[str]
    mode: typing.Optional[str]


class PrescreenRecord(Record):
    def __init__(self, data: dict):
        super().__init__(data)

    def __str__(self) -> str:

        self.identifying_keys_order = ["ID", "ENTRYTYPE"] + [
            k for k in self.identifying_fields if k in self.data
        ]
        complementary_keys_order = [
            k for k, v in self.data.items() if k not in self.identifying_keys_order
        ]

        ik_sorted = {
            k: v for k, v in self.data.items() if k in self.identifying_keys_order
        }
        ck_sorted = {
            k: v
            for k, v in self.data.items()
            if k in complementary_keys_order and k not in self.provenance_keys
        }
        ret_str = (
            self.pp.pformat(ik_sorted)[:-1] + "\n" + self.pp.pformat(ck_sorted)[1:]
        )

        return ret_str


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

            if record["colrev_status"] in [
                RecordState.md_imported,
                RecordState.md_retrieved,
                RecordState.md_needs_manual_preparation,
                RecordState.md_prepared,
            ]:
                continue

            inclusion_1, inclusion_2 = "NA", "NA"

            if RecordState.md_processed == record["colrev_status"]:
                inclusion_1 = "TODO"
            elif RecordState.rev_prescreen_excluded == record["colrev_status"]:
                inclusion_1 = "no"
            else:
                inclusion_1 = "yes"
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
                "inclusion_1": inclusion_1,
                "inclusion_2": inclusion_2,
                "exclusion_criteria": exclusion_criteria,
            }
            # row.update    (exclusion_criteria)
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

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)

        return

    def include_all_in_prescreen(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50
        for record in records.values():
            if record["colrev_status"] != RecordState.md_processed:
                continue
            self.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "Included in prescreen (automatically)"
            )
            record.update(colrev_status=RecordState.rev_prescreen_included)

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
            conditions=[{"colrev_status": RecordState.md_processed}]
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
                [record["ID"]], "colrev_status", str(RecordState.rev_prescreen_included)
            )
        else:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Excluded in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                [record["ID"]], "colrev_status", str(RecordState.rev_prescreen_excluded)
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
