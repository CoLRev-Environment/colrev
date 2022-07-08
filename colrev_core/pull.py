#! /usr/bin/env python
from colrev_core.process import Process
from colrev_core.process import ProcessType


class Pull(Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER=REVIEW_MANAGER, type=ProcessType.explore)

    def main(self, *, records_only: bool = False, project_only: bool = False) -> None:

        if project_only:
            self.pull_project()
        elif records_only:
            self.pull_records_from_index()
        else:
            self.pull_project()
            self.pull_records_from_index()

        return

    def pull_project(self) -> None:
        try:
            git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
            origin = git_repo.remotes.origin
            self.REVIEW_MANAGER.logger.info(
                f"Pull changes from {git_repo.remotes.origin}"
            )
            res = origin.pull()
        except AttributeError:
            self.REVIEW_MANAGER.logger.info("No remote detected for pull")
            pass
            return

        if 4 == res[0].flags:
            self.REVIEW_MANAGER.logger.info("No updates")
        elif 64 == res[0].flags:
            self.REVIEW_MANAGER.logger.info("Updated CoLRev repository")
        else:
            self.REVIEW_MANAGER.logger.info(f"Returned flag {res[0].flags}")

    def pull_records_from_crossref(self) -> None:
        from colrev_core.prep import Preparation
        from colrev_core.record import PrepRecord, Record
        from colrev_core.built_in import prep as built_in_prep
        from tqdm import tqdm

        CROSSREF_PREP = built_in_prep.CrossrefMetadataPrep()

        self.REVIEW_MANAGER.logger.info("Pull records from crossref")

        PREPARATION = Preparation(
            REVIEW_MANAGER=self.REVIEW_MANAGER, notify_state_transition_process=False
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        for record in tqdm(records.values()):
            RECORD = PrepRecord(data=record)
            # TODO : use masterdata_is_curated() for identifying_fields_keys only?
            if not RECORD.masterdata_is_curated() and "doi" in RECORD.data:
                CROSSREF_RECORD = CROSSREF_PREP.prepare(
                    PREPARATION, RECORD.copy_prep_rec()
                )

                if "retracted" in CROSSREF_RECORD.data.get("prescreen_exclusion", ""):
                    RECORD.prescreen_exclude(reason="retracted", print_warning=True)
                    RECORD.remove_field(key="warning")

                elif "forthcoming" == RECORD.data["year"]:
                    self.REVIEW_MANAGER.logger.info(
                        f"Update published forthcoming paper: {RECORD.data['ID']}"
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
                            not in Record.identifying_field_keys
                            + Record.provenance_keys
                            + ["ID", "ENTRYTYPE", "exclusion_criteria"]
                        ):
                            try:
                                source = CROSSREF_RECORD.data["colrev_data_provenance"][
                                    k
                                ]["source"]
                            except KeyError:
                                pass
                                source = (
                                    "https://api.crossref.org/works/"
                                    + f"{RECORD.data['doi']}"
                                )
                            RECORD.update_field(
                                key=k, value=v, source=source, keep_source_if_equal=True
                            )

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Update records", script_call="colrev pull"
        )

        return

    def pull_records_from_index(self) -> None:
        from colrev_core.prep import Preparation
        from colrev_core.record import PrepRecord
        from pathos.multiprocessing import ProcessPool
        import multiprocessing as mp

        from colrev_core.built_in import prep as built_in_prep

        self.REVIEW_MANAGER.logger.info("Pull records from index")

        LOCAL_INDEX_PREP = built_in_prep.LocalIndexPrep()

        # Note : do not use named argument (used in multiprocessing)
        def pull_record(record):
            previous_status = record["colrev_status"]
            # TODO : remove the following
            previous_source_url = record.get("source_url", "")
            previouscolrev_pdf_id = record.get("colrev_pdf_id", "")
            prev_dblp_key = record.get("dblp_key", "")

            RECORD = PrepRecord(data=record)
            RETRIEVED_RECORD = LOCAL_INDEX_PREP.prepare(PREPARATION, RECORD)
            source_info = "LOCAL_INDEX"
            if "CURATED:" in RETRIEVED_RECORD.data["colrev_masterdata_provenance"]:
                source_info = RETRIEVED_RECORD.data[
                    "colrev_masterdata_provenance"
                ].replace("CURATED:", "")
            RECORD.merge(MERGING_RECORD=RETRIEVED_RECORD, default_source=source_info)

            record = RECORD.get_data()
            record["colrev_status"] = previous_status

            if "" != previous_source_url:
                record["source_url"] = previous_source_url
            if "" != previouscolrev_pdf_id:
                record["colrev_pdf_id"] = previouscolrev_pdf_id
            if "" != prev_dblp_key:
                record["dblp_key"] = prev_dblp_key
            return record

        self.REVIEW_MANAGER.logger.info("Load records")

        PREPARATION = Preparation(
            REVIEW_MANAGER=self.REVIEW_MANAGER, notify_state_transition_process=False
        )
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

        self.REVIEW_MANAGER.logger.info("Update records based on LocalIndex")

        pool = ProcessPool(nodes=mp.cpu_count() - 1)
        records_list = pool.map(pull_record, records.values())
        pool.close()
        pool.join()
        pool.clear()

        # TODO : test the following line
        records = {r["ID"]: r for r in records_list}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Update records", script_call="colrev pull"
        )

        return


if __name__ == "__main__":
    pass
