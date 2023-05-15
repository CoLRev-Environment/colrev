#! /usr/bin/env python
"""Checker for missing fields."""
from __future__ import annotations

from typing import Set

import colrev.exceptions as colrev_exceptions
import colrev.qm.quality_model
import colrev.record

# pylint: disable=too-few-public-methods


class MissingFieldChecker:
    """The MissingFieldChecker"""

    # Based on https://en.wikipedia.org/wiki/BibTeX
    record_field_requirements = {
        "article": ["author", "title", "journal", "year", "volume", "number"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "incollection": ["author", "title", "booktitle", "publisher", "year"],
        "inbook": ["author", "title", "chapter", "publisher", "year"],
        "proceedings": ["booktitle", "editor"],
        "book": ["author", "title", "publisher", "year"],
        "phdthesis": ["author", "title", "school", "year"],
        "masterthesis": ["author", "title", "school", "year"],
        "techreport": ["author", "title", "institution", "year"],
        "unpublished": ["title", "author", "year"],
        "misc": ["author", "title", "year"],
        "software": ["author", "title", "url"],
        "other": ["author", "title", "year"],
    }
    """Fields requirements for respective ENTRYTYPE"""

    # book, inbook: author <- editor

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model
        self.masterdata_restrictions = self.__get_masterdata_restrictions()

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the missing-field checks"""

        if self.masterdata_restrictions:
            self.__check_completeness_curated_masterdata(
                record=record, masterdata_restrictions=self.masterdata_restrictions
            )
        else:
            self.__check_completeness(record=record)

        missing_fields = self.__check_missing_fiels(record=record)

        self.__check_forthcoming(record=record, missing_fields=missing_fields)

        if not missing_fields:
            record.set_masterdata_complete(
                source="update_masterdata_provenance",
                replace_source=False,
            )

    def get_missing_fields(self, *, record: colrev.record.Record) -> set:
        """Get the missing fields"""
        missing_field_keys = set()
        if record.data["ENTRYTYPE"] in self.record_field_requirements:
            reqs = self.record_field_requirements[record.data["ENTRYTYPE"]]
            missing_field_keys = {
                x
                for x in reqs
                if x not in record.data.keys()
                or "" == record.data[x]
                or "UNKNOWN" == record.data[x]
            }
            return missing_field_keys
        raise colrev_exceptions.MissingRecordQualityRuleSpecification(
            msg=f"Missing record_field_requirements for {record.data['ENTRYTYPE']}"
        )

    def __check_forthcoming(
        self, *, record: colrev.record.Record, missing_fields: set
    ) -> None:
        if record.data.get("year", "") != "forthcoming":
            return
        source = "NA"
        if "year" in record.data["colrev_masterdata_provenance"]:
            source = record.data["colrev_masterdata_provenance"]["year"]["source"]
        if "volume" in missing_fields:
            missing_fields.remove("volume")
            record.data["colrev_masterdata_provenance"]["volume"] = {
                "source": source,
                "note": "not-missing",
            }
        if "number" in missing_fields:
            missing_fields.remove("number")
            record.data["colrev_masterdata_provenance"]["number"] = {
                "source": source,
                "note": "not-missing",
            }

    def __check_missing_fiels(self, *, record: colrev.record.Record) -> set:
        missing_fields: Set[str] = set()
        try:
            missing_fields = self.get_missing_fields(record=record)
            not_missing_fields = []
            for missing_field in missing_fields:
                if missing_field in record.data["colrev_masterdata_provenance"]:
                    if (
                        "not-missing"
                        in record.data["colrev_masterdata_provenance"][missing_field][
                            "note"
                        ]
                    ):
                        not_missing_fields.append(missing_field)
                        continue
                record.add_masterdata_provenance_note(key=missing_field, note="missing")

            for not_missing_field in not_missing_fields:
                missing_fields.remove(not_missing_field)
        except colrev_exceptions.MissingRecordQualityRuleSpecification:
            pass
        return missing_fields

    def __check_completeness(self, *, record: colrev.record.Record) -> None:
        required_fields_keys = self.record_field_requirements["other"]
        if record.data["ENTRYTYPE"] in self.record_field_requirements:
            required_fields_keys = self.record_field_requirements[
                record.data["ENTRYTYPE"]
            ]
        for required_fields_key in required_fields_keys:
            not_missing_note = False
            if required_fields_key in record.data["colrev_masterdata_provenance"]:
                if (
                    "not-missing"
                    in record.data["colrev_masterdata_provenance"][required_fields_key][
                        "note"
                    ]
                ):
                    not_missing_note = True

            if (
                record.data.get(required_fields_key, "UNKNOWN") == "UNKNOWN"
                and not not_missing_note
            ):
                record.update_field(
                    key=required_fields_key,
                    value="UNKNOWN",
                    source="generic_field_requirements",
                    note="missing",
                    append_edit=False,
                )

        for required_field in ["author", "title", "year"]:
            if required_field in record.data:
                continue
            # self.set_status(
            #     target_state=colrev.record.RecordState.md_needs_manual_preparation
            # )
            colrev.record.Record(data=record.data).add_masterdata_provenance(
                key=required_field,
                source="colrev_curation.masterdata_restrictions",
                note="missing",
            )

    def __check_completeness_curated_masterdata(
        self, *, record: colrev.record.Record, masterdata_restrictions: dict
    ) -> None:
        for exact_match in ["ENTRYTYPE", "journal", "booktitle"]:
            if exact_match in masterdata_restrictions:
                if masterdata_restrictions[exact_match] != record.data.get(
                    exact_match, ""
                ):
                    record.data[exact_match] = masterdata_restrictions[exact_match]

        if "volume" in masterdata_restrictions:
            if masterdata_restrictions["volume"] and "volume" not in record.data:
                # self.set_status(
                #     target_state=colrev.record.RecordState.md_needs_manual_preparation
                # )
                colrev.record.Record(data=record.data).add_masterdata_provenance(
                    key="volume",
                    source="colrev_curation.masterdata_restrictions",
                    note="missing",
                )

        if "number" in masterdata_restrictions:
            if masterdata_restrictions["number"] and "number" not in record.data:
                # self.set_status(
                #     target_state=colrev.record.RecordState.md_needs_manual_preparation
                # )
                colrev.record.Record(data=record.data).add_masterdata_provenance(
                    key="number",
                    source="colrev_curation.masterdata_restrictions",
                    note="missing",
                )
            elif not masterdata_restrictions["number"] and "number" in record.data:
                record.remove_field(
                    key="number",
                    not_missing_note=True,
                    source="colrev_curation.masterdata_restrictions",
                )

    def __get_masterdata_restrictions(self) -> dict:
        masterdata_restrictions = {}
        curated_endpoints = [
            x
            for x in self.quality_model.review_manager.settings.data.data_package_endpoints
            if x["endpoint"] == "colrev.colrev_curation"
        ]
        if curated_endpoints:
            curated_endpoint = curated_endpoints[0]
            masterdata_restrictions = curated_endpoint.get(
                "masterdata_restrictions", {}
            )
        return masterdata_restrictions

    def get_applicable_restrictions(self, *, record: colrev.record.Record) -> dict:
        """Get the applicable masterdata restrictions"""

        if not str(record.data.get("year", "NA")).isdigit():
            return {}

        start_year_values = list(self.masterdata_restrictions.keys())

        year_index_diffs = [
            int(record.data["year"]) - int(x) for x in start_year_values
        ]
        year_index_diffs = [x if x >= 0 else 2000 for x in year_index_diffs]

        if not year_index_diffs:
            return {}

        index_min = min(range(len(year_index_diffs)), key=year_index_diffs.__getitem__)
        applicable_restrictions = self.masterdata_restrictions[
            start_year_values[index_min]
        ]

        return applicable_restrictions


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(MissingFieldChecker(quality_model))
