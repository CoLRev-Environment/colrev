#! /usr/bin/env python
import math
import pkgutil
import typing

import colrev.process
import colrev.record
import colrev.settings
from colrev.built_in import screen as built_in_screen


class Screen(colrev.process.Process):

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "colrev_cli_screen": {
            "endpoint": built_in_screen.CoLRevCLIScreenEndpoint,
        },
        "spreadsheed_screen": {"endpoint": built_in_screen.SpreadsheetScreenEndpoint},
        # "conditional_screen": {"endpoint": built_in_screen.ConditionalScreenEndpoint},
    }

    def __init__(self, *, review_manager, notify_state_transition_process: bool = True):
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.screen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        adapter_manager = self.review_manager.get_adapter_manager()
        self.screen_scripts: typing.Dict[
            str, typing.Any
        ] = adapter_manager.load_scripts(
            PROCESS=self,
            scripts=review_manager.settings.screen.scripts,
        )

    def include_all_in_screen(
        self,
    ) -> None:
        """Include all records in the screen"""

        records = self.review_manager.dataset.load_records_dict()

        screening_criteria = self.get_screening_criteria()

        saved_args = locals()
        saved_args["include_all"] = ""
        pad = 50
        for record_id, record in records.items():
            if record["colrev_status"] != colrev.record.RecordState.pdf_prepared:
                continue
            self.review_manager.report_logger.info(
                f" {record_id}".ljust(pad, " ") + "Included in screen (automatically)"
            )
            if len(screening_criteria) == 0:
                record.update(screening_criteria="NA")
            else:
                record.update(
                    screening_criteria=";".join([e + "=in" for e in screening_criteria])
                )
            record.update(colrev_status=colrev.record.RecordState.rev_included)

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Screen (include_all)",
            manual_author=False,
            script_call="colrev screen",
            saved_args=saved_args,
        )

    def get_screening_criteria(self) -> list:
        """Get the list of screening criteria from settings"""

        return list(self.review_manager.settings.screen.criteria.keys())

    def set_screening_criteria(self, *, screening_criteria) -> None:
        self.review_manager.settings.screen.criteria = screening_criteria
        self.review_manager.save_settings()

    def get_data(self) -> dict:
        """Get the data (records to screen)"""

        record_state_list = self.review_manager.dataset.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev.record.RecordState.pdf_prepared) == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)
        items = self.review_manager.dataset.read_next_record(
            conditions=[{"colrev_status": colrev.record.RecordState.pdf_prepared}]
        )
        screen_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(screen_data)
        )
        return screen_data

    def add_criterion(self, *, criterion_to_add) -> None:
        """Add a screening criterion to the records and settings"""

        assert criterion_to_add.count(",") == 2
        criterion_name, criterion_type, criterion_explanation = criterion_to_add.split(
            ","
        )
        records = self.review_manager.dataset.load_records_dict()

        if criterion_name not in self.review_manager.settings.screen.criteria:

            add_criterion = colrev.settings.ScreenCriterion(
                explanation=criterion_explanation,
                criterion_type=criterion_type,
                comment="",
            )
            self.review_manager.settings.screen.criteria[criterion_name] = add_criterion

            self.review_manager.save_settings()
            self.review_manager.dataset.add_setting_changes()
        else:
            print(f"Error: criterion {criterion_name} already in settings")
            return

        for record in records.values():

            if record["colrev_status"] in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                record["screening_criteria"] += f";{criterion_name}=TODO"
                # Note : we set the status to pdf_prepared because the screening
                # decisions have to be updated (resulting in inclusion or exclusion)
                record["colrev_status"] = colrev.record.RecordState.pdf_prepared
            if record["colrev_status"] == colrev.record.RecordState.rev_excluded:
                record["screening_criteria"] += f";{criterion_name}=TODO"
                # Note : no change in colrev_status
                # because at least one of the other criteria led to exclusion decision

        # TODO : screening: if screening_criteria field is already available
        # only go through the criteria with "TODO"
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg=f"Add screening criterion: {criterion_name}",
            script_call="colrev screen",
        )

    def delete_criterion(self, *, criterion_to_delete) -> None:
        """Delete a screening criterion from the records and settings"""
        records = self.review_manager.dataset.load_records_dict()

        if criterion_to_delete in self.review_manager.settings.screen.criteria:
            del self.review_manager.settings.screen.criteria[criterion_to_delete]
            self.review_manager.save_settings()
            self.review_manager.dataset.add_setting_changes()
        else:
            print(f"Error: criterion {criterion_to_delete} not in settings")
            return

        for record in records.values():

            if record["colrev_status"] in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                record["screening_criteria"] = (
                    record["screening_criteria"]
                    .replace(f"{criterion_to_delete}=TODO", "")
                    .replace(f"{criterion_to_delete}=in", "")
                    .replace(f"{criterion_to_delete}=out", "")
                    .replace(";;", ";")
                    .lstrip(";")
                    .rstrip(";")
                )
                # Note : colrev_status does not change
                # because the other screening criteria do not change

            if record["colrev_status"] in [colrev.record.RecordState.rev_excluded]:
                record["screening_criteria"] = (
                    record["screening_criteria"]
                    .replace(f"{criterion_to_delete}=TODO", "")
                    .replace(f"{criterion_to_delete}=in", "")
                    .replace(f"{criterion_to_delete}=out", "")
                    .replace(";;", ";")
                    .lstrip(";")
                    .rstrip(";")
                )

                if (
                    "=out" not in record["screening_criteria"]
                    and "=TODO" not in record["screening_criteria"]
                ):
                    record["colrev_status"] = colrev.record.RecordState.rev_included

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg=f"Removed screening criterion: {criterion_to_delete}",
            script_call="colrev screen",
        )

    def create_screen_split(self, *, create_split: int) -> list:

        screen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.review_manager.report_logger.info(
            f"Creating screen splits for {create_split} researchers " f"({nrecs} each)"
        )

        added: typing.List[str] = []
        while len(added) < nrecs:
            added.append(next(data["items"])["ID"])
        screen_splits.append("colrev screen --split " + ",".join(added))

        return screen_splits

    def setup_custom_script(self) -> None:

        filedata = pkgutil.get_data(__name__, "template/custom_screen_script.py")
        if filedata:
            with open("custom_screen_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path="custom_screen_script.py")

        self.review_manager.settings.screen.scripts.append(
            {"endpoint": "custom_screen_script"}
        )
        self.review_manager.save_settings()

    def main(self, *, split_str: str):

        # pylint: disable=duplicate-code
        split = []
        if split_str != "NA":
            split = split_str.split(",")
            split.remove("")

        records = self.review_manager.dataset.load_records_dict()

        for screen_script in self.review_manager.settings.screen.scripts:

            endpoint = self.screen_scripts[screen_script["endpoint"]]
            records = endpoint.run_screen(self, records, split)


if __name__ == "__main__":
    pass
