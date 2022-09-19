#! /usr/bin/env python
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.ops.built_in.screen.utils as util_cli_screen
import colrev.record
import colrev.settings
import colrev.ui_cli.cli_colors as colors

if TYPE_CHECKING:
    import colrev.ops.screen


@zope.interface.implementer(colrev.env.package_manager.ScreenPackageInterface)
class CoLRevCLIScreen:
    """Screen documents using a CLI"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

        self.__i = 0
        self.__pad = 0
        self.__stat_len = 0
        self.screening_criteria: dict = {}
        self.criteria_available = 0

    def __print_screening_criteria(
        self, *, screen_operation: colrev.ops.screen.Screen
    ) -> None:
        print("\n\nIn the screen, the following criteria are applied:\n")
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

    def __screen_record(
        self,
        *,
        screen_operation: colrev.ops.screen.Screen,
        screen_record: colrev.record.ScreenRecord,
    ) -> str:

        # pylint: disable=too-many-branches

        print("\n\n")
        self.__i += 1
        quit_pressed, skip_pressed = False, False
        if self.criteria_available:
            decisions = []

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
                        f"({self.__i}/{self.__stat_len}) Record should be included according to"
                        f" {criterion_settings.criterion_type}"
                        f" {color}{criterion_name}{colors.END}"
                        " [y,n,q,s]? "
                    )
                    if "q" == ret:
                        quit_pressed = True
                    elif "s" == ret:
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

            screen_record.screen(
                review_manager=screen_operation.review_manager,
                screen_inclusion=screen_inclusion,
                screening_criteria=c_field,
                PAD=self.__pad,
            )

        else:

            decision, ret = "NA", "NA"
            while ret not in ["y", "n", "q", "s"]:
                ret = input(f"({self.__i}/{self.__stat_len}) Include [y,n,q,s]? ")
                if "q" == ret:
                    quit_pressed = True
                elif "s" == ret:
                    skip_pressed = True
                    return "skip"
                elif ret in ["y", "n"]:
                    decision = ret

            if quit_pressed:
                screen_operation.review_manager.logger.info("Stop screen")
                return "quit"

            if decision == "y":
                screen_record.screen(
                    review_manager=screen_operation.review_manager,
                    screen_inclusion=True,
                    screening_criteria="NA",
                )
            if decision == "n":
                screen_record.screen(
                    review_manager=screen_operation.review_manager,
                    screen_inclusion=False,
                    screening_criteria="NA",
                    PAD=self.__pad,
                )

        return "screened"

    def screen_cli(
        self, screen_operation: colrev.ops.screen.Screen, split: list
    ) -> dict:

        screen_data = screen_operation.get_data()
        self.__pad = screen_data["PAD"]
        self.__stat_len = screen_data["nr_tasks"]

        screen_operation.review_manager.logger.info("Start screen")

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

            screen_record = colrev.record.ScreenRecord(data=record_dict)
            abstract_from_tei = False
            if "abstract" not in screen_record.data:
                abstract_from_tei = True
                tei = screen_operation.review_manager.get_tei(
                    pdf_path=Path(screen_record.data["file"]),
                    tei_path=screen_record.get_tei_filename(),
                )
                screen_record.data["abstract"] = tei.get_abstract()

            print(screen_record)

            ret = self.__screen_record(
                screen_operation=screen_operation, screen_record=screen_record
            )

            if abstract_from_tei:
                del screen_record.data["abstract"]

            if "skip" == ret:
                continue
            if "quit" == ret:
                screen_operation.review_manager.logger.info("Stop screen")
                break

        if self.__stat_len == 0:
            screen_operation.review_manager.logger.info("No records to screen")
            return records

        screen_operation.review_manager.dataset.add_record_changes()

        if self.__i < self.__stat_len:  # if records remain for screening
            if "y" != input("Create commit (y/n)?"):
                return records

        screen_operation.review_manager.create_commit(
            msg="Screening (manual)", manual_author=True, saved_args=None
        )
        return records

    def run_screen(self, screen_operation, records: dict, split: list) -> dict:

        records = self.screen_cli(screen_operation, split)

        return records


if __name__ == "__main__":
    pass
