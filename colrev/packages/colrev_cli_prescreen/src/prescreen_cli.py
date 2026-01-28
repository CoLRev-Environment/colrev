#! /usr/bin/env python
"""Prescreen based on CLI"""

from __future__ import annotations

import logging
import textwrap
import typing
from pathlib import Path

from pydantic import Field

import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods


def _print_prescreen_record(record_dict: dict) -> None:
    """Print the record for prescreen operations"""

    ret_str = f"  ID: {record_dict['ID']} ({record_dict[Fields.ENTRYTYPE]})"
    ret_str += (
        f"\n  {Colors.GREEN}{record_dict.get(Fields.TITLE, 'no title')}{Colors.END}"
        f"\n  {record_dict.get(Fields.AUTHOR, 'no-author')}"
    )
    if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
        ret_str += (
            f"\n  {record_dict.get(Fields.JOURNAL, 'no-journal')} "
            f"({record_dict.get(Fields.YEAR, 'no-year')}) "
            f"{record_dict.get(Fields.VOLUME, 'no-volume')}"
            f"({record_dict.get(Fields.NUMBER, '')})"
        )
    elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
        ret_str += f"\n  {record_dict.get(Fields.BOOKTITLE, 'no-booktitle')}"
    if Fields.ABSTRACT in record_dict:
        lines = textwrap.wrap(record_dict[Fields.ABSTRACT], 100, break_long_words=False)
        if lines:
            ret_str += f"\n  Abstract: {lines.pop(0)}\n"
            ret_str += "\n  ".join(lines) + ""

    if Fields.URL in record_dict:
        ret_str += f"\n  url: {record_dict[Fields.URL]}"

    if Fields.FILE in record_dict:
        ret_str += f"\n  file: {record_dict[Fields.FILE]}"

    print(ret_str)


class CoLRevCLIPrescreen(base_classes.PrescreenPackageBaseClass):
    """CLI-based prescreen"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings

    ci_supported: bool = Field(default=False)

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
        self.prescreen_operation = prescreen_operation
        self.review_manager = prescreen_operation.review_manager

    def _fun_cli_prescreen(
        self,
        *,
        prescreen_data: dict,
        split: list,
        stat_len: int,
        padding: int,
    ) -> bool:
        self.logger.debug("Start prescreen")

        if 0 == stat_len:
            self.logger.info("No records to prescreen")

        i, quit_pressed = 0, False
        for record_dict in prescreen_data["items"]:
            if len(split) > 0:
                if record_dict[Fields.ID] not in split:
                    continue

            record = colrev.record.record.Record(record_dict)
            ret, inclusion_decision_str = "NA", "NA"
            i += 1

            print("\n\n")
            print(f"Record {i} (of {stat_len})\n")
            _print_prescreen_record(record.data)

            while ret not in ["y", "n", "s", "q"]:
                ret = input(
                    "\nInclude this record "
                    "[enter y,n,s,q for yes, no, skip/decide later, quit-and-save]? "
                )
                if ret == "q":
                    quit_pressed = True
                elif ret == "s":
                    continue
                else:
                    inclusion_decision_str = ret.replace("y", "yes").replace("n", "no")

            if quit_pressed:
                self.logger.info("Stop prescreen")
                break

            if ret == "s":
                continue

            inclusion_decision = "yes" == inclusion_decision_str

            self.prescreen_operation.prescreen(
                record=record,
                prescreen_inclusion=inclusion_decision,
                PAD=padding,
            )

        return i == stat_len

    def run_prescreen(
        self,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on a cli"""

        if not split:
            split = []

        prescreen_data = self.prescreen_operation.get_data()
        stat_len = len(split) if len(split) > 0 else prescreen_data["nr_tasks"]
        padding = prescreen_data["PAD"]

        self._fun_cli_prescreen(
            prescreen_data=prescreen_data,
            split=split,
            stat_len=stat_len,
            padding=padding,
        )

        # Note : currently, it is easier to create a commit in all cases.
        # Upon continuing the prescreen, the scope-based prescreen commits the changes,
        # which is misleading.
        # Users can still squash commits.
        # Note: original: completed = self._fun_cli_prescreen(...
        # if not completed:
        #     if input("Create commit (y/n)?") != "y":
        #         return records

        self.review_manager.create_commit(
            msg="Pre-screen: manual screen (cli)", manual_author=True
        )
        return records


def cli() -> None:
    import colrev.loader.load_utils
    import colrev.writer.write_utils

    # TODO: allow custom file selection
    filename = Path("records.bib")
    records_dict = colrev.loader.load_utils.load(filename=filename)
    for record_dict in records_dict.values():
        if record_dict["colrev_status"] != RecordState.md_processed:
            continue

        print("\n\n")
        _print_prescreen_record(record_dict)
        ret, inclusion_decision_str = "NA", "NA"
        quit_pressed = False

        while ret not in ["y", "n", "s", "q"]:
            ret = input(
                "\nInclude this record "
                "[enter y,n,s,q for yes, no, skip/decide later, quit-and-save]? "
            )
            if ret == "q":
                quit_pressed = True
            elif ret == "s":
                continue
            else:
                inclusion_decision_str = ret.replace("y", "yes").replace("n", "no")

        if quit_pressed:
            print("Stop prescreen")
            break

        if ret == "s":
            continue

        inclusion = "yes" == inclusion_decision_str

        if inclusion:
            record_dict["colrev_status"] = RecordState.rev_synthesized
        else:
            record_dict["colrev_status"] = RecordState.rev_excluded

    colrev.writer.write_utils.write_file(records_dict, filename=filename)
