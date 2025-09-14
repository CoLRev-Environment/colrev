#!/usr/bin/env python3
"""Scripts to support command-line validation."""
from __future__ import annotations

import difflib
import subprocess  # nosec
import typing

import inquirer
from rapidfuzz import fuzz

import colrev.record.record
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState

if typing.TYPE_CHECKING:
    import colrev.ops.validate

# pylint: disable=duplicate-code
keys = [
    Fields.AUTHOR,
    Fields.TITLE,
    Fields.JOURNAL,
    Fields.BOOKTITLE,
    Fields.YEAR,
    Fields.VOLUME,
    Fields.NUMBER,
    Fields.PAGES,
]


def print_string_diff(change: tuple) -> str:
    """Generates a string representation of the differences between two strings."""
    diff = difflib.Differ()
    letters = list(diff.compare(change[1], change[0]))
    for i, letter in enumerate(letters):
        if letter.startswith("  "):
            letters[i] = letters[i][-1]
        elif letter.startswith("+ "):
            letters[i] = f"{Colors.RED}" + letters[i][-1] + f"{Colors.END}"
        elif letter.startswith("- "):
            letters[i] = f"{Colors.GREEN}" + letters[i][-1] + f"{Colors.END}"
    res = "".join(letters).replace("\n", " ")
    return res


def print_diff(origin: dict, record_dict: dict) -> None:
    """Print the diff between two records"""

    for key in keys:

        if key not in origin and key not in record_dict:
            continue
        if key not in origin and key in record_dict:
            print(f"  diff {key}: {Colors.GREEN}{record_dict.get(key, '')}{Colors.END}")
            continue
        if key in origin and key not in record_dict:
            print(f"  diff {key}: {Colors.RED}{record_dict.get(key, '')}{Colors.END}")
            continue
        if origin[key] == record_dict[key]:
            continue

        similarity = fuzz.partial_ratio(origin[key], record_dict[key]) / 100
        if similarity < 0.5 or key in [
            Fields.VOLUME,
            Fields.NUMBER,
            Fields.YEAR,
        ]:
            line = f"{origin[key]} > {Colors.RED}{record_dict[key]}{Colors.END}"
        else:
            line = print_string_diff((origin[key], record_dict[key]))
        print(f"  diff {key} : {line}")


def print_diff_pair(record_pair: list) -> None:
    """Print the diff between two records"""

    for key in keys:
        prev_val = "_FIRST_VAL"
        for rec in record_pair:
            if (
                prev_val == rec.get(key, FieldValues.UNKNOWN)
                or prev_val == "_FIRST_VAL"
            ):
                line = f"{rec.get(key, '')}"
            else:
                similarity = 0.0
                if (
                    prev_val != FieldValues.UNKNOWN
                    and rec.get(key, "") != ""
                    and rec[key] is not None
                ):
                    similarity = fuzz.partial_ratio(prev_val, rec[key]) / 100
                    # Note : the fuzz.partial_ratio works better for partial substrings
                    # from difflib import SequenceMatcher
                    # similarity = SequenceMatcher(None, prev_val, rec[key]).ratio()
                if (
                    prev_val == FieldValues.UNKNOWN
                    and rec.get(key, FieldValues.UNKNOWN) != FieldValues.UNKNOWN
                ):
                    line = f"{Colors.GREEN}{rec.get(key, '')}{Colors.END}"
                elif (
                    rec.get(key, FieldValues.UNKNOWN) == FieldValues.UNKNOWN
                    and prev_val != FieldValues.UNKNOWN
                ):
                    line = f"{Colors.RED}[REMOVED]{Colors.END}"
                elif similarity < 0.5 or key in [
                    Fields.VOLUME,
                    Fields.NUMBER,
                    Fields.YEAR,
                ]:
                    line = f"{Colors.RED}{rec.get(key, '')}{Colors.END}"
                else:
                    line = print_string_diff((prev_val, rec.get(key, "")))
            print(f"{key} : {line}")
            prev_val = rec.get(key, FieldValues.UNKNOWN)
        print()


