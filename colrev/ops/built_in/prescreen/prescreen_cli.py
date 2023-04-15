#! /usr/bin/env python
"""Prescreen based on CLI"""
from __future__ import annotations

import typing
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
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
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __fun_cli_prescreen(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        prescreen_data: dict,
        split: list,
        stat_len: int,
        padding: int,
    ) -> bool:
        if prescreen_operation.review_manager.settings.prescreen.explanation == "":
            print(
                f"\n{colors.ORANGE}Provide a short explanation of the prescreen{colors.END} "
                "(why should particular papers be included?):"
            )
            print(
                'Example objective: "Include papers that focus on digital technology."'
            )
            prescreen_operation.review_manager.settings.prescreen.explanation = input(
                ""
            )
            prescreen_operation.review_manager.save_settings()
        else:
            print("\nIn the prescreen, the following process is followed:\n")
            print(
                "   "
                + prescreen_operation.review_manager.settings.prescreen.explanation
            )
            print()

        prescreen_operation.review_manager.logger.debug("Start prescreen")

        if 0 == stat_len:
            prescreen_operation.review_manager.logger.info("No records to prescreen")

        i, quit_pressed = 0, False
        for record_dict in prescreen_data["items"]:
            if len(split) > 0:
                if record_dict["ID"] not in split:
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
                prescreen_operation.review_manager.logger.info("Stop prescreen")
                break

            if ret == "s":
                continue

            inclusion_decision = "yes" == inclusion_decision_str
            prescreen_operation.prescreen(
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
            prescreen_operation=prescreen_operation,
            prescreen_data=prescreen_data,
            split=split,
            stat_len=stat_len,
            padding=padding,
        )

        # records = prescreen_operation.review_manager.dataset.load_records_dict()
        # prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()

        # Note : currently, it is easier to create a commit in all cases.
        # Upon continuing the prescreen, the scope-based prescreen commits the changes,
        # which is misleading.
        # Users can still squash commits.
        # Note: originall: completed = self.__fun_cli_prescreen(...
        # if not completed:
        #     if input("Create commit (y/n)?") != "y":
        #         return records

        prescreen_operation.review_manager.create_commit(
            msg="Pre-screening (manual)", manual_author=True
        )
        return records


if __name__ == "__main__":
    pass
