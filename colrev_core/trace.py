#! /usr/bin/env python
import logging
import pprint
import time

import bibtexparser
import dictdiffer

logging.getLogger("bibtexparser").setLevel(logging.CRITICAL)

logger = logging.getLogger("colrev_core")


def lpad_multiline(s: str, lpad: int) -> str:
    lines = s.splitlines()
    return "\n".join(["".join([" " * lpad]) + line for line in lines])


def main(REVIEW_MANAGER, ID: str) -> None:

    logger.info(f"Trace record by ID: {ID}")

    MAIN_REFERENCES_RELATIVE = REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]
    DATA = REVIEW_MANAGER.paths["DATA"]

    revlist = REVIEW_MANAGER.git_repo.iter_commits()

    pp = pprint.PrettyPrinter(indent=4)

    prev_record: dict = {}
    prev_data = ""
    for commit in reversed(list(revlist)):
        commit_message_first_line = commit.message.partition("\n")[0]
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
            individual_bib_db = bibtexparser.loads(filecontents)
            record = [
                record for record in individual_bib_db.entries if record["ID"] == ID
            ][0]

            if len(record) == 0:
                print(f"record {ID} not in commit.")
            else:
                diffs = list(dictdiffer.diff(prev_record, record))
                if len(diffs) > 0:
                    for diff in diffs:
                        print(lpad_multiline(pp.pformat(diff), 5))
                prev_record = record

        if DATA in commit.tree:
            filecontents = (commit.tree / DATA).data_stream.read()
            for line in str(filecontents).split("\\n"):
                if ID in line:
                    if line != prev_data:
                        print(f"Data: {line}")
                        prev_data = line

    return
