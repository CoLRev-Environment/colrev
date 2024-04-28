#!/usr/bin/env python3
"""Hook to update non-CoLRev repositories"""
from pathlib import Path

import colrev.packages.sync.src.sync
from colrev.constants import Colors
from colrev.constants import ExitCodes
from colrev.constants import Fields


def main() -> int:
    """Main entrypoint for the update hoooks"""

    sync_operation = colrev.packages.sync.src.sync.Sync()
    sync_operation.get_cited_papers()

    if len(sync_operation.non_unique_for_import) > 0:
        # Note: interactive resolution not supported in pre-commit hooks
        print(
            f"To resolve non-unique cases, run {Colors.ORANGE}colrev sync{Colors.END}"
        )

        return ExitCodes.FAIL

    # Add IDs to .spelling (if not already in the file)
    if Path(".spelling").is_file():
        if not all(
            x.data[Fields.ID] in Path(".spelling").read_text(encoding="utf-8")
            for x in sync_operation.records_to_import
        ):
            with open(".spelling", "a", encoding="utf-8") as file:
                for item in sync_operation.records_to_import:
                    file.write(item.data[Fields.ID])

    sync_operation.add_to_bib()

    return ExitCodes.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
