#!/usr/bin/env python3
"""Hook for reporting in CoLRev projects"""
import sys
from pathlib import Path

import colrev.ops.commit
import colrev.ops.correct
import colrev.review_manager
from colrev.constants import ExitCodes


def main() -> int:
    """Main entrypoint for the reporting"""

    print(sys.argv)
    msgfile = Path(sys.argv[1])
    review_manager = colrev.review_manager.ReviewManager()

    with open(msgfile, encoding="utf8") as file:
        available_contents = file.read()

    with open(msgfile, "w", encoding="utf8") as file:
        file.write(available_contents)
        # Don't append if it's already there
        # update = False
        # if "Command" not in available_contents:
        #     update = True
        # if "Properties" in available_contents:
        #     update = False
        # if update:
        commit = colrev.ops.commit.Commit(
            review_manager=review_manager,
            msg=available_contents,
            manual_author=True,
            script_name="MANUAL",
        )
        commit.update_report(msg_file=msgfile)

    if (
        not review_manager.settings.is_curated_masterdata_repo()
        and review_manager.dataset.records_changed()
    ):  # pragma: no cover
        colrev.ops.check.CheckOperation(review_manager)  # to notify
        corrections_operation = colrev.ops.correct.Corrections(
            review_manager=review_manager
        )
        corrections_operation.check_corrections_of_records()

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
