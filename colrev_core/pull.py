#! /usr/bin/env python
from colrev_core.process import Process
from colrev_core.process import ProcessType


class Pull(Process):
    def __init__(self, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER, ProcessType.explore)

    def main(self, records_only: bool = False, project_only: bool = False) -> None:

        if not project_only:
            self.pull_project()

        if not records_only:
            self.pull_records_from_index()

        return

    def pull_project(self) -> None:
        git_repo = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo()
        origin = git_repo.remotes.origin
        self.REVIEW_MANAGER.logger.info(f"Pull changes from {git_repo.remotes.origin}")
        res = origin.pull()
        if 4 == res[0].flags:
            self.REVIEW_MANAGER.logger.info("No updates")
        elif 64 == res[0].flags:
            self.REVIEW_MANAGER.logger.info("Updated CoLRev repository")
        else:
            self.REVIEW_MANAGER.logger.info(f"Returned flag {res[0].flags}")

    def pull_records_from_index(self) -> None:
        from colrev_core.prep import Preparation
        from pathos.multiprocessing import ProcessPool
        import multiprocessing as mp

        def pull_record(record):
            previous_status = record["status"]
            # TODO : removethe following
            previous_source_url = record.get("source_url", "")
            previouscolrev_pdf_id = record.get("colrev_pdf_id", "")
            prev_dblp_key = record.get("dblp_key", "")

            # TODO : the source_url should be a list (with newlines)?

            record = PREPARATION.get_record_from_local_index(record)
            record["status"] = previous_status

            if "" != previous_source_url:
                record["source_url"] = previous_source_url
            if "" != previouscolrev_pdf_id:
                record["colrev_pdf_id"] = previouscolrev_pdf_id
            if "" != prev_dblp_key:
                record["dblp_key"] = prev_dblp_key
            return record

        self.REVIEW_MANAGER.logger.info("Load records")

        PREPARATION = Preparation(
            self.REVIEW_MANAGER, notify_state_transition_process=False
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
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit("Update records")

        return


if __name__ == "__main__":
    pass
