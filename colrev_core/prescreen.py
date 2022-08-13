#! /usr/bin/env python
import math
import pkgutil
import typing

import colrev_core.built_in.prescreen as built_in_prescreen
import colrev_core.environment
import colrev_core.process
import colrev_core.record


class Prescreen(colrev_core.process.Process):

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "scope_prescreen": {
            "endpoint": built_in_prescreen.ScopePrescreenEndpoint,
        },
        "colrev_cli_prescreen": {
            "endpoint": built_in_prescreen.CoLRevCLIPrescreenEndpoint,
        },
        "asreview_prescreen": {
            "endpoint": built_in_prescreen.ASReviewPrescreenEndpoint,
        },
        "conditional_prescreen": {
            "endpoint": built_in_prescreen.ConditionalPrescreenEndpoint
        },
        "spreadsheed_prescreen": {
            "endpoint": built_in_prescreen.SpreadsheetPrescreenEndpoint
        },
    }

    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.prescreen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        self.prescreen_scripts: typing.Dict[
            str, typing.Any
        ] = colrev_core.environment.AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.prescreen.scripts,
        )

    def export_table(self, *, export_table_format: str) -> None:

        ENDPOINT = built_in_prescreen.SpreadsheetPrescreenEndpoint(
            PRESCREEN=self, SETTINGS={"name": "export_table"}
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.export_table(self, records, [])

    def import_table(self, *, import_table_path: str) -> None:

        ENDPOINT = built_in_prescreen.SpreadsheetPrescreenEndpoint(
            PRESCREEN=self, SETTINGS={"name": "import_table"}
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.import_table(self, records, import_table_path)

    def include_all_in_prescreen(self) -> None:

        ENDPOINT = built_in_prescreen.ConditionalPrescreenEndpoint(
            PRESCREEN=self, SETTINGS={"name": "include_all"}
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.run_prescreen(self, records, [])

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev_core.record.RecordState.md_processed)
                == x["colrev_status"]
            ]
        )
        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"colrev_status": colrev_core.record.RecordState.md_processed}]
        )
        prescreen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prescreen_data))
        return prescreen_data

    def create_prescreen_split(self, *, create_split: int) -> list:

        prescreen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.REVIEW_MANAGER.report_logger.info(
            f"Creating prescreen splits for {create_split} researchers "
            f"({nrecs} each)"
        )

        added: typing.List[str] = []
        while len(added) < nrecs:
            added.append(next(data["items"])["ID"])
        prescreen_splits.append("colrev prescreen --split " + ",".join(added))

        return prescreen_splits

    def setup_custom_script(self) -> None:

        filedata = pkgutil.get_data(__name__, "template/custom_prescreen_script.py")
        if filedata:
            with open("custom_prescreen_script.py", "w", encoding="utf8") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            path="custom_prescreen_script.py"
        )

        self.REVIEW_MANAGER.settings.prescreen.scripts.append(
            {"endpoint": "custom_prescreen_script"}
        )
        self.REVIEW_MANAGER.save_settings()

    def main(self, *, split_str: str):

        # pylint: disable=duplicate-code
        split = []
        if split_str != "NA":
            split = split_str.split(",")
            split.remove("")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for PRESCREEN_SCRIPT in self.REVIEW_MANAGER.settings.prescreen.scripts:

            self.REVIEW_MANAGER.logger.info(f"Run {PRESCREEN_SCRIPT['endpoint']}")
            ENDPOINT = self.prescreen_scripts[PRESCREEN_SCRIPT["endpoint"]]
            records = ENDPOINT.run_prescreen(self, records, split)


if __name__ == "__main__":
    pass
