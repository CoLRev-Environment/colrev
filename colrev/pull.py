#! /usr/bin/env python
import multiprocessing as mp
from multiprocessing import Value

from pathos.multiprocessing import ProcessPool
from tqdm import tqdm

import colrev.built_in.prep as built_in_prep
import colrev.cli_colors as colors
import colrev.prep
import colrev.process
import colrev.record


change_counter = None


class Pull(colrev.process.Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev.process.ProcessType.explore,
        )

    def main(self, *, records_only: bool = False, project_only: bool = False) -> None:

        if project_only:
            self.pull_project()
        elif records_only:
            self.pull_records_from_index()
            self.pull_records_from_crossref()
        else:
            self.pull_project()
            self.pull_records_from_index()
            self.pull_records_from_crossref()

    def pull_project(self) -> None:
        try:
            git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
            origin = git_repo.remotes.origin
            self.REVIEW_MANAGER.logger.info(
                f"Pull project changes from {git_repo.remotes.origin}"
            )
            res = origin.pull()
        except AttributeError:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.RED}No remote detected for pull{colors.END}"
            )
            return

        if 4 == res[0].flags:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.GREEN}Project up-to-date{colors.END}"
            )
        elif 64 == res[0].flags:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.GREEN}Updated CoLRev repository{colors.END}"
            )
        else:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.RED}Returned flag {res[0].flags}{colors.END}"
            )
        print()

    def pull_records_from_crossref(self) -> None:

        PREPARATION = colrev.prep.Preparation(
            REVIEW_MANAGER=self.REVIEW_MANAGER, notify_state_transition_process=False
        )

        CROSSREF_PREP = built_in_prep.CrossrefMetadataPrep(
            PREPARATION=PREPARATION, SETTINGS={"name": "local_index_prep"}
        )

        self.REVIEW_MANAGER.logger.info("Pull records from Crossref")

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        # pylint: disable=redefined-outer-name
        change_counter = Value("i", 0)
        for record in tqdm(records.values()):
            RECORD = colrev.record.PrepRecord(data=record)
            PREVIOUS_RECORD = RECORD.copy_prep_rec()
            # TODO : use masterdata_is_curated() for identifying_fields_keys only?
            if "doi" in RECORD.data and not RECORD.masterdata_is_curated():
                CROSSREF_RECORD = CROSSREF_PREP.prepare(
                    PREPARATION, RECORD.copy_prep_rec()
                )

                if "retracted" in CROSSREF_RECORD.data.get("prescreen_exclusion", ""):

                    self.REVIEW_MANAGER.logger.info(
                        f"{colors.GREEN}Found paper retract: "
                        f"{RECORD.data['ID']}{colors.END}"
                    )
                    RECORD.prescreen_exclude(reason="retracted", print_warning=True)
                    RECORD.remove_field(key="warning")

                elif "forthcoming" == RECORD.data["year"]:
                    self.REVIEW_MANAGER.logger.info(
                        f"{colors.GREEN}Update published forthcoming paper: "
                        f"{RECORD.data['ID']}{colors.END}"
                    )
                    RECORD = CROSSREF_PREP.prepare(PREPARATION, RECORD)

                    # TODO : we may create a full list here
                    colrev_id = RECORD.create_colrev_id(
                        alsoKnownAsRecord=RECORD.get_data()
                    )
                    RECORD.data["colrev_id"] = colrev_id

                else:
                    for k, v in CROSSREF_RECORD.data.items():
                        if (
                            k
                            not in colrev.record.Record.identifying_field_keys
                            + colrev.record.Record.provenance_keys
                            + ["ID", "ENTRYTYPE", "screening_criteria"]
                        ):
                            try:
                                source = CROSSREF_RECORD.data["colrev_data_provenance"][
                                    k
                                ]["source"]
                            except KeyError:
                                source = (
                                    "https://api.crossref.org/works/"
                                    + f"{RECORD.data['doi']}"
                                )
                            RECORD.update_field(
                                key=k, value=v, source=source, keep_source_if_equal=True
                            )
                if PREVIOUS_RECORD != RECORD:
                    with change_counter.get_lock():
                        change_counter.value += 1

        if change_counter.value > 0:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.GREEN}Updated {change_counter.value} "
                f"records based on Crossref{colors.END}"
            )
        else:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.GREEN}Records up-to-date with Crossref{colors.END}"
            )
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Update records", script_call="colrev pull"
        )

        print()

    def pull_records_from_index(self) -> None:

        self.REVIEW_MANAGER.logger.info("Pull records from LocalIndex")

        PREPARATION = colrev.prep.Preparation(
            REVIEW_MANAGER=self.REVIEW_MANAGER, notify_state_transition_process=False
        )

        LOCAL_INDEX_PREP = built_in_prep.LocalIndexPrep(
            PREPARATION=PREPARATION, SETTINGS={"name": "local_index_prep"}
        )

        # Note : do not use named argument (used in multiprocessing)
        def pull_record(record):
            previous_status = record["colrev_status"]
            # TODO : remove the following
            previouscolrev_pdf_id = record.get("colrev_pdf_id", "")
            prev_dblp_key = record.get("dblp_key", "")

            RECORD = colrev.record.PrepRecord(data=record)
            RETRIEVED_RECORD = LOCAL_INDEX_PREP.prepare(PREPARATION, RECORD)
            source_info = "LOCAL_INDEX"
            if "CURATED:" in RETRIEVED_RECORD.data.get(
                "colrev_masterdata_provenance", ""
            ):
                source_info = RETRIEVED_RECORD.data[
                    "colrev_masterdata_provenance"
                ].replace("CURATED:", "")
            PREVIOUS_RECORD = RECORD.copy_prep_rec()
            RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=source_info)

            if PREVIOUS_RECORD != RECORD:
                # pylint: disable=global-variable-not-assigned
                global change_counter
                with change_counter.get_lock():
                    change_counter.value += 1

            record = RECORD.get_data()
            record["colrev_status"] = previous_status

            if "" != previouscolrev_pdf_id:
                record["colrev_pdf_id"] = previouscolrev_pdf_id
            if "" != prev_dblp_key:
                record["dblp_key"] = prev_dblp_key
            return record

        PREPARATION = colrev.prep.Preparation(
            REVIEW_MANAGER=self.REVIEW_MANAGER, notify_state_transition_process=False
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        self.REVIEW_MANAGER.logger.info("Update records based on LocalIndex")

        # pylint: disable=global-statement
        global change_counter

        change_counter = Value("i", 0)

        pool = ProcessPool(nodes=mp.cpu_count() - 1)
        records_list = pool.map(pull_record, records.values())
        pool.close()
        pool.join()
        pool.clear()

        if change_counter.value > 0:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.GREEN}Updated {change_counter.value} "
                f"records based on LocalIndex{colors.END}"
            )
        else:
            self.REVIEW_MANAGER.logger.info(
                f"{colors.GREEN}Records up-to-date with LocalIndex{colors.END}"
            )

        records = {r["ID"]: r for r in records_list}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Update records", script_call="colrev pull"
        )

        print()


if __name__ == "__main__":
    pass
