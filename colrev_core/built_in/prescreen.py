#! /usr/bin/env python
import csv
from pathlib import Path

import pandas as pd
import zope.interface

from colrev_core.process import PrescreenEndpoint
from colrev_core.record import Record
from colrev_core.record import RecordState


@zope.interface.implementer(PrescreenEndpoint)
class ScopePrescreenEndpoint:

    # TODO : move the scope settings to the parameters of this endpoint

    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        from colrev_core.settings import (
            TimeScopeFrom,
            TimeScopeTo,
            OutletInclusionScope,
            OutletExclusionScope,
            ENTRYTYPEScope,
            ComplementaryMaterialsScope,
        )

        def load_predatory_journals_beal() -> dict:

            import pkgutil

            predatory_journals = {}

            filedata = pkgutil.get_data(
                __name__, "../template/predatory_journals_beall.csv"
            )
            if filedata:
                for pj in filedata.decode("utf-8").splitlines():
                    predatory_journals[pj.lower()] = pj.lower()

            return predatory_journals

        predatory_journals_beal = load_predatory_journals_beal()

        saved_args = locals()
        PAD = 50
        for record in records.values():
            if record["colrev_status"] != RecordState.md_processed:
                continue

            # Note : LanguageScope is covered in prep
            # because dedupe cannot handle merges between languages

            for scope_restriction in PRESCREEN.REVIEW_MANAGER.settings.prescreen.scope:

                if isinstance(scope_restriction, ENTRYTYPEScope):
                    if record["ENTRYTYPE"] not in scope_restriction.ENTRYTYPEScope:
                        Record(data=record).prescreen_exclude(
                            reason="not in ENTRYTYPEScope"
                        )

                if isinstance(scope_restriction, OutletExclusionScope):
                    if "values" in scope_restriction.OutletExclusionScope:
                        for r in scope_restriction.OutletExclusionScope["values"]:
                            for key, value in r.items():
                                if key in record and record.get(key, "") == value:
                                    Record(data=record).prescreen_exclude(
                                        reason="in OutletExclusionScope"
                                    )
                    if "list" in scope_restriction.OutletExclusionScope:
                        for r in scope_restriction.OutletExclusionScope["list"]:
                            for key, value in r.items():
                                if (
                                    "resource" == key
                                    and "predatory_journals_beal" == value
                                ):
                                    if "journal" in record:
                                        if (
                                            record["journal"].lower()
                                            in predatory_journals_beal
                                        ):
                                            Record(data=record).prescreen_exclude(
                                                reason="predatory_journals_beal"
                                            )

                if isinstance(scope_restriction, TimeScopeFrom):
                    if int(record.get("year", 0)) < scope_restriction.TimeScopeFrom:
                        Record(data=record).prescreen_exclude(
                            reason="not in TimeScopeFrom "
                            f"(>{scope_restriction.TimeScopeFrom})"
                        )

                if isinstance(scope_restriction, TimeScopeTo):
                    if int(record.get("year", 5000)) > scope_restriction.TimeScopeTo:
                        Record(data=record).prescreen_exclude(
                            reason="not in TimeScopeTo "
                            f"(<{scope_restriction.TimeScopeTo})"
                        )

                if isinstance(scope_restriction, OutletInclusionScope):
                    in_outlet_scope = False
                    if "values" in scope_restriction.OutletInclusionScope:
                        for r in scope_restriction.OutletInclusionScope["values"]:
                            for key, value in r.items():
                                if key in record and record.get(key, "") == value:
                                    in_outlet_scope = True
                    if not in_outlet_scope:
                        Record(data=record).prescreen_exclude(
                            reason="not in OutletInclusionScope"
                        )

                # TODO : discuss whether we should move this to the prep scripts
                if isinstance(scope_restriction, ComplementaryMaterialsScope):
                    if scope_restriction.ComplementaryMaterialsScope:
                        if "title" in record:
                            # TODO : extend/test the following
                            if record["title"].lower() in [
                                "about our authors",
                                "editorial board",
                                "author index",
                                "contents",
                                "index of authors",
                                "list of reviewers",
                            ]:
                                Record(data=record).prescreen_exclude(
                                    reason="complementary material"
                                )

            if record["colrev_status"] == RecordState.rev_prescreen_excluded:
                PRESCREEN.REVIEW_MANAGER.report_logger.info(
                    f' {record["ID"]}'.ljust(PAD, " ")
                    + "Prescreen excluded (automatically)"
                )

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        PRESCREEN.REVIEW_MANAGER.create_commit(
            msg="Pre-screen (scope)", manual_author=False, saved_args=saved_args
        )
        return records


