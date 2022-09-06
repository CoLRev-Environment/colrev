#! /usr/bin/env python
from __future__ import annotations

import multiprocessing as mp
from multiprocessing import Value

from pathos.multiprocessing import ProcessPool
from tqdm import tqdm

import colrev.env.cli_colors as colors
import colrev.ops.built_in.prep as built_in_prep
import colrev.process
import colrev.record


CHANGE_COUNTER = None


class Pull(colrev.process.Process):
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
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
            git_repo = self.review_manager.dataset.get_repo()
            origin = git_repo.remotes.origin
            self.review_manager.logger.info(
                f"Pull project changes from {git_repo.remotes.origin}"
            )
            res = origin.pull()
        except AttributeError:
            self.review_manager.logger.info(
                f"{colors.RED}No remote detected for pull{colors.END}"
            )
            return

        if 4 == res[0].flags:
            self.review_manager.logger.info(
                f"{colors.GREEN}Project up-to-date{colors.END}"
            )
        elif 64 == res[0].flags:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated CoLRev repository{colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{colors.RED}Returned flag {res[0].flags}{colors.END}"
            )
        print()

    def pull_records_from_crossref(self) -> None:

        prep_operation = self.review_manager.get_prep_operation(
            notify_state_transition_operation=False
        )

        crossref_prep = built_in_prep.CrossrefMetadataPrep(
            prep_operation=prep_operation, settings={"name": "local_index_prep"}
        )

        self.review_manager.logger.info("Pull records from Crossref")

        records = self.review_manager.dataset.load_records_dict()

        # pylint: disable=redefined-outer-name,invalid-name
        CHANGE_COUNTER = Value("i", 0)
        for record_dict in tqdm(records.values()):
            record = colrev.record.PrepRecord(data=record_dict)
            previous_record = record.copy_prep_rec()
            # TODO : use masterdata_is_curated() for identifying_fields_keys only?
            if "doi" in record.data and not record.masterdata_is_curated():
                crossref_record = crossref_prep.prepare(
                    prep_operation, record.copy_prep_rec()
                )

                if "retracted" in crossref_record.data.get("prescreen_exclusion", ""):

                    self.review_manager.logger.info(
                        f"{colors.GREEN}Found paper retract: "
                        f"{record.data['ID']}{colors.END}"
                    )
                    record.prescreen_exclude(reason="retracted", print_warning=True)
                    record.remove_field(key="warning")

                elif "forthcoming" == record.data["year"]:
                    self.review_manager.logger.info(
                        f"{colors.GREEN}Update published forthcoming paper: "
                        f"{record.data['ID']}{colors.END}"
                    )
                    record = crossref_prep.prepare(prep_operation, record)

                    # TODO : we may create a full list here
                    colrev_id = record.create_colrev_id(
                        also_known_as_record=record.get_data()
                    )
                    record.data["colrev_id"] = colrev_id

                else:
                    for key, value in crossref_record.data.items():
                        if (
                            key
                            not in colrev.record.Record.identifying_field_keys
                            + colrev.record.Record.provenance_keys
                            + ["ID", "ENTRYTYPE", "screening_criteria"]
                        ):
                            try:
                                source = crossref_record.data["colrev_data_provenance"][
                                    key
                                ]["source"]
                            except KeyError:
                                source = (
                                    "https://api.crossref.org/works/"
                                    + f"{record.data['doi']}"
                                )
                            record.update_field(
                                key=key,
                                value=value,
                                source=source,
                                keep_source_if_equal=True,
                            )
                if previous_record != record:
                    with CHANGE_COUNTER.get_lock():
                        CHANGE_COUNTER.value += 1

        if CHANGE_COUNTER.value > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated {CHANGE_COUNTER.value} "
                f"records based on Crossref{colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{colors.GREEN}Records up-to-date with Crossref{colors.END}"
            )
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Update records", script_call="colrev pull"
        )

        print()

    def pull_records_from_index(self) -> None:

        self.review_manager.logger.info("Pull records from LocalIndex")

        prep_operation = self.review_manager.get_prep_operation(
            notify_state_transition_operation=False
        )

        local_index_prep = built_in_prep.LocalIndexPrep(
            prep_operation=prep_operation, settings={"name": "local_index_prep"}
        )

        # Note : do not use named argument (used in multiprocessing)
        def pull_record(record_dict):
            previous_status = record_dict["colrev_status"]
            # TODO : remove the following
            previouscolrev_pdf_id = record_dict.get("colrev_pdf_id", "")
            prev_dblp_key = record_dict.get("dblp_key", "")

            record = colrev.record.PrepRecord(data=record_dict)
            retrieved_record = local_index_prep.prepare(prep_operation, record)
            source_info = "LOCAL_INDEX"
            if "CURATED:" in retrieved_record.data.get(
                "colrev_masterdata_provenance", ""
            ):
                source_info = retrieved_record.data[
                    "colrev_masterdata_provenance"
                ].replace("CURATED:", "")
            previous_record = record.copy_prep_rec()
            record.merge(merging_record=retrieved_record, default_source=source_info)

            if previous_record != record:
                # pylint: disable=global-variable-not-assigned
                global CHANGE_COUNTER
                with CHANGE_COUNTER.get_lock():
                    CHANGE_COUNTER.value += 1

            record_dict = record.get_data()
            record_dict["colrev_status"] = previous_status

            if "" != previouscolrev_pdf_id:
                record_dict["colrev_pdf_id"] = previouscolrev_pdf_id
            if "" != prev_dblp_key:
                record_dict["dblp_key"] = prev_dblp_key
            return record_dict

        prep_operation = self.review_manager.get_prep_operation(
            notify_state_transition_operation=False
        )
        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Update records based on LocalIndex")

        # pylint: disable=global-statement
        global CHANGE_COUNTER

        CHANGE_COUNTER = Value("i", 0)

        pool = ProcessPool(nodes=mp.cpu_count() - 1)
        records_list = pool.map(pull_record, records.values())
        pool.close()
        pool.join()
        pool.clear()

        if CHANGE_COUNTER.value > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Updated {CHANGE_COUNTER.value} "
                f"records based on LocalIndex{colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{colors.GREEN}Records up-to-date with LocalIndex{colors.END}"
            )

        records = {r["ID"]: r for r in records_list}
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Update records", script_call="colrev pull"
        )

        print()


if __name__ == "__main__":
    pass
