#! /usr/bin/env python
"""Utils for deduplication"""
import os
import time

import colrev.record

# pylint: disable=too-many-arguments


def console_duplicate_instance_label(
    record_pair: list,
    keys: list,
    manual: bool,
    index_dupe_info: str,
    n_match: int,
    n_distinct: int,
    examples_buffer: list,
) -> str:

    if manual:
        os.system("cls" if os.name == "nt" else "clear")
        colrev.record.Record.print_diff_pair(record_pair=record_pair, keys=keys)

    user_input = "unsure"
    if "yes" == index_dupe_info:
        user_input = "y"
        if manual:
            print(f"{n_match} positive, {n_distinct} negative")
            print("#")
            print("# index_dupe_info: yes/duplicate")
            print("#")
            # TODO : add option to validate explicitly  (Enter to confirm)
            time.sleep(0.6)
    elif "no" == index_dupe_info:
        user_input = "n"
        if manual:
            print(f"{n_match} positive, {n_distinct} negative")
            print("#")
            print("# index_dupe_info: no duplicate")
            print("#")
            # TODO : add option to validate explicitly  (Enter to confirm)
            time.sleep(0.6)
    else:
        if manual:
            print(f"{n_match} positive, {n_distinct} negative")

        if manual:
            valid_response = False
            user_input = ""

            while not valid_response:
                if examples_buffer:
                    prompt = (
                        "Duplicate? (y)es / (n)o / (u)nsure /"
                        + " (f)inished / (p)revious"
                    )
                    valid_responses = {"y", "n", "u", "f", "p"}
                else:
                    prompt = "Duplicate? (y)es / (n)o / (u)nsure / (f)inished"
                    valid_responses = {"y", "n", "u", "f"}

                print(prompt)
                user_input = input()
                if user_input in valid_responses:
                    valid_response = True
    return user_input


if __name__ == "__main__":
    pass
