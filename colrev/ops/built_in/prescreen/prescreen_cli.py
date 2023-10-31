#! /usr/bin/env python
"""Prescreen based on CLI"""
from __future__ import annotations

import typing
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record
from colrev.constants import Colors
from colrev.constants import Fields

if typing.TYPE_CHECKING:
    import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class CoLRevCLIPrescreen(JsonSchemaMixin):

    """CLI-based prescreen"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.prescreen_operation = prescreen_operation
        self.review_manager = prescreen_operation.review_manager

    def __fun_cli_prescreen(
        self,
        *,
        prescreen_data: dict,
        split: list,
        stat_len: int,
        padding: int,
    ) -> bool:
        if self.review_manager.settings.prescreen.explanation == "":
            print(
                f"\n{Colors.ORANGE}Provide a short explanation of the prescreen{Colors.END} "
                "(why should particular papers be included?):"
            )
            print(
                'Example objective: "Include papers that focus on digital technology."'
            )
            self.review_manager.settings.prescreen.explanation = input("")
            self.review_manager.save_settings()
        else:
            print("\nIn the prescreen, the following process is followed:\n")
            print("   " + self.review_manager.settings.prescreen.explanation)
            print()

        self.review_manager.logger.debug("Start prescreen")

        if 0 == stat_len:
            self.review_manager.logger.info("No records to prescreen")

        i, quit_pressed = 0, False
        for record_dict in prescreen_data["items"]:
            if len(split) > 0:
                if record_dict[Fields.ID] not in split:
                    continue

            record = colrev.record.Record(data=record_dict)
            ret, inclusion_decision_str = "NA", "NA"
            i += 1

            print("\n\n")
            print(f"Record {i} (of {stat_len})\n")
            record.print_prescreen_record()

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
                self.review_manager.logger.info("Stop prescreen")
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
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on a cli"""

        if not split:
            split = []

        prescreen_data = prescreen_operation.get_data()
        stat_len = len(split) if len(split) > 0 else prescreen_data["nr_tasks"]
        padding = prescreen_data["PAD"]

        self.__fun_cli_prescreen(
            prescreen_data=prescreen_data,
            split=split,
            stat_len=stat_len,
            padding=padding,
        )

        # Note : currently, it is easier to create a commit in all cases.
        # Upon continuing the prescreen, the scope-based prescreen commits the changes,
        # which is misleading.
        # Users can still squash commits.
        # Note: originall: completed = self.__fun_cli_prescreen(...
        # if not completed:
        #     if input("Create commit (y/n)?") != "y":
        #         return records

        self.review_manager.create_commit(
            msg="Pre-screening (manual)", manual_author=True
        )
        return records
