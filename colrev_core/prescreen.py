#! /usr/bin/env python
import csv
import importlib
import sys
import typing
from pathlib import Path

import pandas as pd
import zope.interface
from zope.interface.verify import verifyObject

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


class PrescreenEndpoint(zope.interface.Interface):
    def run_prescreen(PRESCREEN, records: dict, split: list) -> dict:
        pass


@zope.interface.implementer(PrescreenEndpoint)
class ScopePrescreenEndpoint:

    # TODO : move the scope settings to the parameters of this endpoint

    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        from colrev_core.settings import (
            TimeScopeFrom,
            TimeScopeTo,
            OutletInclusionScope,
            OutletExclusionScope,
            ENTRYTYPEScope,
            ComplementaryMaterialsScope,
        )

        def load_predatory_journals_beal() -> dict:

            import pkgutil

            predatory_journals = {}

            filedata = pkgutil.get_data(
                __name__, "template/predatory_journals_beall.csv"
            )
            if filedata:
                for pj in filedata.decode("utf-8").splitlines():
                    predatory_journals[pj.lower()] = pj.lower()

            return predatory_journals

        predatory_journals_beal = load_predatory_journals_beal()

        saved_args = locals()
        PAD = 50
        for record in records.values():
            if record["colrev_status"] != RecordState.md_processed:
                continue

            # Note : LanguageScope is covered in prep
            # because dedupe cannot handle merges between languages

            for scope_restriction in PRESCREEN.REVIEW_MANAGER.settings.prescreen.scope:

                if isinstance(scope_restriction, ENTRYTYPEScope):
                    if record["ENTRYTYPE"] not in scope_restriction.ENTRYTYPEScope:
                        Record(data=record).prescreen_exclude(
                            reason="not in ENTRYTYPEScope"
                        )

                if isinstance(scope_restriction, OutletExclusionScope):
                    if "values" in scope_restriction.OutletExclusionScope:
                        for r in scope_restriction.OutletExclusionScope["values"]:
                            for key, value in r.items():
                                if key in record and record.get(key, "") == value:
                                    Record(data=record).prescreen_exclude(
                                        reason="in OutletExclusionScope"
                                    )
                    if "list" in scope_restriction.OutletExclusionScope:
                        for r in scope_restriction.OutletExclusionScope["list"]:
                            for key, value in r.items():
                                if (
                                    "resource" == key
                                    and "predatory_journals_beal" == value
                                ):
                                    if "journal" in record:
                                        if (
                                            record["journal"].lower()
                                            in predatory_journals_beal
                                        ):
                                            Record(data=record).prescreen_exclude(
                                                reason="predatory_journals_beal"
                                            )

                if isinstance(scope_restriction, TimeScopeFrom):
                    if int(record.get("year", 0)) < scope_restriction.TimeScopeFrom:
                        Record(data=record).prescreen_exclude(
                            reason="not in TimeScopeFrom "
                            f"(>{scope_restriction.TimeScopeFrom})"
                        )

                if isinstance(scope_restriction, TimeScopeTo):
                    if int(record.get("year", 5000)) > scope_restriction.TimeScopeTo:
                        Record(data=record).prescreen_exclude(
                            reason="not in TimeScopeTo "
                            f"(<{scope_restriction.TimeScopeTo})"
                        )

                if isinstance(scope_restriction, OutletInclusionScope):
                    in_outlet_scope = False
                    if "values" in scope_restriction.OutletInclusionScope:
                        for r in scope_restriction.OutletInclusionScope["values"]:
                            for key, value in r.items():
                                if key in record and record.get(key, "") == value:
                                    in_outlet_scope = True
                    if not in_outlet_scope:
                        Record(data=record).prescreen_exclude(
                            reason="not in OutletInclusionScope"
                        )

                # TODO : discuss whether we should move this to the prep scripts
                if isinstance(scope_restriction, ComplementaryMaterialsScope):
                    if scope_restriction.ComplementaryMaterialsScope:
                        if "title" in record:
                            # TODO : extend/test the following
                            if record["title"].lower() in [
                                "about our authors",
                                "editorial board",
                                "author index",
                                "contents",
                                "index of authors",
                                "list of reviewers",
                            ]:
                                Record(data=record).prescreen_exclude(
                                    reason="complementary material"
                                )

            if record["colrev_status"] != RecordState.rev_prescreen_excluded:
                PRESCREEN.REVIEW_MANAGER.report_logger.info(
                    f' {record["ID"]}'.ljust(PAD, " ")
                    + "Prescreen excluded (automatically)"
                )

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        PRESCREEN.REVIEW_MANAGER.create_commit(
            msg="Pre-screen (scope)", manual_author=False, saved_args=saved_args
        )
        return records


