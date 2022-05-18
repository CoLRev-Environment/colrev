#! /usr/bin/env python
from pathlib import Path

import pandas as pd

from colrev_core import prep
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import RecordState


class PrepMan(Process):
    def __init__(self, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER,
            ProcessType.prep_man,
            notify_state_transition_process=notify_state_transition_process,
        )

    def prep_man_stats(self) -> None:
        from colrev_core.record import Record

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        self.REVIEW_MANAGER.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}
        overall_types: dict = {"ENTRYTYPE": {}}
        prep_man_hints = []
        origins = []
        crosstab = []
        for record in records.values():
            if RecordState.md_imported != record["colrev_status"]:
                if record["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                        overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                    )
                else:
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if RecordState.md_needs_manual_preparation != record["colrev_status"]:
                continue

            if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if "colrev_masterdata_provenance" in record:
                RECORD = Record(record)
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

        return

    def extract_needs_prep_man(self) -> None:

        prep_bib_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path(
            "prep-references.bib"
        )
        prep_csv_path = self.REVIEW_MANAGER.paths["REPO_DIR"] / Path(
            "prep-references.csv"
        )

        if prep_csv_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_csv_path})")
            return

        if prep_bib_path.is_file():
            print(f"Please rename file to avoid overwriting changes ({prep_bib_path})")
            return

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        records = {
            id: record
            for id, record in records.items()
            if RecordState.md_needs_manual_preparation == record["colrev_status"]
        }

        self.REVIEW_MANAGER.REVIEW_DATASEt.save_records_dict_to_file(
            records, save_path=prep_bib_path
        )

        bib_db_df = pd.DataFrame.from_records(records.values())

        col_names = [
            "ID",
            "colrev_origin",
            "author",
            "title",
            "year",
            "journal",
            # "booktitle",
            "volume",
            "number",
            "pages",
            "doi",
        ]
        for col_name in col_names:
            if col_name not in bib_db_df:
                bib_db_df[col_name] = "NA"
        bib_db_df = bib_db_df[col_names]

        bib_db_df.to_csv(prep_csv_path, index=False)
        self.REVIEW_MANAGER.logger.info(f"Created {prep_csv_path.name}")

        return

    def apply_prep_man(self) -> None:

        PREPARATION = prep.Preparation(self.REVIEW_MANAGER)

        if Path("prep-references.csv").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-references.csv")
            bib_db_df = pd.read_csv("prep-references.csv")
            records_changed = bib_db_df.to_dict("records")
        if Path("prep-references.bib").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-references.bib")

            with open("prep-references.bib") as target_db:
                records_changed_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
                    load_str=target_db.read()
                )

                records_changed = records_changed_dict.values()

        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        revlist = (
            ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )

        filecontents_current_commit = next(revlist)  # noqa
        filecontents = next(revlist)

        prior_records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records(
            load_str=filecontents.decode("utf-8")
        )
        prior_records = prior_records_dict.values()

        records_to_reset = []
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for record in records.values():
            # IDs may change - matching based on origins
            changed_record_l = [
                x
                for x in records_changed
                if x["colrev_origin"] == record["colrev_origin"]
            ]
            if len(changed_record_l) == 1:
                changed_record = changed_record_l.pop()
                for k, v in changed_record.items():
                    # if record['ID'] == 'Alter2014':
                    #     print(k, v)
                    if str(v) == "nan":
                        if k in record:
                            del record[k]
                        continue
                    record[k] = v
                    if v == "":
                        del record[k]
                    if v == "RESET":
                        prior_record_l = [
                            x
                            for x in prior_records
                            if x["colrev_origin"] == record["colrev_origin"]
                        ]
                        if len(prior_record_l) == 1:
                            prior_record = prior_record_l.pop()
                            record[k] = prior_record[k]
                    if v == "UNMERGE":
                        records_to_reset.append(record)

        if len(records_to_reset) > 0:
            PREPARATION.reset(records_to_reset)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
        self.REVIEW_MANAGER.format_references()
        self.REVIEW_MANAGER.check_repo()
        return

    def append_to_non_dupe_db(
        self, record_to_unmerge_original: dict, record_original: dict
    ):

        record_to_unmerge = record_to_unmerge_original.copy()
        record = record_original.copy()

        non_dupe_db_path = Path.home().joinpath("colrev") / Path("non_duplicates.bib")

        non_dupe_db_path.parents[0].mkdir(parents=True, exist_ok=True)

        if non_dupe_db_path.is_file():

            with open(non_dupe_db_path) as target_db:

                non_dupe_recs_dict = (
                    self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                        target_db.read()
                    )
                )

            max_id = max([int(ID) for ID in non_dupe_recs_dict.keys()] + [1]) + 1
        else:
            non_dupe_recs_dict = dict()
            max_id = 1

        record_to_unmerge["ID"] = str(max_id).rjust(9, "0")
        max_id += 1
        record["ID"] = str(max_id).rjust(9, "0")

        record_to_unmerge = {k: str(v) for k, v in record_to_unmerge.items()}
        record = {k: str(v) for k, v in record.items()}

        del record_to_unmerge["colrev_origin"]
        del record["colrev_origin"]
        del record_to_unmerge["colrev_status"]
        del record["colrev_status"]

        non_dupe_recs_dict[record_to_unmerge["ID"]] = record_to_unmerge
        non_dupe_recs_dict[record["ID"]] = record

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(
            non_dupe_recs_dict, save_path=non_dupe_db_path
        )

        return

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.md_needs_manual_preparation) == x["colrev_status"]
            ]
        )

        all_ids = [x["ID"] for x in record_state_list]

        PAD = min((max(len(x["ID"]) for x in record_state_list) + 2), 35)

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"colrev_status": RecordState.md_needs_manual_preparation}]
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

    def set_data(self, record, PAD: int = 40) -> None:
        from colrev_core.record import Record

        PREPARATION = prep.Preparation(self.REVIEW_MANAGER)
        record.update(colrev_status=RecordState.md_prepared)
        RECORD = Record(record)
        RECORD.set_masterdata_complete()
        RECORD.set_masterdata_consistent()
        RECORD.set_fields_complete()
        record = RECORD.get_data()
        record = PREPARATION.drop_fields(record)

        self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(record)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return


if __name__ == "__main__":
    pass
