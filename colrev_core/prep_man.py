#! /usr/bin/env python
from pathlib import Path

import bibtexparser
import pandas as pd

from colrev_core import prep
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState


class PrepMan(Process):
    def __init__(self, REVIEW_MANAGER, notify_state_transition_process: bool = True):
        super().__init__(
            REVIEW_MANAGER,
            ProcessType.prep_man,
            notify_state_transition_process=notify_state_transition_process,
        )

    def prep_man_stats(self) -> None:

        self.REVIEW_MANAGER.logger.info(
            f"Load {self.REVIEW_MANAGER.paths['MAIN_REFERENCES_RELATIVE']}"
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        self.REVIEW_MANAGER.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}
        overall_types: dict = {"ENTRYTYPE": {}}
        prep_man_hints = []
        origins = []
        crosstab = []
        for record in records:
            if RecordState.md_imported != record["status"]:
                if record["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                        overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                    )
                else:
                    overall_types["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if RecordState.md_needs_manual_preparation != record["status"]:
                continue

            if record["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record["ENTRYTYPE"]] = 1

            if "man_prep_hints" in record:
                hints = record["man_prep_hints"].split(";")
                prep_man_hints.append([hint.lstrip() for hint in hints])
                for hint in hints:
                    if "change-score" in hint:
                        continue
                    # Note: if something causes the needs_manual_preparation
                    # it is caused by all origins
                    for orig in record.get("origin", "NA").split(";"):
                        crosstab.append([orig[: orig.rfind("/")], hint.lstrip()])

            origins.append(
                [x[: x.rfind("/")] for x in record.get("origin", "NA").split(";")]
            )

        crosstab_df = pd.DataFrame(crosstab, columns=["origin", "hint"])

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            tabulated = pd.pivot_table(
                crosstab_df[["origin", "hint"]],
                index=["origin"],
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

        # TODO : these should be combined in one dict and returned:
        print("Entry type statistics overall:")
        self.REVIEW_MANAGER.pp.pprint(overall_types["ENTRYTYPE"])

        print("Entry type statistics (needs_manual_preparation):")
        self.REVIEW_MANAGER.pp.pprint(stats["ENTRYTYPE"])

        return

    def extract_needs_prep_man(self) -> None:
        from bibtexparser.bibdatabase import BibDatabase

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
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()

        records = [
            record
            for record in records
            if RecordState.md_needs_manual_preparation == record["status"]
        ]

        # Casting to string (in particular the RecordState Enum)
        records = [{k: str(v) for k, v in r.items()} for r in records]

        bib_db = BibDatabase()
        bib_db.entries = records
        bibtex_str = bibtexparser.dumps(bib_db)
        with open(prep_bib_path, "w") as out:
            out.write(bibtex_str)

        bib_db_df = pd.DataFrame.from_records(records)

        col_names = [
            "ID",
            "origin",
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
            bib_db_changed = bib_db_df.to_dict("records")
        if Path("prep-references.bib").is_file():
            self.REVIEW_MANAGER.logger.info("Load prep-references.bib")

            from bibtexparser.bparser import BibTexParser
            from bibtexparser.customization import convert_to_unicode

            with open("prep-references.bib") as target_db:
                bib_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(target_db, partial=True)

                bib_db_changed = bib_db.entries

        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        revlist = (
            ((commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read())
            for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
        )

        filecontents_current_commit = next(revlist)  # noqa
        filecontents = next(revlist)
        prior_bib_db = bibtexparser.loads(filecontents)
        prior_records = prior_bib_db.entries

        records_to_reset = []
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records()
        for record in records:
            # IDs may change - matching based on origins
            changed_record_l = [
                x for x in bib_db_changed if x["origin"] == record["origin"]
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
                            x for x in prior_records if x["origin"] == record["origin"]
                        ]
                        if len(prior_record_l) == 1:
                            prior_record = prior_record_l.pop()
                            record[k] = prior_record[k]
                    if v == "UNMERGE":
                        records_to_reset.append(record)

        if len(records_to_reset) > 0:
            PREPARATION.reset(records_to_reset)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records(records)
        self.REVIEW_MANAGER.format_references()
        self.REVIEW_MANAGER.check_repo()
        return

    def append_to_non_dupe_db(
        self, record_to_unmerge_original: dict, record_original: dict
    ):
        from bibtexparser.bibdatabase import BibDatabase
        from bibtexparser.bparser import BibTexParser
        from bibtexparser.customization import convert_to_unicode

        record_to_unmerge = record_to_unmerge_original.copy()
        record = record_original.copy()

        non_dupe_db_path = Path.home().joinpath(".colrev") / Path("non_duplicates.bib")

        non_dupe_db_path.parents[0].mkdir(parents=True, exist_ok=True)

        if non_dupe_db_path.is_file():

            with open(non_dupe_db_path) as target_db:
                non_dupe_db = BibTexParser(
                    customization=convert_to_unicode,
                    ignore_nonstandard_types=False,
                    common_strings=True,
                ).parse_file(target_db, partial=True)

            max_id = max([int(x["ID"]) for x in non_dupe_db.entries] + [1]) + 1
        else:
            non_dupe_db = BibDatabase()
            max_id = 1

        record_to_unmerge["ID"] = str(max_id).rjust(9, "0")
        max_id += 1
        record["ID"] = str(max_id).rjust(9, "0")
        record_to_unmerge["manual_non_duplicate"] = record["ID"]
        record["manual_non_duplicate"] = record_to_unmerge["ID"]

        record_to_unmerge = {k: str(v) for k, v in record_to_unmerge.items()}
        record = {k: str(v) for k, v in record.items()}

        del record_to_unmerge["origin"]
        del record["origin"]
        del record_to_unmerge["status"]
        del record["status"]
        if "man_prep_hints" in record_to_unmerge:
            del record_to_unmerge["man_prep_hints"]
        if "man_prep_hints" in record:
            del record["man_prep_hints"]

        non_dupe_db.entries.append(record_to_unmerge)
        non_dupe_db.entries.append(record)
        bibtex_str = bibtexparser.dumps(non_dupe_db)

        with open(non_dupe_db_path, "w") as out:
            out.write(bibtex_str)

        return

    def get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.md_needs_manual_preparation) == x[1]
            ]
        )

        all_ids = [x[0] for x in record_state_list]

        PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"status": RecordState.md_needs_manual_preparation}]
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

        PREPARATION = prep.Preparation(self.REVIEW_MANAGER)

        record.update(status=RecordState.md_prepared)
        record.update(metadata_source="MAN_PREP")
        record = PREPARATION.drop_fields(record)

        self.REVIEW_MANAGER.REVIEW_DATASET.update_record_by_ID(record)

        # TODO : maybe update the IDs when we have a replace_record procedure
        # set_IDs
        # that can handle changes in IDs
        # record.update(
        #     ID=REVIEW_MANAGER.generate_ID_blacklist(
        #         record, all_ids, record_in_bib_db=True, raise_error=False
        #     )
        # )
        # all_ids.append(record["ID"])

        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        return


if __name__ == "__main__":
    pass
