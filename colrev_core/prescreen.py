#! /usr/bin/env python
import typing

from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class Prescreen(Process):

    from colrev_core.built_in import prescreen as built_in_prescreen

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
            type=ProcessType.prescreen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        self.prescreen_scripts: typing.Dict[
            str, typing.Any
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.prescreen.scripts,
        )

    def export_table(self, *, export_table_format: str) -> None:
        from colrev_core.built_in import prescreen as built_in_prescreen

        ENDPOINT = built_in_prescreen.SpreadsheetPrescreenEndpoint(
            SETTINGS={"name": "export_table"}
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.export_table(self, records, [])
        return

    def import_table(self, *, import_table_path: str) -> None:
        from colrev_core.built_in import prescreen as built_in_prescreen

        ENDPOINT = built_in_prescreen.SpreadsheetPrescreenEndpoint(
            SETTINGS={"name": "import_table"}
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.import_table(self, records, import_table_path)

        return

    def include_all_in_prescreen(self) -> None:
        from colrev_core.built_in import prescreen as built_in_prescreen

        ENDPOINT = built_in_prescreen.ConditionalPrescreenEndpoint(
            SETTINGS={"name": "include_all"}
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.run_prescreen(self, records, [])
        return

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.md_processed) == x["colrev_status"]
            ]
        )
        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"colrev_status": RecordState.md_processed}]
        )
        prescreen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prescreen_data))
        return prescreen_data

    def create_prescreen_split(self, *, create_split: int) -> list:
        import math

        prescreen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.REVIEW_MANAGER.report_logger.info(
            f"Creating prescreen splits for {create_split} researchers "
            f"({nrecs} each)"
        )

        added: typing.List[str] = []
        for i in range(0, create_split):
            while len(added) < nrecs:
                added.append(next(data["items"])["ID"])
        prescreen_splits.append("colrev prescreen --split " + ",".join(added))

        return prescreen_splits

    def setup_custom_script(self) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, "template/custom_prescreen_script.py")
        if filedata:
            with open("custom_prescreen_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(
            path="custom_prescreen_script.py"
        )

        self.REVIEW_MANAGER.settings.prescreen.scripts.append(
            {"endpoint": "custom_prescreen_script"}
        )
        self.REVIEW_MANAGER.save_settings()

        return

    def main(self, *, split_str: str):

        split = []
        if split_str != "NA":
            split = split_str.split(",")
            split.remove("")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for PRESCREEN_SCRIPT in self.REVIEW_MANAGER.settings.prescreen.scripts:

            self.REVIEW_MANAGER.logger.info(f"Run {PRESCREEN_SCRIPT['endpoint']}")
            ENDPOINT = self.prescreen_scripts[PRESCREEN_SCRIPT["endpoint"]]
            records = ENDPOINT.run_prescreen(self, records, split)

        return


if __name__ == "__main__":
    pass
