#! /usr/bin/env python
"""Checker for missing fields."""
from __future__ import annotations

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class MissingFieldChecker:
    """The MissingFieldChecker"""

    # Based on https://en.wikipedia.org/wiki/BibTeX
    record_field_requirements = {
        "article": ["author", "title", "journal", "year", "volume", "number"],
        "inproceedings": ["author", "title", "booktitle", "year"],
        "incollection": ["author", "title", "booktitle", "publisher", "year"],
        "inbook": ["author", "title", "chapter", "publisher", "year"],
        "proceedings": ["booktitle", "editor", "year"],
        "conference": ["booktitle", "editor", "year"],
        "book": ["author", "title", "publisher", "year"],
        "phdthesis": ["author", "title", "school", "year"],
        "bachelorthesis": ["author", "title", "school", "year"],
        "thesis": ["author", "title", "school", "year"],
        "masterthesis": ["author", "title", "school", "year"],
        "techreport": ["author", "title", "institution", "year"],
        "unpublished": ["title", "author", "year"],
        "misc": ["author", "title", "year"],
        "software": ["author", "title", "url"],
        "online": ["author", "title", "url"],
        "other": ["author", "title", "year"],
    }
    """Fields requirements for respective ENTRYTYPE"""

    # book, inbook: author <- editor

    msg = "missing"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model
        self.curation_restrictions = self.__load_curation_restrictions()
        self.__complementary_material_strings = (
            colrev.env.utils.load_complementary_material_strings()
        )
        self.__complementary_material_keywords = (
            colrev.env.utils.load_complementary_material_keywords()
        )

    def __load_curation_restrictions(self) -> dict:
        curation_restrictions = {}
        curated_endpoints = [
            x
            for x in self.quality_model.review_manager.settings.data.data_package_endpoints
            if x["endpoint"] == "colrev.colrev_curation"
        ]
        if curated_endpoints:
            curated_endpoint = curated_endpoints[0]
            curation_restrictions = curated_endpoint.get("masterdata_restrictions", {})
        return curation_restrictions

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the missing-field checks"""

        if self.curation_restrictions:
            self.__check_completeness_curated_masterdata(record=record)
        else:
            self.__check_completeness(record=record)

        self.__ignore_exceptions(record=record)
        self.__check_forthcoming(record=record)

        if not self.__has_missing_fields(record=record):
            record.set_masterdata_complete(
                source="update_masterdata_provenance",
                masterdata_repository=False,
                replace_source=False,
            )

    def __ignore_exceptions(self, *, record: colrev.record.Record) -> None:
        # No authors for complementary materials or errata required
        if (
            any(
                x == record.data.get("title", "UNKNOWN").lower()
                for x in self.__complementary_material_strings
            )
            or any(
                x in record.data.get("title", "UNKNOWN").lower()
                for x in self.__complementary_material_keywords
            )
            or any(
                x in record.data.get("title", "UNKNOWN").lower()
                for x in ["errata", "erratum", "corrigendum"]
            )
        ):
            if "author" in record.data["colrev_masterdata_provenance"] and any(
                x == "missing"
                for x in record.data["colrev_masterdata_provenance"]["author"][
                    "note"
                ].split(",")
            ):
                record.remove_field(
                    key="author", not_missing_note=True, source="ignored_exception"
                )

    def __has_missing_fields(self, *, record: colrev.record.Record) -> bool:
        if any(
            "missing" in x["note"].split(",")
            for x in record.data["colrev_masterdata_provenance"].values()
        ):
            return True
        return False

    def __check_forthcoming(self, *, record: colrev.record.Record) -> None:
        if record.data.get("year", "") != "forthcoming":
            record.remove_masterdata_provenance_note(key="volume", note="forthcoming")
            record.remove_masterdata_provenance_note(key="number", note="forthcoming")
            return
        source = "NA"
        if "year" in record.data["colrev_masterdata_provenance"]:
            source = record.data["colrev_masterdata_provenance"]["year"]["source"]
        if record.data.get("volume", "") in ["", "UNKNOWN"]:
            record.remove_masterdata_provenance_note(key="volume", note="missing")
            record.add_masterdata_provenance(
                key="volume", source=source, note="forthcoming"
            )
        if record.data.get("number", "") in ["", "UNKNOWN"]:
            record.remove_masterdata_provenance_note(key="number", note="missing")
            record.add_masterdata_provenance(
                key="number", source=source, note="forthcoming"
            )

    def __check_completeness(
        self, *, record: colrev.record.Record, curation_restrictions: bool = False
    ) -> None:
        required_fields_keys = self.record_field_requirements["other"]
        if record.data["ENTRYTYPE"] in self.record_field_requirements:
            required_fields_keys = self.record_field_requirements[
                record.data["ENTRYTYPE"]
            ]
        else:
            raise colrev_exceptions.MissingRecordQualityRuleSpecification(
                msg=f"Missing record_field_requirements for {record.data['ENTRYTYPE']}"
            )

        if curation_restrictions:
            source = "colrev_curation.curation_restrictions"
        else:
            source = "generic_field_requirements"

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
                    source=source,
                    note=self.msg,
                    append_edit=False,
                )

        for required_field in ["author", "title", "year"]:
            if required_field in record.data:
                continue
            colrev.record.Record(data=record.data).add_masterdata_provenance(
                key=required_field,
                source=source,
                note=self.msg,
            )

    def __check_completeness_curated_masterdata(
        self, *, record: colrev.record.Record
    ) -> None:
        applicable_curation_restrictions = self.__get_applicable_curation_restrictions(
            record=record
        )

        self.__check_completeness(record=record, curation_restrictions=True)

        if "volume" in applicable_curation_restrictions:
            if (
                applicable_curation_restrictions["volume"]
                and "volume" not in record.data
            ):
                colrev.record.Record(data=record.data).add_masterdata_provenance(
                    key="volume",
                    source="colrev_curation.curation_restrictions",
                    note=self.msg,
                )
            else:
                colrev.record.Record(
                    data=record.data
                ).remove_masterdata_provenance_note(
                    key="volume",
                    note=self.msg,
                )

        if "number" in applicable_curation_restrictions:
            if (
                applicable_curation_restrictions["number"]
                and "number" not in record.data
            ):
                colrev.record.Record(data=record.data).add_masterdata_provenance(
                    key="number",
                    source="colrev_curation.curation_restrictions",
                    note=self.msg,
                )
            else:
                colrev.record.Record(
                    data=record.data
                ).remove_masterdata_provenance_note(
                    key="volume",
                    note=self.msg,
                )

        self.apply_curation_restrictions(record=record)

    def __get_applicable_curation_restrictions(
        self, *, record: colrev.record.Record
    ) -> dict:
        """Get the applicable curation restrictions"""

        if not str(record.data.get("year", "NA")).isdigit():
            return {}

        start_year_values = list(self.curation_restrictions.keys())
        year_index_diffs = [
            int(record.data["year"]) - int(x) for x in start_year_values
        ]
        year_index_diffs = [x if x >= 0 else 2000 for x in year_index_diffs]

        if not year_index_diffs:
            return {}

        index_min = min(range(len(year_index_diffs)), key=year_index_diffs.__getitem__)
        applicable_curation_restrictions = self.curation_restrictions[
            start_year_values[index_min]
        ]
        return applicable_curation_restrictions

    # Extract the restrictions to a qm-utility function?
    def apply_curation_restrictions(self, *, record: colrev.record.Record) -> None:
        """Apply the curation restrictions"""
        applicable_curation_restrictions = self.__get_applicable_curation_restrictions(
            record=record
        )
        if "ENTRYTYPE" in applicable_curation_restrictions:
            if applicable_curation_restrictions["ENTRYTYPE"] != record.data.get(
                "ENTRYTYPE", ""
            ):
                try:
                    record.change_entrytype(
                        new_entrytype=applicable_curation_restrictions["ENTRYTYPE"],
                        qm=self.quality_model,
                    )
                except colrev_exceptions.MissingRecordQualityRuleSpecification as exc:
                    print(exc)

        for field in ["journal", "booktitle"]:
            if field not in applicable_curation_restrictions:
                continue
            if applicable_curation_restrictions[field] == record.data.get(field, ""):
                continue
            record.update_field(
                key=field,
                value=applicable_curation_restrictions[field],
                source="colrev_curation.curation_restrictions",
            )
        if (
            "number" in applicable_curation_restrictions
            and not applicable_curation_restrictions["number"]
            and "number" in record.data
        ):
            record.remove_field(
                key="number",
                not_missing_note=True,
                source="colrev_curation.curation_restrictions",
            )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(MissingFieldChecker(quality_model))
