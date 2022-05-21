#! /usr/bin/env python
import pprint
import time

import dictdiffer

from colrev_core.process import Process
from colrev_core.process import ProcessType


class Trace(Process):
    def __init__(self, *, REVIEW_MANAGER):

        super().__init__(REVIEW_MANAGER, ProcessType.check)

    def __lpad_multiline(self, *, s: str, lpad: int) -> str:
        lines = s.splitlines()
        return "\n".join(["".join([" " * lpad]) + line for line in lines])

    def main(self, *, ID: str) -> None:

        self.REVIEW_MANAGER.logger.info(f"Trace record by ID: {ID}")

        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
        DATA = self.REVIEW_MANAGER.paths["DATA"]

        revlist = self.REVIEW_MANAGER.REVIEW_DATASET.get_repo().iter_commits()

        pp = pprint.PrettyPrinter(indent=4)

        prev_record: dict = {}
        prev_data = ""
        for commit in reversed(list(revlist)):
            commit_message_first_line = str(commit.message).partition("\n")[0]
            print(
                "\n\n"
                + time.strftime(
                    "%Y-%m-%d %H:%M",
                    time.gmtime(commit.committed_date),
                )
                + f" {commit} ".ljust(40, " ")
                + f" {commit_message_first_line} (by {commit.author.name})"
            )

            if str(MAIN_REFERENCES_RELATIVE) in commit.tree:
                filecontents = (
                    commit.tree / str(MAIN_REFERENCES_RELATIVE)
                ).data_stream.read()

                records_dict = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )

                if ID not in records_dict:
                    continue
                record = records_dict[ID]

                if len(record) == 0:
                    print(f"record {ID} not in commit.")
                else:
                    diffs = list(dictdiffer.diff(prev_record, record))
                    if len(diffs) > 0:
                        for diff in diffs:
                            print(self.__lpad_multiline(s=pp.pformat(diff), lpad=5))
                    prev_record = record

            if DATA in commit.tree:
                filecontents = (commit.tree / DATA).data_stream.read()
                for line in str(filecontents).split("\\n"):
                    if ID in line:
                        if line != prev_data:
                            print(f"Data: {line}")
                            prev_data = line

        return


if __name__ == "__main__":
    pass
