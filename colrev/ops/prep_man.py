#! /usr/bin/env python
"""CoLRev prep_man operation: Prepare metadata manually."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
from tqdm import tqdm

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


class PrepMan(colrev.operation.Operation):
    """Prepare records manually (metadata)"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.prep_man,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

    def __get_crosstab_df(self) -> pd.DataFrame:
        # pylint: disable=too-many-branches
        # pylint: disable=duplicate-code

        records = self.review_manager.dataset.load_records_dict()

        self.review_manager.logger.info("Calculate statistics")
        stats: dict = {"ENTRYTYPE": {}}
        overall_types: dict = {"ENTRYTYPE": {}}
        prep_man_hints, origins, crosstab = [], [], []
        for record_dict in records.values():
            if colrev.record.RecordState.md_imported != record_dict["colrev_status"]:
                if record_dict["ENTRYTYPE"] in overall_types["ENTRYTYPE"]:
                    overall_types["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = (
                        overall_types["ENTRYTYPE"][record_dict["ENTRYTYPE"]] + 1
                    )
                else:
                    overall_types["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = 1

            if (
                colrev.record.RecordState.md_needs_manual_preparation
                != record_dict["colrev_status"]
            ):
                continue

            if record_dict["ENTRYTYPE"] in stats["ENTRYTYPE"]:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = (
                    stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] + 1
                )
            else:
                stats["ENTRYTYPE"][record_dict["ENTRYTYPE"]] = 1

            if "colrev_masterdata_provenance" in record_dict:
                record = colrev.record.Record(data=record_dict)
                prov_d = record.data["colrev_masterdata_provenance"]
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
                    for orig in record_dict.get("colrev_origin", ["NA"]):
                        crosstab.append([orig[: orig.rfind("/")], hint.lstrip()])

            origins.append(
                [x[: x.rfind("/")] for x in record_dict.get("colrev_origin", ["NA"])]
            )

        print("Entry type statistics overall:")
        self.review_manager.p_printer.pprint(overall_types["ENTRYTYPE"])

        print("Entry type statistics (needs_manual_preparation):")
        self.review_manager.p_printer.pprint(stats["ENTRYTYPE"])

        return pd.DataFrame(crosstab, columns=["colrev_origin", "hint"])

    def prep_man_langs(self) -> None:
        """Add missing language fields based on spreadsheets"""

        lang_prep_csv_path = self.review_manager.prep_dir / Path(
            "missing_lang_recs_df.csv"
        )
        lang_prep_csv_path.parent.mkdir(exist_ok=True, parents=True)

        records = self.review_manager.dataset.load_records_dict()

        if not lang_prep_csv_path.is_file():
            language_service = colrev.env.language_service.LanguageService()

            missing_lang_recs = []
            self.review_manager.logger.info(
                "Calculate most likely languages for records without language field"
            )
            for record in tqdm(records.values()):
                if "title" not in record:
                    continue
                if "language" not in record:
                    confidence_values = (
                        language_service.compute_language_confidence_values(
                            text=record["title"]
                        )
                    )
                    predicted_language, conf = confidence_values.pop(0)

                    lang_rec = {
                        "ID": record["ID"],
                        "title": record["title"],
                        "most_likely_language": predicted_language,
                        "confidence": conf,
                    }
                    missing_lang_recs.append(lang_rec)

            missing_lang_recs_df = pd.DataFrame(missing_lang_recs)
            missing_lang_recs_df.to_csv(
                lang_prep_csv_path, index=False, quoting=csv.QUOTE_ALL
            )
            self.review_manager.logger.info(f"Exported table to {lang_prep_csv_path}")
            self.review_manager.logger.info(
                "Update the language column and rerun colrev prep-man -l"
            )

        else:
            self.review_manager.logger.info(
                f"Import language fields from {lang_prep_csv_path}"
            )
            languages_df = pd.read_csv(lang_prep_csv_path)
            language_records = languages_df.to_dict("records")
            for language_record in language_records:
                if language_record["most_likely_language"] == "":
                    continue
                if language_record["ID"] not in records:
                    # warn
                    continue
                record_dict = records[language_record["ID"]]
                record = colrev.record.Record(data=record_dict)
                record.update_field(
                    key="language",
                    value=language_record["most_likely_language"],
                    source="LanguageDetector/Manual",
                    note="",
                )
                if "language of title not in [eng]" == record.data.get(
                    "prescreen_exclusion", ""
                ):
                    record.remove_field(key="prescreen_exclusion")
                    if "title" in record.data["colrev_masterdata_provenance"]:
                        record.data["colrev_masterdata_provenance"]["title"][
                            "note"
                        ] = ""
                    if (
                        record.data["colrev_status"]
                        == colrev.record.RecordState.md_needs_manual_preparation
                    ):
                        # by resetting to md_imported,
                        # the prescreen-exclusion based on languages will be reapplied.
                        record.set_status(
                            target_state=colrev.record.RecordState.md_imported
                        )

            self.review_manager.dataset.save_records_dict(records=records)

    def prep_man_stats(self) -> None:
        """Print statistics on prep_man"""
        # pylint: disable=duplicate-code

        crosstab_df = self.__get_crosstab_df()

        if crosstab_df.empty:
            print("No records to prepare manually.")
        else:
            # pylint: disable=duplicate-code
            tabulated = pd.pivot_table(
                crosstab_df[["colrev_origin", "hint"]],
                index=["colrev_origin"],
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
                if colrev.record.RecordState.md_needs_manual_preparation
                == x["colrev_status"]
            ]
        )

        all_ids = [x["ID"] for x in record_header_list]

        pad = min((max(len(x["ID"]) for x in record_header_list) + 2), 35)

        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {"colrev_status": colrev.record.RecordState.md_needs_manual_preparation}
            ]
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

        record = colrev.record.PrepRecord(data=record_dict)
        record.set_masterdata_complete(source="prep_man")
        record.set_masterdata_consistent()
        record.set_fields_complete()
        record.set_status(target_state=colrev.record.RecordState.md_prepared)
        record_dict = record.get_data()

        self.review_manager.dataset.save_records_dict(
            records={record_dict["ID"]: record_dict}, partial=True
        )
        self.review_manager.dataset.add_record_changes()

    def main(self) -> None:
        """Manually prepare records (main entrypoint)"""

        if self.review_manager.in_ci_environment():
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev prep-man",
                detailed_trace="prep-man not available in ci environment",
            )

        records = self.review_manager.dataset.load_records_dict()

        package_manager = self.review_manager.get_package_manager()

        for (
            prep_man_package_endpoint
        ) in self.review_manager.settings.prep.prep_man_package_endpoints:
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.prep_man,
                selected_packages=self.review_manager.settings.prep.prep_man_package_endpoints,
                operation=self,
            )
            endpoint = endpoint_dict[prep_man_package_endpoint["endpoint"]]
            records = endpoint.prepare_manual(self, records)  # type: ignore


if __name__ == "__main__":
    pass