def _validate_dedupe(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
    threshold: float,  # pylint: disable=unused-argument
) -> None:
    dedupe_operation = validate_operation.review_manager.get_dedupe_operation()

    for validation_item in validation_details:
        print(validation_item["change_score"])
        print_diff_pair(
            record_pair=[
                validation_item["prior_record_a"],
                validation_item["prior_record_b"],
            ],
        )

        user_selection = input("Validate [y,n,q for yes, no (undo), or quit]?")

        if user_selection == "n":
            dedupe_operation.unmerge_records(
                current_record_ids=validation_item["record"][Fields.ID]
            )

        if user_selection == "q":
            break
        if user_selection == "y":
            continue


def _validate_prep_prescreen_exclusions(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
) -> None:

    prescreen_excluded_to_validate = validation_details
    if prescreen_excluded_to_validate:
        print("Prescreen excluded:")
        prescreen_errors = []

        choices = [
            (
                f"{e['ID']} : " f"{Colors.ORANGE}{e['title']}{Colors.END}",
                i,
            )
            for i, e in enumerate(prescreen_excluded_to_validate)
        ]
        questions = [
            inquirer.Checkbox(
                "selected_records",
                message="Select prescreen errors (using space)",
                choices=choices,
            ),
        ]
        answers = inquirer.prompt(questions)
        selected_indices = answers["selected_records"]
        for index in selected_indices:
            prescreen_errors.append(prescreen_excluded_to_validate[index])

        for error in prescreen_errors:
            colrev.record.record.Record(error).set_status(
                target_state=RecordState.md_needs_manual_preparation
            )
            validate_operation.review_manager.dataset.save_records_dict(
                {error[Fields.ID]: error},
                partial=True,
            )


# def _remove_from_feed(*, review_manager, origin) -> None:
#     feed_name, feed_id = origin.split("/")
#     feed_file = review_manager.paths.search / Path(feed_name)
#     records = colrev.loader.load_utils.load(
#         filename=feed_file,
#         logger=review_manager.logger,
#         unique_id_field="ID",
#     )
#     records = {k: v for k, v in records.items() if k != feed_id}
#     write_file(records_dict=records, filename=feed_file)


def _validate_prep(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
    threshold: float,
) -> None:

    # Part 1 : origin validation
    origins_to_remove: typing.Dict[str, list] = {}
    displayed = False
    for validation_element in validation_details:
        if validation_element["change_score_max"] < threshold:
            continue
        displayed = True
        print("\n\n\n\n\n")
        # Escape sequence to clear terminal output for each new comparison
        # os.system("cls" if os.name == "nt" else "clear")

        record_dict = validation_element["record_dict"]
        print("Origins")
        for origin in validation_element["origins"]:
            print()
            print(f"{origin[Fields.ORIGIN][0]} : change {origin['change_score']}")
            colrev.record.record.Record(origin).print_citation_format()
            print_diff(
                origin=origin,
                record_dict=record_dict,
            )
            # break # we could continue in verbose mode!?

        print()
        print(f"Current record: {record_dict[Fields.ID]}")
        colrev.record.record.Record(record_dict).print_citation_format()
        print()

        questions = [
            inquirer.List(
                "user_selection",
                message="Validate?",
                choices=[
                    "yes",
                    "no (remove origin)",
                    "quit",
                ],
                default="y",
            ),
        ]
        answers = inquirer.prompt(questions)
        user_selection = answers["user_selection"]

        if user_selection.startswith("no (remove origin)"):
            # remove origin
            choices = [
                f"{origin[Fields.ORIGIN][0]}"
                for i, origin in enumerate(list(validation_element["origins"]))
            ]
            questions = [
                inquirer.Checkbox(
                    "selected_records",
                    message="Select origin to remove (using space)",
                    choices=choices,
                ),
            ]
            answers = inquirer.prompt(questions)
            for origin_to_remove in answers["selected_records"]:
                file, identifier = origin_to_remove.split("/")
                if file not in origins_to_remove:
                    origins_to_remove[file] = []
                origins_to_remove[file].append(identifier)

            record_dict[Fields.ORIGIN] = [
                origin[Fields.ORIGIN][0]
                for origin in list(validation_element["origins"])
                if origin[Fields.ORIGIN][0] not in answers["selected_records"]
            ]

            validate_operation.review_manager.dataset.save_records_dict(
                {record_dict[Fields.ID]: record_dict},
                partial=True,
            )

        if user_selection == "quit":
            break
        if user_selection == "yes":
            continue

    # if there is a key in origins_to_remove that does not start with md_, print
    # pylint: disable=use-a-generator
    if any([key for key in origins_to_remove if not key.startswith("md_")]):
        print("Please run colrev load again to (re)load all origin(s)")

    validate_operation.remove_md_origins(origins_to_remove)

    if not displayed:
        validate_operation.review_manager.logger.info(
            "No preparation changes above threshold"
        )


