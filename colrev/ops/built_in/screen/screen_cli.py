#! /usr/bin/env python
"""Screen based on CLI"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from lxml.etree import XMLSyntaxError

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.screen.utils as util_cli_screen
import colrev.record
import colrev.settings
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.screen


@zope.interface.implementer(colrev.env.package_manager.ScreenPackageEndpointInterface)
@dataclass
class CoLRevCLIScreen(JsonSchemaMixin):
    """Screen documents using a CLI"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.__i = 0
        self.__pad = 0
        self.__stat_len = 0
        self.screening_criteria: dict = {}
        self.criteria_available = 0

    def __print_screening_criteria(
        self, *, screen_operation: colrev.ops.screen.Screen
    ) -> None:
        if not screen_operation.review_manager.settings.screen.criteria:
            return
        print("\nIn the screen, the following criteria are applied:\n")
        for (
            criterion_name,
            criterion_settings,
        ) in screen_operation.review_manager.settings.screen.criteria.items():
            color = colors.GREEN
            if (
                colrev.settings.ScreenCriterionType.exclusion_criterion
                == criterion_settings.criterion_type
            ):
                color = colors.RED
            print(
                f" - {criterion_name} "
                f"({color}{criterion_settings.criterion_type}{colors.END}): "
                f"{criterion_settings.explanation}"
            )
            if criterion_settings.comment != "":
                print(f"   {criterion_settings.comment}")

    def __screen_with_criteria_print_overall_decision(
        self, *, record: colrev.record.Record, screen_inclusion: bool
    ) -> None:
        if screen_inclusion:
            print(
                f"Overall screening decision for {record.data['ID']}: "
                f"{colors.GREEN}include{colors.END}"
            )
        else:
            print(
                f"Overall screening decision for {record.data['ID']}: "
                f"{colors.RED}exclude{colors.END}"
            )

    def __screen_record_with_criteria(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        record: colrev.record.Record,
        abstract_from_tei: bool,
    ) -> str:
        decisions = []
        quit_pressed, skip_pressed = False, False

        for criterion_name, criterion_settings in self.screening_criteria.items():
            decision, ret = "NA", "NA"
            while ret not in ["y", "n", "q", "s"]:
                color = colors.GREEN
                if (
                    colrev.settings.ScreenCriterionType.exclusion_criterion
                    == criterion_settings.criterion_type
                ):
                    color = colors.RED

                ret = input(
                    # is relevant / should be in the sample / should be retained
                    # ({self.__i}/{self.__stat_len})
                    f"Record should be included according to"
                    f" {criterion_settings.criterion_type}"
                    f" {color}{criterion_name}{colors.END}"
                    " [y,n,q,s for yes,no,quit,skip to decide later]? "
                )
                if ret == "q":
                    quit_pressed = True
                elif ret == "s":
                    skip_pressed = True
                    continue
                elif ret in ["y", "n"]:
                    decision = ret

            if quit_pressed:
                return "quit"
            if skip_pressed:
                return "skip"

            decision = decision.replace("n", "out").replace("y", "in")
            decisions.append([criterion_name, decision])

        c_field = ""
        for criterion_name, decision in decisions:
            c_field += f";{criterion_name}={decision}"
        c_field = c_field.replace(" ", "").lstrip(";")

        screen_inclusion = all(decision == "in" for _, decision in decisions)
        self.__screen_with_criteria_print_overall_decision(
            record=record, screen_inclusion=screen_inclusion
        )

        if abstract_from_tei:
            if "abstract" in record.data:
                del record.data["abstract"]

        screen_operation.screen(
            record=record,
            screen_inclusion=screen_inclusion,
            screening_criteria=c_field,
            PAD=self.__pad,
        )
        return "screened"

    def __screen_record_without_criteria(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        record: colrev.record.Record,
        abstract_from_tei: bool,
    ) -> str:
        quit_pressed = False
        decision, ret = "NA", "NA"
        while ret not in ["y", "n", "q", "s"]:
            ret = input(
                f"({self.__i}/{self.__stat_len}) "
                "Include [y,n,q,s for yes, no, quit, skip/screen later]? "
            )
            if ret == "q":
                quit_pressed = True
            elif ret == "s":
                return "skip"
            elif ret in ["y", "n"]:
                decision = ret

        if quit_pressed:
            screen_operation.review_manager.logger.info("Stop screen")
            return "quit"

        if abstract_from_tei:
            if "abstract" in record.data:
                del record.data["abstract"]
        if decision == "y":
            screen_operation.screen(
                record=record,
                screen_inclusion=True,
                screening_criteria="NA",
            )
        if decision == "n":
            screen_operation.screen(
                record=record,
                screen_inclusion=False,
                screening_criteria="NA",
                PAD=self.__pad,
            )
        return "screened"

    def __screen_record(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        record_dict: dict,
    ) -> str:
        record = colrev.record.Record(data=record_dict)
        abstract_from_tei = False
        if (
            "abstract" not in record.data
            and Path(record.data.get("file", "")).suffix == ".pdf"
        ):
            try:
                abstract_from_tei = True
                tei = screen_operation.review_manager.get_tei(
                    pdf_path=Path(record.data["file"]),
                    tei_path=record.get_tei_filename(),
                )
                record.data["abstract"] = tei.get_abstract()
            except (colrev_exceptions.ServiceNotAvailableException, XMLSyntaxError):
                pass

        self.__i += 1
        print("\n\n")
        print(f"Record {self.__i} (of {self.__stat_len})")
        print(record)

        if self.criteria_available:
            ret = self.__screen_record_with_criteria(
                screen_operation=screen_operation,
                record=record,
                abstract_from_tei=abstract_from_tei,
            )

        else:
            ret = self.__screen_record_without_criteria(
                screen_operation=screen_operation,
                record=record,
                abstract_from_tei=abstract_from_tei,
            )

        return ret

    def __screen_cli(
        self, screen_operation: colrev.ops.screen.Screen, split: list
    ) -> dict:
        screen_data = screen_operation.get_data()
        self.__pad = screen_data["PAD"]
        self.__stat_len = screen_data["nr_tasks"]

        if 0 == self.__stat_len:
            screen_operation.review_manager.logger.info("No records to prescreen")

        records = screen_operation.review_manager.dataset.load_records_dict()

        self.__print_screening_criteria(screen_operation=screen_operation)

        self.screening_criteria = (
            util_cli_screen.get_screening_criteria_from_user_input(
                screen_operation=screen_operation, records=records
            )
        )
        self.criteria_available = len(self.screening_criteria.keys())

        for record_dict in screen_data["items"]:
            if len(split) > 0:
                if record_dict["ID"] not in split:
                    continue

            ret = self.__screen_record(
                screen_operation=screen_operation, record_dict=record_dict
            )

            if ret == "skip":
                continue
            if ret == "quit":
                screen_operation.review_manager.logger.info("Stop screen")
                break

        if self.__stat_len == 0:
            screen_operation.review_manager.logger.info("No records to screen")
            return records

        screen_operation.review_manager.dataset.add_record_changes()

        if self.__i < self.__stat_len:  # if records remain for screening
            if input("Create commit (y/n)?") != "y":
                return records

        screen_operation.review_manager.create_commit(
            msg="Screening (manual)", manual_author=True
        )
        return records

    def run_screen(
        self, screen_operation: colrev.ops.screen.Screen, records: dict, split: list
    ) -> dict:
        """Screen records based on a cli"""

        records = self.__screen_cli(screen_operation, split)

        return records


if __name__ == "__main__":
    pass
