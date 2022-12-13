#!/usr/bin/env python3
"""Scripts to print the CoLRev status (cli)."""
from __future__ import annotations

import logging
from time import sleep
from typing import TYPE_CHECKING

from tqdm import tqdm

import colrev.exceptions as colrev_exceptions
import colrev.ui_cli.cli_colors as colors


if TYPE_CHECKING:
    import colrev.ops.status


def print_review_instructions(review_instructions: dict) -> None:
    """Print the review instructions on cli"""

    print("Review project\n")

    verbose = False

    # key_list = [list(x.keys()) for x in review_instructions]
    # keys = [item for sublist in key_list for item in sublist]
    # priority_item_set = "priority" in keys

    for review_instruction in review_instructions:

        # prioritize based on the order of instructions (most important first)
        # if priority_item_set and "priority" not in review_instruction.keys():
        #     continue

        if "info" in review_instruction:
            print("  " + review_instruction["info"])
        if "msg" in review_instruction:
            if "cmd" in review_instruction:
                if verbose:
                    print("  " + review_instruction["msg"] + ", i.e., use ")
                print(f'  {colors.ORANGE}{review_instruction["cmd"]}{colors.END}')
            else:
                print(f"  {colors.ORANGE}{review_instruction['msg']}{colors.END}")
        if "cmd_after" in review_instruction:
            print("  Then use " + review_instruction["cmd_after"])
        print()


def print_collaboration_instructions(collaboration_instructions: dict) -> None:
    """Print the collaboration instructions on cli"""

    # pylint: disable=too-many-branches

    print("Versioning and collaboration\n")

    if "status" in collaboration_instructions:
        if "title" in collaboration_instructions["status"]:
            title = collaboration_instructions["status"]["title"]
            if "WARNING" == collaboration_instructions["status"].get("level", "NA"):
                print(f"  {colors.RED}{title}{colors.END}")
            elif "SUCCESS" == collaboration_instructions["status"].get("level", "NA"):
                print(f"  {colors.GREEN}{title}{colors.END}")
            else:
                print("  " + title)
        if "msg" in collaboration_instructions["status"]:
            print(f'  {collaboration_instructions["status"]["msg"]}')

    for item in collaboration_instructions["items"]:
        if "title" in item:
            if "level" in item:
                if "WARNING" == item["level"]:
                    print(f'  {colors.RED}{item["title"]}{colors.END}')
                elif "SUCCESS" == item["level"]:
                    print(f'  {colors.GREEN}{item["title"]}{colors.END}')
            else:
                print("  " + item["title"])

        if "msg" in item:
            print("  " + item["msg"])
        if "cmd_after" in item:
            print(f'  {item["cmd_after"]}')
        print()


def print_environment_instructions(environment_instructions: dict) -> None:
    """Print the environment instructions on cli"""

    if len(environment_instructions) == 0:
        return

    print("CoLRev environment\n")

    key_list = [list(x.keys()) for x in environment_instructions]
    keys = [item for sublist in key_list for item in sublist]
    priority_item_set = "priority" in keys

    for environment_instruction in environment_instructions:
        if priority_item_set and "priority" not in environment_instruction.keys():
            continue
        if "info" in environment_instruction:
            print("  " + environment_instruction["info"])
        if "msg" in environment_instruction:
            if "cmd" in environment_instruction:
                print("  " + environment_instruction["msg"] + "  i.e., use ")
                print(f'  {colors.ORANGE}{environment_instruction["cmd"]}{colors.END}')
            else:
                print("  " + environment_instruction["msg"])
        if "cmd_after" in environment_instruction:
            print("  Then use " + environment_instruction["cmd_after"])
        print()


def print_progress(*, total_atomic_steps: int, completed_steps: int) -> None:
    """Print the progress bar on cli"""

    # Prints the percentage of atomic processing tasks that have been completed
    # possible extension: estimate the number of manual tasks (making assumptions on
    # frequencies of man-prep, ...)?

    if total_atomic_steps != 0:
        current_percentage = int((completed_steps / total_atomic_steps) * 100)
    else:
        current_percentage = -1

    sleep_interval = 1.1 / max(current_percentage, 100)
    print()

    for i in tqdm(
        range(100),
        desc="  Progress:",
        bar_format="{desc} |{bar}|{percentage:.0f}%",
        ncols=40,
    ):
        sleep(sleep_interval)
        if current_percentage in [i, -1]:
            break


def print_project_status(status_operation: colrev.ops.status.Status) -> None:
    """Print the project status on cli"""

    try:
        status_stats = status_operation.review_manager.get_status_stats()
        status_report = status_operation.get_review_status_report(colors=colors)
        print(status_report)

        if not status_stats.completeness_condition:
            print_progress(
                total_atomic_steps=status_stats.atomic_steps,
                completed_steps=status_stats.completed_atomic_steps,
            )
        print("")

        advisor = status_operation.review_manager.get_advisor()
        instructions = advisor.get_instructions(status_stats=status_stats)
        print_review_instructions(instructions["review_instructions"])
        print_collaboration_instructions(instructions["collaboration_instructions"])
        print_environment_instructions(instructions["environment_instructions"])

    except colrev_exceptions.RepoSetupError as exc:
        print(f"Status failed ({exc})")

    print("Checks\n")
    try:

        ret_check = status_operation.review_manager.check_repo()
    except colrev_exceptions.RepoSetupError as exc:
        ret_check = {"status": 1, "msg": exc}

    if 0 == ret_check["status"]:
        print(
            "  ReviewManager.check_repo()  ...  "
            f'{colors.GREEN}{ret_check["msg"]}{colors.END}'
        )
    if 1 == ret_check["status"]:
        print(f"  ReviewManager.check_repo()  ...  {colors.RED}FAIL{colors.END}")
        print(f'{ret_check["msg"]}\n')
        return

    try:
        ret_f = status_operation.review_manager.format_records_file()
    except KeyError as exc:
        logging.error(exc)
        ret_f = {"status": 1, "msg": "KeyError"}
    if 0 == ret_f["status"]:
        print(
            "  ReviewManager.format()      ...  "
            f'{colors.GREEN}{ret_f["msg"]}{colors.END}'
        )
    if 1 == ret_f["status"]:
        print(f"  ReviewManager.format()      ...  {colors.RED}FAIL{colors.END}")
        print(f'\n    {ret_f["msg"]}\n')
    if not status_operation.review_manager.in_virtualenv():
        print(
            f"  {colors.RED}WARNING{colors.END} running scripts outside of virtualenv"
        )
        print(
            "  For instructions to set up a virtual environment, run\n"
            f"  {colors.ORANGE}colrev show venv{colors.END}"
        )
    print()


if __name__ == "__main__":
    pass