def _validate_properties(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
) -> None:

    validate_operation.review_manager.logger.info(
        " Traceability of records".ljust(32, " ")
        + str(validation_details["record_traceability"])
    )
    validate_operation.review_manager.logger.info(
        " Consistency (based on hooks)".ljust(32, " ")
        + str(validation_details["consistency"])
    )
    validate_operation.review_manager.logger.info(
        " Completeness of iteration".ljust(32, " ")
        + str(validation_details["completeness"])
    )


def _validate_contributor_commits(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
) -> None:
    validate_operation.review_manager.logger.info(
        "Showing commits in which the contributor was involved as the author or committer."
    )

    print()
    print("Commits to validate:")
    print()
    for item in validation_details:
        for _, item_values in item.items():
            print(item_values["msg"])
            print(f"  date      {item_values['date']}")
            print(
                f"  author    {item_values['author']} ({item_values['author_email']})"
            )
            print(
                f"  committer {item_values['committer']} ({item_values['committer_email']})"
            )
            print(f"  {Colors.ORANGE}{item_values['validate']}{Colors.END}")

    print()


def _validate_general(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
) -> None:
    validate_operation.review_manager.logger.info("Start general validation")
    validate_operation.review_manager.logger.info(
        "Next, an interface will open and "
        "display the changes introduced in the selected commit."
    )
    validate_operation.review_manager.logger.info(
        "To undo minor changes, edit the corresponding files directly and run "
        f"{Colors.ORANGE}git add FILENAME && "
        f"git commit -m 'DESCRIPTION OF CHANGES UNDONE'{Colors.END}"
    )
    validate_operation.review_manager.logger.info(
        "To undo all changes introduced in a commit, run "
        f"{Colors.ORANGE}git revert COMMIT_ID{Colors.END}"
    )
    input("Enter to continue")
    if "commit_relative" in validation_details:
        subprocess.run(  # nosec
            ["gitk", f"--select-commit={validation_details['commit_relative']}"],
            check=False,
        )
    else:
        subprocess.run(["gitk"], check=False)  # nosec


def validate(
    *,
    validate_operation: colrev.ops.validate.Validate,
    validation_details: dict,
    threshold: float,
) -> None:
    """Validate details in the cli"""

    for key, details in validation_details.items():
        if key == "prep":
            _validate_prep(
                validate_operation=validate_operation,
                validation_details=details,
                threshold=threshold,
            )
        elif key == "prep_prescreen_exclusions":
            _validate_prep_prescreen_exclusions(
                validate_operation=validate_operation,
                validation_details=details,
            )
        elif key == "dedupe":
            _validate_dedupe(
                validate_operation=validate_operation,
                validation_details=details,
                threshold=threshold,
            )
        elif key == "properties":
            _validate_properties(
                validate_operation=validate_operation,
                validation_details=details,
            )
        elif key == "contributor_commits":
            _validate_contributor_commits(
                validate_operation=validate_operation,
                validation_details=details,
            )
        elif key == "general":
            _validate_general(
                validate_operation=validate_operation,
                validation_details=details,
            )
        else:
            print("Not yet implemented")
            print(validation_details)

    if validate_operation.review_manager.dataset.records_changed():
        validate_operation.review_manager.dataset.create_commit(msg="validate")
