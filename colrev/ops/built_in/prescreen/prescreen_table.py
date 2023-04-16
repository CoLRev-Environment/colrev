#! /usr/bin/env python
"""Prescreen based on a table"""
from __future__ import annotations

import csv
import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    if typing.TYPE_CHECKING:
        import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class TablePrescreen(JsonSchemaMixin):

    """Table-based prescreen (exported and imported)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False
    export_todos_only: bool = True

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def export_table(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
        export_table_format: str = "csv",
    ) -> None:
        """Export a prescreen table"""

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/73
        # add delta (records not yet in the table)
        # instead of overwriting
        # export_table_format as a settings parameter

        prescreen_operation.review_manager.logger.info("Loading records for export")

        tbl = []
        for record in records.values():
            if record["colrev_status"] not in [
                colrev.record.RecordState.md_processed,
                colrev.record.RecordState.rev_prescreen_excluded,
                colrev.record.RecordState.rev_prescreen_included,
                colrev.record.RecordState.pdf_needs_manual_retrieval,
                colrev.record.RecordState.pdf_imported,
                colrev.record.RecordState.pdf_not_available,
                colrev.record.RecordState.pdf_needs_manual_preparation,
                colrev.record.RecordState.pdf_prepared,
                colrev.record.RecordState.rev_excluded,
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            if colrev.record.RecordState.md_processed == record["colrev_status"]:
                inclusion_1 = "TODO"
            elif self.export_todos_only:
                continue
            elif (
                colrev.record.RecordState.rev_prescreen_excluded
                == record["colrev_status"]
            ):
                inclusion_1 = "out"
            else:
                inclusion_1 = "in"

            # pylint: disable=duplicate-code
            row = {
                "ID": record["ID"],
                "author": record.get("author", ""),
                "title": record.get("title", ""),
                "journal": record.get("journal", ""),
                "booktitle": record.get("booktitle", ""),
                "year": record.get("year", ""),
                "volume": record.get("volume", ""),
                "number": record.get("number", ""),
                "pages": record.get("pages", ""),
                "doi": record.get("doi", ""),
                "abstract": record.get("abstract", ""),
                "presceen_inclusion": inclusion_1,
            }
            tbl.append(row)

        if export_table_format.lower() == "csv":
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("prescreen.csv", index=False, quoting=csv.QUOTE_ALL)
            prescreen_operation.review_manager.logger.info("Created prescreen.csv")

        if export_table_format.lower() == "xlsx":
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("prescreen.xlsx", index=False, sheet_name="screen")
            prescreen_operation.review_manager.logger.info("Created prescreen.xlsx")

        prescreen_operation.review_manager.logger.info(
            f"To prescreen records, {colors.ORANGE}enter [in|out] "
            f"in the presceen_inclusion column.{colors.END}"
        )
        prescreen_operation.review_manager.logger.info(
            f"Afterwards, run {colors.ORANGE}colrev prescreen --import_table "
            f"prescreen.{export_table_format.lower()}{colors.END}"
        )

    def import_table(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        import_table_path: str = "prescreen.csv",
    ) -> None:
        """Import a prescreen table"""

        # pylint: disable=too-many-branches

        prescreen_operation.review_manager.logger.info(f"Load {import_table_path}")

        # pylint: disable=duplicate-code
        if not Path(import_table_path).is_file():
            prescreen_operation.review_manager.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        prescreen_df = pd.read_csv(import_table_path)
        prescreen_df.fillna("", inplace=True)
        prescreened_records = prescreen_df.to_dict("records")

        if "presceen_inclusion" not in prescreened_records[0]:
            prescreen_operation.review_manager.logger.warning(
                "presceen_inclusion column missing"
            )
            return

        prescreen_included = 0
        prescreen_excluded = 0
        nr_todo = 0
        prescreen_operation.review_manager.logger.info("Update prescreen results")
        for prescreened_record in prescreened_records:
            if prescreened_record.get("ID", "") in records:
                record = colrev.record.Record(
                    data=records[prescreened_record.get("ID", "")]
                )
                if record.data[
                    "colrev_status"
                ] in colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.rev_prescreen_included
                ):
                    if (
                        "in" == prescreened_record.data.get("presceen_inclusion", "")
                        and colrev.record.RecordState.rev_prescreen_excluded
                        != record.data["colrev_status"]
                    ):
                        continue

                if prescreened_record.get("presceen_inclusion", "") == "out":
                    if (
                        record.data["colrev_status"]
                        != colrev.record.RecordState.rev_prescreen_excluded
                    ):
                        prescreen_excluded += 1
                    record.set_status(
                        target_state=colrev.record.RecordState.rev_prescreen_excluded
                    )

                elif prescreened_record.get("presceen_inclusion", "") == "in":
                    if (
                        record.data["colrev_status"]
                        != colrev.record.RecordState.rev_prescreen_included
                    ):
                        prescreen_included += 1
                    record.set_status(
                        target_state=colrev.record.RecordState.rev_prescreen_included
                    )
                elif prescreened_record.get("presceen_inclusion", "") == "TODO":
                    nr_todo += 1
                else:
                    prescreen_operation.review_manager.logger.warning(
                        "Invalid value in prescreen_inclusion: "
                        f"{prescreened_record.get('presceen_inclusion', '')} "
                        f"({prescreened_record.get('ID', 'NO_ID')})"
                    )

            else:
                prescreen_operation.review_manager.logger.warning(
                    f"ID not in records: {prescreened_record.get('ID', '')}"
                )

        prescreen_operation.review_manager.logger.info(
            f" {colors.GREEN}{prescreen_included} records prescreen_included{colors.END}"
        )
        prescreen_operation.review_manager.logger.info(
            f" {colors.RED}{prescreen_excluded} records prescreen_excluded{colors.END}"
        )

        prescreen_operation.review_manager.logger.info(
            f" {colors.ORANGE}{nr_todo} records to prescreen{colors.END}"
        )

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()

        prescreen_operation.review_manager.logger.info("Completed import")

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on screening tables"""

        if input("create prescreen table [y,n]?") == "y":
            self.export_table(
                prescreen_operation=prescreen_operation, records=records, split=split
            )

        if input("import prescreen table [y,n]?") == "y":
            self.import_table(prescreen_operation=prescreen_operation, records=records)

        if prescreen_operation.review_manager.dataset.has_changes():
            if input("create commit [y,n]?") == "y":
                prescreen_operation.review_manager.create_commit(
                    msg="Pre-screen (table)",
                    manual_author=True,
                )
        return records


if __name__ == "__main__":
    pass