@zope.interface.implementer(PrescreenEndpoint)
class CoLRevCLIPrescreenEndpoint:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        from colrev.cli import prescreen_cli

        records = prescreen_cli(PRESCREEN, split)
        return records


@zope.interface.implementer(PrescreenEndpoint)
class ASReviewPrescreenEndpoint:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        print("TODO")
        return records


@zope.interface.implementer(PrescreenEndpoint)
class ConditionalPrescreenEndpoint:
    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:
        # TODO : conditions as a settings/parameter
        saved_args = locals()
        saved_args["include_all"] = ""
        PAD = 50
        for record in records.values():
            if record["colrev_status"] != RecordState.md_processed:
                continue
            PRESCREEN.REVIEW_MANAGER.report_logger.info(
                f' {record["ID"]}'.ljust(PAD, " ")
                + "Included in prescreen (automatically)"
            )
            record.update(colrev_status=RecordState.rev_prescreen_included)

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        PRESCREEN.REVIEW_MANAGER.create_commit(
            msg="Pre-screen (include_all)", manual_author=False, saved_args=saved_args
        )
        return records


@zope.interface.implementer(PrescreenEndpoint)
class SpreadsheetPrescreenEndpoint:
    @classmethod
    def export_table(cls, PRESCREEN, records, split, export_table_format="csv") -> None:
        # TODO : add delta (records not yet in the spreadsheet)
        # instead of overwriting
        # TODO : export_table_format as a settings parameter

        PRESCREEN.REVIEW_MANAGER.logger.info("Loading records for export")

        tbl = []
        for record in records.values():

            if record["colrev_status"] not in [
                RecordState.md_processed,
                RecordState.rev_prescreen_excluded,
                RecordState.rev_prescreen_included,
                RecordState.pdf_needs_manual_retrieval,
                RecordState.pdf_imported,
                RecordState.pdf_not_available,
                RecordState.pdf_needs_manual_preparation,
                RecordState.pdf_prepared,
                RecordState.rev_excluded,
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue

            if len(split) > 0:
                if record["ID"] not in split:
                    continue

            if RecordState.md_processed == record["colrev_status"]:
                inclusion_1 = "TODO"
            elif RecordState.rev_prescreen_excluded == record["colrev_status"]:
                inclusion_1 = "no"
            else:
                inclusion_1 = "yes"

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
            # row.update    (exclusion_criteria)
            tbl.append(row)

        if "csv" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_csv("prescreen.csv", index=False, quoting=csv.QUOTE_ALL)
            PRESCREEN.REVIEW_MANAGER.logger.info("Created prescreen.csv")

        if "xlsx" == export_table_format.lower():
            screen_df = pd.DataFrame(tbl)
            screen_df.to_excel("prescreen.xlsx", index=False, sheet_name="screen")
            PRESCREEN.REVIEW_MANAGER.logger.info("Created prescreen.xlsx")

        return

    @classmethod
    def import_table(
        cls, PRESCREEN, records, import_table_path="prescreen.csv"
    ) -> None:
        if not Path(import_table_path).is_file():
            PRESCREEN.REVIEW_MANAGER.logger.error(
                f"Did not find {import_table_path} - exiting."
            )
            return
        screen_df = pd.read_csv(import_table_path)
        screen_df.fillna("", inplace=True)
        screened_records = screen_df.to_dict("records")

        PRESCREEN.REVIEW_MANAGER.logger.warning(
            "import_table not completed (exclusion_criteria not yet imported)"
        )

        for screened_record in screened_records:
            if screened_record.get("ID", "") in records:
                record = records[screened_record.get("ID", "")]
                if "no" == screened_record.get("inclusion_1", ""):
                    record["colrev_status"] = RecordState.rev_prescreen_excluded
                if "yes" == screened_record.get("inclusion_1", ""):
                    record["colrev_status"] = RecordState.rev_prescreen_included

        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        return

    @classmethod
    def run_prescreen(cls, PRESCREEN, records: dict, split: list) -> dict:

        if "y" == input("create prescreen spreadsheet [y,n]?"):
            cls.export_table(PRESCREEN, records, split)

        if "y" == input("import prescreen spreadsheet [y,n]?"):
            cls.import_table(PRESCREEN, records)

        if PRESCREEN.REVIEW_MANAGER.REVIEW_DATASET.has_changes():
            if "y" == input("create commit [y,n]?"):
                PRESCREEN.REVIEW_MANAGER.create_commit(
                    msg="Pre-screen (spreadsheets)", manual_author=True
                )
        return records
