#! /usr/bin/env python
"""Traces records and changes through history."""
from __future__ import annotations

import pprint
import time

import dictdiffer

import colrev.operation


class Trace(colrev.operation.Operation):
    """Trace a record through history"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.check,
        )

    def __lpad_multiline(self, *, s: str, lpad: int) -> str:
        lines = s.splitlines()
        return "\n".join(["".join([" " * lpad]) + line for line in lines])

    def main(self, *, record_id: str) -> None:
        """Trace a record (main entrypoint)"""

        self.review_manager.logger.info(f"Trace record by ID: {record_id}")

        revlist = self.review_manager.dataset.get_repo().iter_commits()

        _pp = pprint.PrettyPrinter(indent=4)

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

            if str(self.review_manager.dataset.RECORDS_FILE_RELATIVE) in commit.tree:
                filecontents = (
                    commit.tree / str(self.review_manager.dataset.RECORDS_FILE_RELATIVE)
                ).data_stream.read()

                records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=filecontents.decode("utf-8")
                )

                if record_id not in records_dict:
                    continue
                record = records_dict[record_id]

                if len(record) == 0:
                    print(f"record {record_id} not in commit.")
                else:
                    diffs = list(dictdiffer.diff(prev_record, record))
                    if len(diffs) > 0:
                        for diff in diffs:
                            print(self.__lpad_multiline(s=_pp.pformat(diff), lpad=5))
                    prev_record = record

            if "data.csv" in commit.tree:
                filecontents = (commit.tree / "data.csv").data_stream.read()
                for line in str(filecontents).split("\\n"):
                    if record_id in line:
                        if line != prev_data:
                            print(f"Data: {line}")
                            prev_data = line


if __name__ == "__main__":
    pass
