#! /usr/bin/env python
"""CoLRev prep_man operation: Prepare metadata manually."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record_prep
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState


class PrepMan(colrev.process.operation.Operation):
    """Prepare records manually (metadata)"""

    type = OperationsType.prep_man

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True
        self.lang_prep_csv_path = self.review_manager.paths.prep / Path(
            "missing_lang_recs_df.csv"
        )

    def _get_crosstab_df(self) -> pd.DataFrame:
        # pylint: disable=too-many-branches
        # pylint: disable=duplicate-code

        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Calculate statistics")
        stats: dict = {Fields.ENTRYTYPE: {}}
        overall_types: dict = {Fields.ENTRYTYPE: {}}
        prep_man_hints, origins, crosstab = [], [], []
        for record_dict in records.values():
            if RecordState.md_imported != record_dict[Fields.STATUS]:
                if record_dict[Fields.ENTRYTYPE] in overall_types[Fields.ENTRYTYPE]:
                    overall_types[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] = (
                        overall_types[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]]
                        + 1
                    )
                else:
                    overall_types[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] = 1

            if RecordState.md_needs_manual_preparation != record_dict[Fields.STATUS]:
                continue

            if record_dict[Fields.ENTRYTYPE] in stats[Fields.ENTRYTYPE]:
                stats[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] = (
                    stats[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] + 1
                )
            else:
                stats[Fields.ENTRYTYPE][record_dict[Fields.ENTRYTYPE]] = 1

            if Fields.MD_PROV in record_dict:
                record = colrev.record.record_prep.PrepRecord(record_dict)
                prov_d = record.data[Fields.MD_PROV]
                hints = []
                for key, value in prov_d.items():
                    if value["note"] != "":
                        hints.append(f'{key} - {value["note"]}')

                prep_man_hints.append([hint.lstrip() for hint in hints])
                for hint in hints:
                    if "change-score" in hint:
                        continue
                    # Note: if something causes the needs_manual_preparation
                    # it is caused by all colrev_origins
                    for orig in record_dict.get(Fields.ORIGIN, ["NA"]):
                        crosstab.append([orig[: orig.rfind("/")], hint.lstrip()])

            origins.append(
                [x[: x.rfind("/")] for x in record_dict.get(Fields.ORIGIN, ["NA"])]
            )

        print("Entry type statistics overall:")
        self.review_manager.p_printer.pprint(overall_types[Fields.ENTRYTYPE])

        print("Entry type statistics (needs_manual_preparation):")
        self.review_manager.p_printer.pprint(stats[Fields.ENTRYTYPE])

        return pd.DataFrame(crosstab, columns=[Fields.ORIGIN, "hint"])

    def _export_prep_man_langs(self, records: dict) -> None:
        language_service = colrev.env.language_service.LanguageService()

        missing_lang_recs = []
        self.review_manager.logger.info(
            "Calculate most likely languages for records without language field"
        )
        for record in tqdm(records.values()):
            if Fields.TITLE not in record:
                continue
            if Fields.LANGUAGE not in record:
                confidence_values = language_service.compute_language_confidence_values(
                    text=record[Fields.TITLE]
                )
                predicted_language, conf = confidence_values.pop(0)

                lang_rec = {
                    Fields.ID: record[Fields.ID],
                    Fields.TITLE: record[Fields.TITLE],
                    "most_likely_language": predicted_language,
                    "confidence": conf,
                }
                missing_lang_recs.append(lang_rec)

        missing_lang_recs_df = pd.DataFrame(missing_lang_recs)
        missing_lang_recs_df.to_csv(
            self.lang_prep_csv_path, index=False, quoting=csv.QUOTE_ALL
        )
        self.review_manager.logger.info(f"Exported table to {self.lang_prep_csv_path}")
        self.review_manager.logger.info(
            "Update the language column and rerun colrev prep-man -l"
        )

    def _import_prep_man_langs(self, records: dict) -> None:
        self.review_manager.logger.info(
            f"Import language fields from {self.lang_prep_csv_path}"
        )
        languages_df = pd.read_csv(self.lang_prep_csv_path)
        language_records = languages_df.to_dict("records")
        for language_record in language_records:
            if language_record["most_likely_language"] == "":
                continue
            if language_record[Fields.ID] not in records:
                # warn
                continue
            record_dict = records[language_record[Fields.ID]]
            record = colrev.record.record_prep.PrepRecord(record_dict)
            record.update_field(
                key=Fields.LANGUAGE,
                value=language_record["most_likely_language"],
                source="LanguageDetector/Manual",
                note="",
            )

            if "language of title not in [eng]" == record.data.get(
                Fields.PRESCREEN_EXCLUSION, ""
            ):
                record.remove_field(key=Fields.PRESCREEN_EXCLUSION)
                record.remove_field_provenance_note(
                    key=Fields.TITLE, note="language-not-found"
                )
                if (
                    record.data[Fields.STATUS]
                    == RecordState.md_needs_manual_preparation
                ):
                    # by resetting to md_imported,
                    # the prescreen-exclusion based on languages will be reapplied.
                    record.set_status(RecordState.md_imported)

        self.review_manager.dataset.save_records_dict(records)

    def prep_man_langs(self) -> None:
        """Add missing language fields based on spreadsheets"""

        self.lang_prep_csv_path.parent.mkdir(exist_ok=True, parents=True)

        records = self.review_manager.dataset.load_records_dict()

        if not self.lang_prep_csv_path.is_file():
            self._export_prep_man_langs(records)

        else:
            self._import_prep_man_langs(records)

    def prep_man_stats(self) -> None:
        """Print statistics on prep_man"""
        # pylint: disable=duplicate-code

        crosstab_df = self._get_crosstab_df()

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            # pylint: disable=duplicate-code
            tabulated = pd.pivot_table(
                crosstab_df[[Fields.ORIGIN, "hint"]],
                index=[Fields.ORIGIN],
                columns=["hint"],
                aggfunc=len,
                fill_value=0,
                margins=True,
            )
            # .sort_index(axis='columns')
            tabulated.sort_values(by=["All"], ascending=False, inplace=True)
            # Transpose because we tend to have more error categories than search files.
            tabulated = tabulated.transpose()
            print(tabulated)
            self.review_manager.logger.info(
                "Writing data to file: manual_preparation_statistics.csv"
            )
            tabulated.to_csv("manual_preparation_statistics.csv")

    def get_data(self) -> dict:
        """Get the data for prep-man"""
        # pylint: disable=duplicate-code

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if RecordState.md_needs_manual_preparation == x[Fields.STATUS]
            ]
        )

        all_ids = [x[Fields.ID] for x in record_header_list]

        pad = min((max(len(x[Fields.ID]) for x in record_header_list) + 2), 35)

        items = self.review_manager.dataset.read_next_record(
            conditions=[{Fields.STATUS: RecordState.md_needs_manual_preparation}]
        )

        md_prep_man_data = {
            "nr_tasks": nr_tasks,
            "items": items,
            "all_ids": all_ids,
            "PAD": pad,
        }
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(md_prep_man_data)
        )
        return md_prep_man_data

    def set_data(self, *, record_dict: dict) -> None:
        """Set data in the prep_man operation"""

        record = colrev.record.record_prep.PrepRecord(record_dict)
        record.set_masterdata_complete(
            source="prep_man",
            masterdata_repository=self.review_manager.settings.is_curated_repo(),
        )
        record.set_masterdata_consistent()
        # record.set_fields_complete()
        record.set_status(RecordState.md_prepared)
        record_dict = record.get_data()

        self.review_manager.dataset.save_records_dict(
            {record_dict[Fields.ID]: record_dict}, partial=True
        )

    @colrev.process.operation.Operation.decorate()
    def main(self) -> None:
        """Manually prepare records (main entrypoint)"""

        if (
            self.review_manager.in_ci_environment()
            and not self.review_manager.in_test_environment()
        ):
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev prep-man",
                detailed_trace="prep-man not available in ci environment",
            )

        records = self.review_manager.dataset.load_records_dict()

        package_manager = self.review_manager.get_package_manager()

        for (
            prep_man_package_endpoint
        ) in self.review_manager.settings.prep.prep_man_package_endpoints:
            prep_man_class = package_manager.get_package_endpoint_class(
                package_type=EndpointType.prep_man,
                package_identifier=prep_man_package_endpoint["endpoint"],
            )
            endpoint = prep_man_class(
                prep_man_operation=self, settings=prep_man_package_endpoint
            )
            records = endpoint.prepare_manual(records)  # type: ignore
