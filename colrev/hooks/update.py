#!/usr/bin/env python3
"""Hook to update non-CoLRev repositories"""
from pathlib import Path

import colrev.exit_codes
import colrev.review_manager
import colrev.ui_cli.cli_colors as colors


def main() -> int:
    """Main entrypoint for the update hoooks"""

    sync_operation = colrev.review_manager.ReviewManager.get_sync_operation()
    sync_operation.get_cited_papers()

    if len(sync_operation.non_unique_for_import) > 0:
        # Note: interactive resolution not supported in pre-commit hooks
        print(
            f"To resolve non-unique cases, run {colors.ORANGE}colrev sync{colors.END}"
        )

        return colrev.exit_codes.ExitCodes.FAIL

    # Add IDs to .spelling (if not already in the file)
    if Path(".spelling").is_file():
        if not all(
            x.data["ID"] in Path(".spelling").read_text(encoding="utf-8")
            for x in sync_operation.records_to_import
        ):
            with open(".spelling", "a", encoding="utf-8") as file:
                for item in sync_operation.records_to_import:
                    file.write(item.data["ID"])

    sync_operation.add_to_bib()

    return colrev.exit_codes.ExitCodes.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
