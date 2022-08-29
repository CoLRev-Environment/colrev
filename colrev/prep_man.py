#! /usr/bin/env python
import typing

import pandas as pd

import colrev.built_in.prep_man as built_in_prep_man
import colrev.process
import colrev.record


class PrepMan(colrev.process.Process):

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

    def __init__(self, *, review_manager, notify_state_transition_process: bool = True):
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.prep_man,
            notify_state_transition_process=notify_state_transition_process,
        )

        self.verbose = True

        adapter_manager = self.review_manager.get_adapter_manager()
        self.prep_man_scripts: typing.Dict[
            str, typing.Any
        ] = adapter_manager.load_scripts(
            PROCESS=self,
            scripts=review_manager.settings.prep.man_prep_scripts,
        )

    def prep_man_stats(self) -> None:
        # pylint: disable=duplicate-code

        self.review_manager.logger.info(
            f"Load {self.review_manager.paths['RECORDS_FILE_RELATIVE']}"
        )
        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}
        overall_types: dict = {"ENTRYTYPE": {}}
        prep_man_hints = []
        origins = []
        crosstab = []
        for record_dict in records.values():
            if colrev.record.RecordState.md_imported != record_dict["colrev_status"]:
                if record_dict["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                    overall_types["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = (
                        overall_types["ENTRYTYPE"][record_dict["ENTRYTYPE"]] + 1
                    )
                else:
                    overall_types["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = 1

            if (
                colrev.record.RecordState.md_needs_manual_preparation
                != record_dict["colrev_status"]
            ):
                continue

            if record_dict["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = 1

            if "colrev_masterdata_provenance" in record_dict:
                record = colrev.record.Record(data=record_dict)
                prov_d = record.data["colrev_masterdata_provenance"]
                hints = []
                for key, value in prov_d.items():
                    if value["note"] != "":
                        hints.append(f'{key} - {value["note"]}')

                prep_man_hints.append([hint.lstrip() for hint in hints])
                for hint in hints:
                    if "change-score" in hint:
                        continue
                    # Note: if something causes the needs_manual_preparation
                    # it is caused by all colrev_origins
                    for orig in record_dict.get("colrev_origin", "NA").split(";"):
                        crosstab.append([orig[: orig.rfind("/")], hint.lstrip()])

            origins.append(
                [
                    x[: x.rfind("/")]
                    for x in record_dict.get("colrev_origin", "NA").split(";")
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
            self.review_manager.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_preparation_statistics.csv")

        print("Entry type statistics overall:")
        self.review_manager.p_printer.pprint(overall_types["ENTRYTYPE"])

        print("Entry type statistics (needs_manual_preparation):")
        self.review_manager.p_printer.pprint(stats["ENTRYTYPE"])

    def get_data(self) -> dict:

        record_state_list = self.review_manager.dataset.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev.record.RecordState.md_needs_manual_preparation)
                == x["colrev_status"]
            ]
        )

        all_ids = [x["ID"] for x in record_state_list]

        pad = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)

        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {"colrev_status": colrev.record.RecordState.md_needs_manual_preparation}
            ]
        )

        md_prep_man_data = {
            "nr_tasks": nr_tasks,
            "items": items,
            "all_ids": all_ids,
            "PAD": pad,
        }
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(md_prep_man_data)
        )
        return md_prep_man_data

    def set_data(self, *, record_dict, pad: int = 40) -> None:

        record = colrev.record.PrepRecord(data=record_dict)
        record.set_masterdata_complete()
        record.set_masterdata_consistent()
        record.set_fields_complete()
        record.set_status(target_state=colrev.record.RecordState.md_prepared)
        record_dict = record.get_data()

        self.review_manager.dataset.update_record_by_id(new_record=record_dict)
        self.review_manager.dataset.add_record_changes()

    def main(self) -> None:

        records = self.review_manager.dataset.load_records_dict()

        for prep_man_script in self.review_manager.settings.prep.man_prep_scripts:

            endpoint = self.prep_man_scripts[prep_man_script["endpoint"]]
            records = endpoint.prepare_manual(self, records)


if __name__ == "__main__":
    pass
