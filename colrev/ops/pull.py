#! /usr/bin/env python
"""CoLRev pull operation: Pull project and records."""
from __future__ import annotations

import multiprocessing as mp
from multiprocessing import Value
from multiprocessing.pool import ThreadPool as Pool

from tqdm import tqdm

import colrev.operation
import colrev.ops.built_in.prep.crossref_metadata_prep as built_in_crossref_prep
import colrev.ops.built_in.prep.local_index_prep as built_in_local_index_prep
import colrev.record
import colrev.ui_cli.cli_colors as colors

# pylint: disable=too-few-public-methods

CHANGE_COUNTER = None


class Pull(colrev.operation.Operation):
    """Pull the project and records"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.format,
        )

    def main(self, *, records_only: bool = False, project_only: bool = False) -> None:
        """Pull the CoLRev project and records (main entrypoint)"""

        if project_only:
            self.__pull_project()
        elif records_only:
            self.__pull_records_from_index()
            self.__pull_records_from_crossref()
        else:
            self.__pull_project()
            self.__pull_records_from_index()
            self.__pull_records_from_crossref()

    def __pull_project(self) -> None:
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

    def __pull_records_from_crossref(self) -> None:

        prep_operation = self.review_manager.get_prep_operation(
            notify_state_transition_operation=False
        )

        crossref_prep = built_in_crossref_prep.CrossrefMetadataPrep(
            prep_operation=prep_operation, settings={"endpoint": "local_index_prep"}
        )

        self.review_manager.logger.info("Pull records from Crossref")

        records = self.review_manager.dataset.load_records_dict()

        # pylint: disable=redefined-outer-name,invalid-name
        CHANGE_COUNTER = Value("i", 0)
        for record_dict in tqdm(records.values()):
            record = colrev.record.PrepRecord(data=record_dict)
            previous_record = record.copy_prep_rec()

            if not ("doi" in record.data and not record.masterdata_is_curated()):
                continue

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
                continue

            if "forthcoming" == record.data["year"]:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Update published forthcoming paper: "
                    f"{record.data['ID']}{colors.END}"
                )
                prepared_record = crossref_prep.prepare(prep_operation, record)
                record = colrev.record.PrepRecord(data=prepared_record.data)

                colrev_id = record.create_colrev_id(
                    also_known_as_record=record.get_data()
                )
                record.data["colrev_id"] = colrev_id
                continue

            for key, value in crossref_record.data.items():
                if (
                    key
                    not in colrev.record.Record.identifying_field_keys
                    + colrev.record.Record.provenance_keys
                    + ["ID", "ENTRYTYPE", "screening_criteria"]
                ):
                    try:
                        source = crossref_record.data["colrev_data_provenance"][key][
                            "source"
                        ]
                    except KeyError:
                        source = (
                            "https://api.crossref.org/works/" + f"{record.data['doi']}"
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

    def __pull_records_from_index(self) -> None:

        self.review_manager.logger.info("Pull records from LocalIndex")

        prep_operation = self.review_manager.get_prep_operation(
            notify_state_transition_operation=False, retrieval_similarity=0.99
        )

        local_index_prep = built_in_local_index_prep.LocalIndexPrep(
            prep_operation=prep_operation, settings={"endpoint": "local_index_prep"}
        )

        # Note : do not use named argument (used in multiprocessing)
        def pull_record(record_dict: dict) -> dict:
            previous_status = record_dict["colrev_status"]
            # TBD : remove the following?
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
                with CHANGE_COUNTER.get_lock():  # type: ignore  # noqa
                    CHANGE_COUNTER.value += 1  # type: ignore  # noqa

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

        pool = Pool(mp.cpu_count() - 1)
        records_list = pool.map(pull_record, records.values())
        pool.close()
        pool.join()

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
