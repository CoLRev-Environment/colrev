#! /usr/bin/env python
import typing

from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class Screen(Process):
    from colrev_core.built_in import screen as built_in_screen

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "colrev_cli_screen": {
            "endpoint": built_in_screen.CoLRevCLIScreenEndpoint,
        },
        "spreadsheed_screen": {"endpoint": built_in_screen.SpreadsheetScreenEndpoint},
        # "conditional_screen": {"endpoint": built_in_screen.ConditionalScreenEndpoint},
    }

    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.screen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        self.screen_scripts: typing.Dict[str, typing.Any] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.screen.scripts,
        )

    def include_all_in_screen(
        self,
    ) -> None:
        """Include all records in the screen"""

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        exclusion_criteria = self.get_exclusion_criteria()

        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50
        for record_ID, record in records.items():
            if record["colrev_status"] != RecordState.pdf_prepared:
                continue
            self.REVIEW_MANAGER.report_logger.info(
                f" {record_ID}".ljust(PAD, " ") + "Included in screen (automatically)"
            )
            if len(exclusion_criteria) == 0:
                record.update(exclusion_criteria="NA")
            else:
                record.update(
                    exclusion_criteria=";".join([e + "=no" for e in exclusion_criteria])
                )
            record.update(colrev_status=RecordState.rev_included)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Screen (include_all)",
            manual_author=False,
            script_call="colrev screen",
            saved_args=saved_args,
        )

        return

    def get_exclusion_criteria(self) -> list:
        """Get the list of exclusion criteria from settings"""

        return [c.name for c in self.REVIEW_MANAGER.settings.screen.criteria]

    def set_exclusion_criteria(self, *, exclusion_criteria) -> None:
        self.REVIEW_MANAGER.settings.screen.criteria = exclusion_criteria
        self.REVIEW_MANAGER.save_settings()
        return

    def get_data(self) -> dict:
        """Get the data (records to screen)"""

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.pdf_prepared) == x["colrev_status"]
            ]
        )
        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)
        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"colrev_status": RecordState.pdf_prepared}]
        )
        screen_data = {"nr_tasks": nr_tasks, "PAD": PAD, "items": items}
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(screen_data))
        return screen_data

    def set_data(self, *, record: dict, PAD: int = 40) -> None:
        """Set data (screening decision for a record)"""

        if RecordState.rev_included == record["colrev_status"]:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Included in screen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(new_record=record)
        else:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Excluded in screen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(new_record=record)

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

    def add_criterion(self, *, criterion_to_add) -> None:
        """Add a screening criterion to the records and settings"""
        from colrev_core.settings import ScreenCriterion

        assert criterion_to_add.count(",") == 1
        criterion_name, criterion_explanation = criterion_to_add.split(",")
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        if criterion_name not in [
            c.name for c in self.REVIEW_MANAGER.settings.screen.criteria
        ]:
            ADD_CRITERION = ScreenCriterion(
                name=criterion_name, explanation=criterion_explanation
            )
            self.REVIEW_MANAGER.settings.screen.criteria.append(ADD_CRITERION)
            self.REVIEW_MANAGER.save_settings()
            self.REVIEW_MANAGER.REVIEW_DATASET.add_setting_changes()
        else:
            print(f"Error: criterion {criterion_name} already in settings")
            return

        for ID, record in records.items():

            if record["colrev_status"] in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                record["exclusion_criteria"] += f";{criterion_name}=TODO"
                # Note : we set the status to pdf_prepared because the screening
                # decisions have to be updated (resulting in inclusion or exclusion)
                record["colrev_status"] = RecordState.pdf_prepared
            if record["colrev_status"] == RecordState.rev_excluded:
                record["exclusion_criteria"] += f";{criterion_name}=TODO"
                # Note : no change in colrev_status
                # because at least one of the other criteria led to exclusion decision

        # TODO : screening: if exclusion_criteria field is already available
        # only go through the criteria with "TODO"
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg=f"Add screening criterion: {criterion_name}",
            script_call="colrev screen",
        )

        return

    def delete_criterion(self, *, criterion_to_delete) -> None:
        """Delete a screening criterion from the records and settings"""
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        if criterion_to_delete in [
            c.name for c in self.REVIEW_MANAGER.settings.screen.criteria
        ]:
            for i, c in enumerate(self.REVIEW_MANAGER.settings.screen.criteria):
                if c.name == criterion_to_delete:
                    del self.REVIEW_MANAGER.settings.screen.criteria[i]
            self.REVIEW_MANAGER.save_settings()
            self.REVIEW_MANAGER.REVIEW_DATASET.add_setting_changes()
        else:
            print(f"Error: criterion {criterion_to_delete} not in settings")
            return

        for ID, record in records.items():

            if record["colrev_status"] in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                record["exclusion_criteria"] = (
                    record["exclusion_criteria"]
                    .replace(f"{criterion_to_delete}=TODO", "")
                    .replace(f"{criterion_to_delete}=yes", "")
                    .replace(f"{criterion_to_delete}=no", "")
                    .replace(";;", ";")
                    .lstrip(";")
                    .rstrip(";")
                )
                # Note : colrev_status does not change
                # because the other exclusion criteria do not change

            if record["colrev_status"] in [RecordState.rev_excluded]:
                record["exclusion_criteria"] = (
                    record["exclusion_criteria"]
                    .replace(f"{criterion_to_delete}=TODO", "")
                    .replace(f"{criterion_to_delete}=yes", "")
                    .replace(f"{criterion_to_delete}=no", "")
                    .replace(";;", ";")
                    .lstrip(";")
                    .rstrip(";")
                )
                # TODO : double-check if we go for inclusion criteria
                if (
                    "=yes" not in record["exclusion_criteria"]
                    and "=TODO" not in record["exclusion_criteria"]
                ):
                    record["colrev_status"] = RecordState.rev_included

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg=f"Removed screening criterion: {criterion_to_delete}",
            script_call="colrev screen",
        )

        return

    def create_screen_split(self, *, create_split: int) -> list:
        import math

        screen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.REVIEW_MANAGER.report_logger.info(
            f"Creating screen splits for {create_split} researchers " f"({nrecs} each)"
        )

        added: typing.List[str] = []
        for i in range(0, create_split):
            while len(added) < nrecs:
                added.append(next(data["items"])["ID"])
        screen_splits.append("colrev screen --split " + ",".join(added))

        return screen_splits

    def setup_custom_script(self) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, "template/custom_screen_script.py")
        if filedata:
            with open("custom_screen_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_screen_script.py")

        self.REVIEW_MANAGER.settings.screen.scripts.append(
            {"endpoint": "custom_screen_script"}
        )
        self.REVIEW_MANAGER.save_settings()

        return

    def main(self, *, split_str: str):

        split = []
        if split_str != "NA":
            split = split_str.split(",")
            split.remove("")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for SCREEN_SCRIPT in self.REVIEW_MANAGER.settings.screen.scripts:

            ENDPOINT = self.screen_scripts[SCREEN_SCRIPT["endpoint"]]
            records = ENDPOINT.run_screen(self, records, split)

        return


if __name__ == "__main__":
    pass
