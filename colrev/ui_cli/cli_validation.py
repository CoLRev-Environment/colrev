#!/usr/bin/env python3
"""Scripts to print the CoLRev status (cli)."""
from __future__ import annotations

import os
import subprocess

import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.status

# pylint: disable=duplicate-code
keys = [
    "author",
    "title",
    "journal",
    "booktitle",
    "year",
    "volume",
    "number",
    "pages",
]


def __validate_dedupe(
    *,
    validate_operation: colrev.operation.Operation,
    validation_details: dict,
    threshold: float,  # pylint: disable=unused-argument
) -> None:
    dedupe_operation = validate_operation.review_manager.get_dedupe_operation()

    for validation_item in validation_details:
        print(validation_item["change_score"])
        colrev.record.Record.print_diff_pair(
            record_pair=[
                validation_item["prior_record_a"],
                validation_item["prior_record_b"],
            ],
            keys=keys,
        )

        user_selection = input("Validate [y,n,q for yes, no (undo), or quit]?")

        if user_selection == "n":
            dedupe_operation.unmerge_records(
                current_record_ids=validation_item["record"]["ID"]
            )

        if user_selection == "q":
            break
        if user_selection == "y":
            continue


def __validate_prep(
    *,
    validate_operation: colrev.operation.Operation,
    validation_details: list,
    threshold: float,
) -> None:
    # Note : for testing:
    # prescreen_excluded_to_validate = [
    # e for e in validation_details if not e["prescreen_exclusion_mark"]
    # ]
    prescreen_excluded_to_validate = [
        e for e in validation_details if e["prescreen_exclusion_mark"]
    ]
    print("Prescreen excluded:")
    for i, validation_detail in enumerate(prescreen_excluded_to_validate):
        print(i)
        colrev.record.Record(
            data=validation_detail["record_dict"]
        ).print_citation_format()

    displayed = False
    for validation_element in validation_details:
        if validation_element["change_score"] < threshold:
            continue
        displayed = True
        # Escape sequence to clear terminal output for each new comparison
        os.system("cls" if os.name == "nt" else "clear")
        if (
            validation_element["prior_record_dict"]["ID"]
            == validation_element["record_dict"]["ID"]
        ):
            print(
                f"difference: {str(round(validation_element['change_score'], 4))} "
                f"record {validation_element['prior_record_dict']['ID']}"
            )
        else:
            print(
                f"difference: {str(round(validation_element['change_score'], 4))} "
                f"record {validation_element['prior_record_dict']['ID']} - "
                f"{validation_element['record_dict']['ID']}"
            )

        colrev.record.Record.print_diff_pair(
            record_pair=[
                validation_element["prior_record_dict"],
                validation_element["record_dict"],
            ],
            keys=keys,
        )

        user_selection = input("Validate [y,n,q for yes, no (undo), or quit]?")

        if user_selection == "n":
            validate_operation.review_manager.dataset.save_records_dict(
                records={
                    validation_element["prior_record_dict"]["ID"]: validation_element[
                        "prior_record_dict"
                    ]
                },
                partial=True,
            )

        if user_selection == "q":
            break
        if user_selection == "y":
            continue

    if not displayed:
        validate_operation.review_manager.logger.info(
            "No preparation changes above threshold"
        )


def validate(
    *,
    validate_operation: colrev.operation.Operation,
    validation_details: dict,
    threshold: float,
) -> None:
    """Validate details in the cli"""

    for key, details in validation_details.items():
        if key == "prep":
            __validate_prep(
                validate_operation=validate_operation,
                validation_details=details,
                threshold=threshold,
            )
        elif key == "dedupe":
            __validate_dedupe(
                validate_operation=validate_operation,
                validation_details=details,
                threshold=threshold,
            )
        elif key == "properties":
            validate_operation.review_manager.logger.info(
                " Traceability of records".ljust(32, " ")
                + str(details["record_traceability"])
            )
            validate_operation.review_manager.logger.info(
                " Consistency (based on hooks)".ljust(32, " ")
                + str(details["consistency"])
            )
            validate_operation.review_manager.logger.info(
                " Completeness of iteration".ljust(32, " ")
                + str(details["completeness"])
            )
        elif key == "contributor_commits":
            validate_operation.review_manager.logger.info(
                "Showing commits in which the contributor was involved as the author or committer."
            )

            print()
            print("Commits to validate:")
            print()
            for item in details:
                for _, item_values in item.items():
                    print(item_values["msg"])
                    print(f"  date      {item_values['date']}")
                    print(
                        f"  author    {item_values['author']} ({item_values['author_email']})"
                    )
                    print(
                        f"  committer {item_values['committer']} ({item_values['committer_email']})"
                    )
                    print(f"  {colors.ORANGE}{item_values['validate']}{colors.END}")

            print()
        elif key == "general":
            validate_operation.review_manager.logger.info("Start general validation")
            validate_operation.review_manager.logger.info(
                "Next, an interface will open and "
                "display the changes introduced in the selected commit."
            )
            validate_operation.review_manager.logger.info(
                "To undo minor changes, edit the corresponding files directly and run "
                f"{colors.ORANGE}git add FILENAME && "
                f"git commit -m 'DESCRIPTION OF CHANGES UNDONE'{colors.END}"
            )
            validate_operation.review_manager.logger.info(
                "To undo all changes introduced in a commit, run "
                f"{colors.ORANGE}git revert COMMIT_ID{colors.END}"
            )
            input("Enter to continue")
            if "commit_relative" in details:
                subprocess.run(
                    ["gitk", f"--select-commit={details['commit_relative']}"],
                    check=False,
                )
            else:
                subprocess.run(["gitk"], check=False)

        else:
            print("Not yet implemented")
            print(validation_details)

    if validate_operation.review_manager.dataset.records_changed():
        validate_operation.review_manager.create_commit(msg="validate")


if __name__ == "__main__":
    pass