@zope.interface.implementer(PrescreenEndpoint)
class CoLRevCLIPrescreenEndpoint:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        from colrev.cli import prescreen_cli

        records = prescreen_cli(PRESCREEN, split)
        return records


@zope.interface.implementer(PrescreenEndpoint)
class ASReviewPrescreenEndpoint:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        print("TODO")
        return records


@zope.interface.implementer(PrescreenEndpoint)
class ConditionalPrescreenEndpoint:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        # TODO : conditions as a settings/parameter
        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50
        for record in records.values():
            if record["colrev_status"] != RecordState.md_processed:
                continue
            PRESCREEN.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "Included in prescreen (automatically)"
            )
            record.update(colrev_status=RecordState.rev_prescreen_included)

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        PRESCREEN.REVIEW_MANAGER.create_commit(
            msg="Pre-screen (include_all)", manual_author=False, saved_args=saved_args
        )
        return records


@zope.interface.implementer(PrescreenEndpoint)
class SpreadsheetPrescreenEndpoint:
    @classmethod
    def export_table(cls, PRESCREEN, records, split, export_table_format="csv") -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter

        PRESCREEN.REVIEW_MANAGER.logger.info("Loading records for export")

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                RecordState.md_processed,
                RecordState.rev_prescreen_excluded,
                RecordState.rev_prescreen_included,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            if RecordState.md_processed == record["colrev_status"]:
                inclusion_1 = "TODO"
            elif RecordState.rev_prescreen_excluded == record["colrev_status"]:
                inclusion_1 = "no"
            else:
                inclusion_1 = "yes"

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
                "presceen_inclusion": inclusion_1,
            }
            # row.update    (exclusion_criteria)
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("prescreen.csv", index=False, quoting=csv.QUOTE_ALL)
            PRESCREEN.REVIEW_MANAGER.logger.info("Created prescreen.csv")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("prescreen.xlsx", index=False, sheet_name="screen")
            PRESCREEN.REVIEW_MANAGER.logger.info("Created prescreen.xlsx")

        return

    @classmethod
    def import_table(
        cls, PRESCREEN, records, import_table_path="prescreen.csv"
    ) -> None:
        if not Path(import_table_path).is_file():
            PRESCREEN.REVIEW_MANAGER.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        PRESCREEN.REVIEW_MANAGER.logger.warning(
            "import_table not completed (exclusion_criteria not yet imported)"
        )

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record = records[screened_record.get("ID", "")]
                if "no" == screened_record.get("inclusion_1", ""):
                    record["colrev_status"] = RecordState.rev_prescreen_excluded
                if "yes" == screened_record.get("inclusion_1", ""):
                    record["colrev_status"] = RecordState.rev_prescreen_included

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        return

    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:

        if "y" == input("create prescreen spreadsheet [y,n]?"):
            cls.export_table(PRESCREEN, records, split)

        if "y" == input("import prescreen spreadsheet [y,n]?"):
            cls.import_table(PRESCREEN, records)

        if PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            if "y" == input("create commit [y,n]?"):
                PRESCREEN.REVIEW_MANAGER.create_commit(
                    msg="Pre-screen (spreadsheets)", manual_author=True
                )
        return records


