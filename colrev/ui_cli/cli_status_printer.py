#!/usr/bin/env python3
"""Scripts to print the CoLRev status (cli)."""
from __future__ import annotations

import sys
import typing
from time import sleep

from tqdm import tqdm

import colrev.exceptions as colrev_exceptions
from colrev.constants import Colors
from colrev.constants import ExitCodes

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.ops.status


def print_review_instructions(review_instructions: dict) -> None:
    """Print the review instructions on cli"""

    print("Next operation")

    verbose = False

    # key_list = [list(x.keys()) for x in review_instructions]
    # keys = [item for sublist in key_list for item in sublist]
    # priority_item_set = "priority" in keys
    if not review_instructions:
        print(f"    {Colors.GREEN}Review iteration completed{Colors.END}")
        print(
            f"    {Colors.ORANGE}To start the next iteration of the review, run the search\n "
            f"    colrev search{Colors.END}"
        )
        print()

    for review_instruction in review_instructions:
        # prioritize based on the order of instructions (most important first)
        # if priority_item_set and "priority" not in review_instruction.keys():
        #     continue

        if "info" in review_instruction:
            print("    " + review_instruction["info"])
        if "msg" in review_instruction:
            if "cmd" in review_instruction:
                if verbose:
                    print("    " + review_instruction["msg"] + ", i.e., use ")
                print(f'    {Colors.ORANGE}{review_instruction["cmd"]}{Colors.END}')
            else:
                print(f"    {Colors.ORANGE}{review_instruction['msg']}{Colors.END}")
        if "cmd_after" in review_instruction:
            print("    Then use " + review_instruction["cmd_after"])
        print()


def _print_collaboration_instructions_status(
    *, collaboration_instructions: dict
) -> None:
    if "status" not in collaboration_instructions:
        return
    if "title" in collaboration_instructions["status"]:
        title = collaboration_instructions["status"]["title"]
        if collaboration_instructions["status"].get("level", "NA") == "WARNING":
            print(f"  {Colors.RED}{title}{Colors.END}")
        elif collaboration_instructions["status"].get("level", "NA") == "SUCCESS":
            print(f"  {Colors.GREEN}{title}{Colors.END}")
        else:
            print("  " + title)
    if "msg" in collaboration_instructions["status"]:
        print(f'  {collaboration_instructions["status"]["msg"]}')


def _print_collaboration_instructions_items(
    *, collaboration_instructions: dict
) -> None:
    for item in collaboration_instructions["items"]:
        if "title" in item:
            if "level" in item:
                if item["level"] == "WARNING":
                    print(f"  {Colors.RED}{item['title']}{Colors.END}")
                elif item["level"] == "SUCCESS":
                    print(f"  {Colors.GREEN}{item['title']}{Colors.END}")
            else:
                print("  " + item["title"])

        if "msg" in item:
            print("  " + item["msg"])
        if "cmd_after" in item:
            print(f'  {item["cmd_after"]}')
        print()


def print_collaboration_instructions(
    *, status_operation: colrev.ops.status.Status, collaboration_instructions: dict
) -> None:
    """Print the collaboration instructions on cli"""

    if (
        not status_operation.review_manager.verbose_mode
        and collaboration_instructions["items"]
    ):
        if collaboration_instructions["items"][0]["title"] in [
            "Project not yet shared",
            "Up-to-date",
        ]:
            return

    print("Versioning and collaboration")
    _print_collaboration_instructions_status(
        collaboration_instructions=collaboration_instructions
    )
    _print_collaboration_instructions_items(
        collaboration_instructions=collaboration_instructions
    )


def print_environment_instructions(environment_instructions: dict) -> None:
    """Print the environment instructions on cli"""

    if not environment_instructions:
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
                print(f'  {Colors.ORANGE}{environment_instruction["cmd"]}{Colors.END}')
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
        desc="    Progress:",
        bar_format="{desc} |{bar}|{percentage:.0f}%",
        ncols=40,
    ):
        sleep(sleep_interval)
        if current_percentage in [i, -1]:
            break


def print_project_status(status_operation: colrev.ops.status.Status) -> None:
    """Print the project status on cli"""

    # pylint: disable=too-many-statements
    # pylint: disable=too-many-branches

    print("Load records...", end="\r")
    sys.stdout.write("\033[K")

    ret_check: typing.Dict[str, typing.Any] = {"status": ExitCodes.SUCCESS}
    failure_items = []
    try:
        checker = status_operation.review_manager.get_checker()
        failure_items.extend(checker.check_repo_basics())
    except colrev_exceptions.RepoSetupError as exc:
        ret_check = {"status": ExitCodes.FAIL, "msg": exc}

    try:
        advisor = status_operation.review_manager.get_advisor()
        status_stats = advisor.status_stats

        status_report = status_operation.get_review_status_report(
            records=checker.records
        )
        print(status_report)

        if (
            not status_stats.completeness_condition
            and status_operation.review_manager.verbose_mode
        ):
            print_progress(
                total_atomic_steps=status_stats.atomic_steps,
                completed_steps=status_stats.completed_atomic_steps,
            )
        print("")

        instructions = advisor.get_instructions()
        print_review_instructions(instructions["review_instructions"])
        print_collaboration_instructions(
            status_operation=status_operation,
            collaboration_instructions=instructions["collaboration_instructions"],
        )
        print_environment_instructions(instructions["environment_instructions"])

    except colrev_exceptions.RepoSetupError as exc:
        print(f"Status failed ({exc})")

    # if status_operation.review_manager.verbose_mode:
    #     print("Checks")

    try:
        failure_items.extend(checker.check_repo_extended())
    except colrev_exceptions.RepoSetupError as exc:
        ret_check = {"status": ExitCodes.FAIL, "msg": exc}

    if failure_items:
        ret_check = {"status": ExitCodes.FAIL, "msg": "  " + "\n  ".join(failure_items)}

    # if (
    #     ExitCodes.SUCCESS == ret_check["status"]
    #     and status_operation.review_manager.verbose_mode
    # ):
    #     print(
    #         "  ReviewManager.check_repo()  ...  "
    #         f"{Colors.GREEN}Everything ok.{Colors.END}"
    #     )
    if ExitCodes.FAIL == ret_check["status"]:
        # print(f"  ReviewManager.check_repo()  ...  {Colors.RED}FAIL{Colors.END}")
        # print(f'{ret_check["msg"]}\n')
        return

    # To format:
    # status_operation.review_manager.dataset.save_records_dict(checker.records)

    # if (
    #     not status_operation.review_manager.in_virtualenv()
    #     and status_operation.review_manager.verbose_mode
    # ):
    #     print(
    #         f"\n  {Colors.RED}WARNING{Colors.END} running scripts outside of virtualenv"
    #     )
    #     print(
    #         "  For instructions to set up a virtual environment, run\n"
    #         f"  {Colors.ORANGE}colrev show venv{Colors.END}"
    #     )
    #     print()

    if status_operation.review_manager.verbose_mode:
        print(
            "Documentation: https://colrev.readthedocs.io/en/latest/manual/manual.html"
        )
    else:
        print(f"For more details: {Colors.ORANGE}colrev status -v{Colors.END}")
