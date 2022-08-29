#! /usr/bin/env python
import math
import pkgutil
import typing

import colrev.built_in.prescreen as built_in_prescreen
import colrev.process
import colrev.record


class Prescreen(colrev.process.Process):

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

    def __init__(self, *, review_manager, notify_state_transition_process: bool = True):
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.prescreen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        AdapterManager = self.review_manager.get_environment_service(
            service_identifier="AdapterManager"
        )
        self.prescreen_scripts: typing.Dict[
            str, typing.Any
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=review_manager.settings.prescreen.scripts,
        )

    def export_table(self, *, export_table_format: str) -> None:

        endpoint = built_in_prescreen.SpreadsheetPrescreenEndpoint(
            prescreen=self, settings={"name": "export_table"}
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.export_table(self, records, [])

    def import_table(self, *, import_table_path: str) -> None:

        endpoint = built_in_prescreen.SpreadsheetPrescreenEndpoint(
            prescreen=self, settings={"name": "import_table"}
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.import_table(self, records, import_table_path)

    def include_all_in_prescreen(self) -> None:

        endpoint = built_in_prescreen.ConditionalPrescreenEndpoint(
            prescreen=self, settings={"name": "include_all"}
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.run_prescreen(self, records, [])

    def get_data(self) -> dict:

        record_state_list = self.review_manager.dataset.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev.record.RecordState.md_processed) == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_state_list) + 2), 40)
        items = self.review_manager.dataset.read_next_record(
            conditions=[{"colrev_status": colrev.record.RecordState.md_processed}]
        )
        prescreen_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(prescreen_data)
        )
        return prescreen_data

    def create_prescreen_split(self, *, create_split: int) -> list:

        prescreen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.review_manager.report_logger.info(
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

        self.review_manager.dataset.add_changes(path="custom_prescreen_script.py")

        self.review_manager.settings.prescreen.scripts.append(
            {"endpoint": "custom_prescreen_script"}
        )
        self.review_manager.save_settings()

    def main(self, *, split_str: str):

        # pylint: disable=duplicate-code
        split = []
        if split_str != "NA":
            split = split_str.split(",")
            split.remove("")

        records = self.review_manager.dataset.load_records_dict()

        for prescreen_script in self.review_manager.settings.prescreen.scripts:

            self.review_manager.logger.info(f"Run {prescreen_script['endpoint']}")
            endpoint = self.prescreen_scripts[prescreen_script["endpoint"]]
            records = endpoint.run_prescreen(self, records, split)


if __name__ == "__main__":
    pass
