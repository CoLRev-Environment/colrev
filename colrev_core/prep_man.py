#! /usr/bin/env python
import typing

import pandas as pd

import colrev_core.built_in.prep_man as built_in_prep_man
import colrev_core.process
import colrev_core.record


class PrepMan(colrev_core.process.Process):

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
        "colrev_cli_man_prep": {
            "endpoint": built_in_prep_man.CoLRevCLIManPrep,
        },
        "export_man_prep": {
            "endpoint": built_in_prep_man.ExportManPrep,
        },
        "prep_man_curation_jupyter": {
            "endpoint": built_in_prep_man.CurationJupyterNotebookManPrep,
        },
    }

    def __init__(self, *, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.prep_man,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        AdapterManager = self.REVIEW_MANAGER.get_environment_service(
            service_identifier="AdapterManager"
        )
        self.prep_man_scripts: typing.Dict[
            str, typing.Any
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.prep.man_prep_scripts,
        )

    def prep_man_stats(self) -> None:
        # pylint: disable=duplicate-code

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['RECORDS_FILE_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        self.REVIEW_MANAGER.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}
        overall_types: dict = {"ENTRYTYPE": {}}
        prep_man_hints = []
        origins = []
        crosstab = []
        for record in records.values():
            if colrev_core.record.RecordState.md_imported != record["colrev_status"]:
                if record["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                        overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                    )
                else:
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if (
                colrev_core.record.RecordState.md_needs_manual_preparation
                != record["colrev_status"]
            ):
                continue

            if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if "colrev_masterdata_provenance" in record:
                RECORD = colrev_core.record.Record(data=record)
                prov_d = RECORD.data["colrev_masterdata_provenance"]
                hints = []
                for k, v in prov_d.items():
                    if v["note"] != "":
                        hints.append(f'{k} - {v["note"]}')

                prep_man_hints.append([hint.lstrip() for hint in hints])
                for hint in hints:
                    if "change-score" in hint:
                        continue
                    # Note: if something causes the needs_manual_preparation
                    # it is caused by all colrev_origins
                    for orig in record.get("colrev_origin", "NA").split(";"):
                        crosstab.append([orig[: orig.rfind("/")], hint.lstrip()])

            origins.append(
                [
                    x[: x.rfind("/")]
                    for x in record.get("colrev_origin", "NA").split(";")
                ]
            )

        crosstab_df = pd.DataFrame(crosstab, columns=["colrev_origin", "hint"])

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            # pylint: disable=duplicate-code
            tabulated = pd.pivot_table(
                crosstab_df[["colrev_origin", "hint"]],
                index=["colrev_origin"],
                columns=["hint"],
                aggfunc=len,
                fill_value=0,
                margins=True,
            )
            # .sort_index(axis='columns')
            tabulated.sort_values(by=["All"], ascending=False, inplace=True)
            # Transpose because we tend to have more error categories than search files.
            tabulated = tabulated.transpose()
            print(tabulated)
            self.REVIEW_MANAGER.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_preparation_statistics.csv")

        print("Entry type statistics overall:")
        self.REVIEW_MANAGER.pp.pprint(overall_types["ENTRYTYPE"])

        print("Entry type statistics (needs_manual_preparation):")
        self.REVIEW_MANAGER.pp.pprint(stats["ENTRYTYPE"])

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev_core.record.RecordState.md_needs_manual_preparation)
                == x["colrev_status"]
            ]
        )

        all_ids = [x["ID"] for x in record_state_list]

        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[
                {
                    "colrev_status": colrev_core.record.RecordState.md_needs_manual_preparation
                }
            ]
        )

        md_prep_man_data = {
            "nr_tasks": nr_tasks,
            "items": items,
            "all_ids": all_ids,
            "PAD": PAD,
        }
        self.REVIEW_MANAGER.logger.debug(
            self.REVIEW_MANAGER.pp.pformat(md_prep_man_data)
        )
        return md_prep_man_data

    def set_data(self, *, record, PAD: int = 40) -> None:

        RECORD = colrev_core.record.PrepRecord(data=record)
        RECORD.set_masterdata_complete()
        RECORD.set_masterdata_consistent()
        RECORD.set_fields_complete()
        RECORD.set_status(target_state=colrev_core.record.RecordState.md_prepared)
        record = RECORD.get_data()

        self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(new_record=record)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

    def main(self) -> None:

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for PREP_MAN_SCRIPT in self.REVIEW_MANAGER.settings.prep.man_prep_scripts:

            ENDPOINT = self.prep_man_scripts[PREP_MAN_SCRIPT["endpoint"]]
            records = ENDPOINT.prepare_manual(self, records)


if __name__ == "__main__":
    pass
