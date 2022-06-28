#! /usr/bin/env python
import importlib
import sys
import typing
from pathlib import Path

import zope.interface
from zope.interface.verify import verifyObject

from colrev_core.prescreen import PrescreenRecord
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class ScreenEndpoint(zope.interface.Interface):
    def run_screen(SCREEN, records: dict, split: list) -> dict:
        pass


@zope.interface.implementer(ScreenEndpoint)
class CoLRevCLIScreenEndpoint:
    @classmethod
    def run_screen(cls, SCREEN, records: dict, split: list) -> dict:
        from colrev.cli import screen_cli

        records = screen_cli(SCREEN, split)

        return records


@zope.interface.implementer(ScreenEndpoint)
class SpreadsheetScreenEndpoint:
    @classmethod
    def export_table(cls, SCREEN, records, split, export_table_format="csv") -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter
        import csv
        import pandas as pd

        SCREEN.REVIEW_MANAGER.logger.info("Loading records for export")

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            inclusion_2 = "NA"

            if RecordState.pdf_prepared == record["colrev_status"]:
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
                "screen_inclusion": inclusion_2,
                "exclusion_criteria": exclusion_criteria,
            }
            # row.update    (exclusion_criteria)
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("screen.csv", index=False, quoting=csv.QUOTE_ALL)
            SCREEN.REVIEW_MANAGER.logger.info("Created screen.csv")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("screen.xlsx", index=False, sheet_name="screen")
            SCREEN.REVIEW_MANAGER.logger.info("Created screen.xlsx")

        return

    @classmethod
    def import_table(cls, SCREEN, records, import_table_path="screen.csv") -> None:
        import pandas as pd

        if not Path(import_table_path).is_file():
            SCREEN.REVIEW_MANAGER.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        SCREEN.REVIEW_MANAGER.logger.warning(
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

        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        SCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        return

    @classmethod
    def run_screen(cls, SCREEN, records: dict, split: list) -> dict:

        if "y" == input("create screen spreadsheet [y,n]?"):
            cls.export_table(SCREEN, records, split)

        if "y" == input("import screen spreadsheet [y,n]?"):
            cls.import_table(SCREEN, records)

        if SCREEN.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            if "y" == input("create commit [y,n]?"):
                SCREEN.REVIEW_MANAGER.create_commit(msg="Screen", manual_author=True)
        return records


class ScreenRecord(PrescreenRecord):

    # Note : currently still identical with PrescreenRecord
    def __init__(self, data: dict):
        super().__init__(data=data)


class Screen(Process):
    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.screen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        self.screen_endpoints: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "colrev_cli_screen": {
                "endpoint": CoLRevCLIScreenEndpoint,
            },
            "spreadsheed_screen": {"endpoint": SpreadsheetScreenEndpoint},
            # "conditional_screen": {"endpoint": ConditionalScreenEndpoint},
        }

        list_custom_scripts = [
            s["endpoint"]
            for s in REVIEW_MANAGER.settings.screen.scripts
            if s["endpoint"] not in self.screen_endpoints
            and Path(s["endpoint"] + ".py").is_file()
        ]
        sys.path.append(".")  # to import custom scripts from the project dir
        for plugin_script in list_custom_scripts:
            custom_screen_script = importlib.import_module(
                plugin_script, "."
            ).CustomScreen
            verifyObject(ScreenEndpoint, custom_screen_script())
            self.screen_endpoints[plugin_script] = {"endpoint": custom_screen_script}

        # TODO : test the module screen_scripts
        list_module_scripts = [
            s["endpoint"]
            for s in REVIEW_MANAGER.settings.screen.scripts
            if s["endpoint"] not in self.screen_endpoints
            and not Path(s["endpoint"] + ".py").is_file()
        ]
        for plugin_script in list_module_scripts:
            try:
                custom_screen_script = importlib.import_module(
                    plugin_script
                ).CustomScreen
                verifyObject(ScreenEndpoint, custom_screen_script())
                self.screen_endpoints[plugin_script] = {
                    "endpoint": custom_screen_script
                }
            except ModuleNotFoundError:
                pass
                # raise MissingDependencyError
                print(
                    "Dependency screen_script " + f"{plugin_script} not found. "
                    "Please install it\n  pip install "
                    f"{plugin_script}"
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
            msg="Screen (include_all)", manual_author=False, saved_args=saved_args
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
            msg=f"Add screening criterion: {criterion_name}"
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
            msg=f"Removed screening criterion: {criterion_to_delete}"
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

            if SCREEN_SCRIPT["endpoint"] not in list(self.screen_endpoints.keys()):
                if self.verbose:
                    print(f"Error: endpoint not available: {SCREEN_SCRIPT}")
                continue

            endpoint = self.screen_endpoints[SCREEN_SCRIPT["endpoint"]]

            ENDPOINT = endpoint["endpoint"]()
            records = ENDPOINT.run_screen(self, records, split)

        return


if __name__ == "__main__":
    pass