class PrescreenRecord(Record):
    def __init__(self, *, data: dict):
        super().__init__(data=data)

    def __str__(self) -> str:

        self.identifying_keys_order = ["ID", "ENTRYTYPE"] + [
            k for k in self.identifying_field_keys if k in self.data
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
    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.prescreen,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        self.prescreen_endpoints: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "scope_prescreen": {
                "endpoint": ScopePrescreenEndpoint,
            },
            "colrev_cli_prescreen": {
                "endpoint": CoLRevCLIPrescreenEndpoint,
            },
            "asreview_prescreen": {
                "endpoint": ASReviewPrescreenEndpoint,
            },
            "conditional_prescreen": {"endpoint": ConditionalPrescreenEndpoint},
            "spreadsheed_prescreen": {"endpoint": SpreadsheetPrescreenEndpoint},
        }

        list_custom_scripts = [
            s["endpoint"]
            for s in REVIEW_MANAGER.settings.prescreen.scripts
            if s["endpoint"] not in self.prescreen_endpoints
            and Path(s["endpoint"] + ".py").is_file()
        ]
        sys.path.append(".")  # to import custom scripts from the project dir
        for plugin_script in list_custom_scripts:
            custom_prescreen_script = importlib.import_module(
                plugin_script, "."
            ).CustomPrescreen
            verifyObject(PrescreenEndpoint, custom_prescreen_script())
            self.prescreen_endpoints[plugin_script] = {
                "endpoint": custom_prescreen_script
            }

        # TODO : test the module prescreen_scripts
        list_module_scripts = [
            s["endpoint"]
            for s in REVIEW_MANAGER.settings.prescreen.scripts
            if s["endpoint"] not in self.prescreen_endpoints
            and not Path(s["endpoint"] + ".py").is_file()
        ]
        for plugin_script in list_module_scripts:
            try:
                custom_prescreen_script = importlib.import_module(
                    plugin_script
                ).CustomPrescreen
                verifyObject(PrescreenEndpoint, custom_prescreen_script())
                self.prescreen_endpoints[plugin_script] = {
                    "endpoint": custom_prescreen_script
                }
            except ModuleNotFoundError:
                pass
                # raise MissingDependencyError
                print(
                    "Dependency prescreen_script " + f"{plugin_script} not found. "
                    "Please install it\n  pip install "
                    f"{plugin_script}"
                )

    def export_table(self, *, export_table_format: str) -> None:
        ENDPOINT = SpreadsheetPrescreenEndpoint()
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.export_table(self, records, [])
        return

    def import_table(self, *, import_table_path: str) -> None:

        ENDPOINT = SpreadsheetPrescreenEndpoint()
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        ENDPOINT.import_table(self, records, import_table_path)

        return

    def include_all_in_prescreen(self) -> None:
        ENDPOINT = ConditionalPrescreenEndpoint()
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

    def set_data(
        self, *, record: dict, prescreen_inclusion: bool, PAD: int = 40
    ) -> None:

        if prescreen_inclusion:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Included in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                IDs=[record["ID"]],
                key="colrev_status",
                val_str=str(RecordState.rev_prescreen_included),
            )
        else:
            self.REVIEW_MANAGER.report_logger.info(
                f" {record['ID']}".ljust(PAD, " ") + "Excluded in prescreen"
            )
            self.REVIEW_MANAGER.REVIEW_DATASET.replace_field(
                IDs=[record["ID"]],
                key="colrev_status",
                val_str=str(RecordState.rev_prescreen_excluded),
            )

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return

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

            if PRESCREEN_SCRIPT["endpoint"] not in list(
                self.prescreen_endpoints.keys()
            ):
                if self.verbose:
                    print(f"Error: endpoint not available: {PRESCREEN_SCRIPT}")
                continue

            endpoint = self.prescreen_endpoints[PRESCREEN_SCRIPT["endpoint"]]

            ENDPOINT = endpoint["endpoint"]()
            records = ENDPOINT.run_prescreen(self, records, split)
        return


if __name__ == "__main__":
    pass
