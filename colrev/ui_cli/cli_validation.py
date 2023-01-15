#!/usr/bin/env python3
"""Scripts to print the CoLRev status (cli)."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import colrev.record
import colrev.ui_cli.cli_colors as colors

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

        if "n" == user_selection:
            dedupe_operation.unmerge_records(
                current_record_ids=validation_item["record"]["ID"]
            )

        if "q" == user_selection:
            break
        if "y" == user_selection:
            continue


def __validate_prep(
    *,
    validate_operation: colrev.operation.Operation,
    validation_details: dict,
    threshold: float,
) -> None:

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

        if "n" == user_selection:
            validate_operation.review_manager.dataset.save_records_dict(
                records={
                    validation_element["prior_record_dict"]["ID"]: validation_element[
                        "prior_record_dict"
                    ]
                },
                partial=True,
            )

        if "q" == user_selection:
            break
        if "y" == user_selection:
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
        if "prep" == key:
            __validate_prep(
                validate_operation=validate_operation,
                validation_details=details,
                threshold=threshold,
            )
        elif "dedupe" == key:
            __validate_dedupe(
                validate_operation=validate_operation,
                validation_details=details,
                threshold=threshold,
            )
        elif "properties" == key:
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
        elif "contributor_commits" == key:
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
        else:
            print("Not yet implemented")
            print(validation_details)

    if validate_operation.review_manager.dataset.records_changed():
        validate_operation.review_manager.create_commit(msg="validate")


if __name__ == "__main__":
    pass
