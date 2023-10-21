#! /usr/bin/env python
"""Checker for missing fields."""
from __future__ import annotations

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class MissingFieldChecker:
    """The MissingFieldChecker"""

    # Based on https://en.wikipedia.org/wiki/BibTeX
    record_field_requirements = {
        "article": [
            Fields.AUTHOR,
            Fields.TITLE,
            Fields.JOURNAL,
            Fields.YEAR,
            Fields.VOLUME,
            Fields.NUMBER,
        ],
        "inproceedings": [Fields.AUTHOR, Fields.TITLE, Fields.BOOKTITLE, Fields.YEAR],
        "incollection": [
            Fields.AUTHOR,
            Fields.TITLE,
            Fields.BOOKTITLE,
            Fields.PUBLISHER,
            Fields.YEAR,
        ],
        "inbook": [
            Fields.AUTHOR,
            Fields.TITLE,
            Fields.CHAPTER,
            Fields.PUBLISHER,
            Fields.YEAR,
        ],
        "proceedings": [Fields.BOOKTITLE, Fields.EDITOR, Fields.YEAR],
        "conference": [Fields.BOOKTITLE, Fields.EDITOR, Fields.YEAR],
        "book": [Fields.AUTHOR, Fields.TITLE, Fields.PUBLISHER, Fields.YEAR],
        "phdthesis": [Fields.AUTHOR, Fields.TITLE, Fields.SCHOOL, Fields.YEAR],
        "bachelorthesis": [Fields.AUTHOR, Fields.TITLE, Fields.SCHOOL, Fields.YEAR],
        "thesis": [Fields.AUTHOR, Fields.TITLE, Fields.SCHOOL, Fields.YEAR],
        "masterthesis": [Fields.AUTHOR, Fields.TITLE, Fields.SCHOOL, Fields.YEAR],
        "techreport": [Fields.AUTHOR, Fields.TITLE, "institution", Fields.YEAR],
        "unpublished": [Fields.TITLE, Fields.AUTHOR, Fields.YEAR],
        "misc": [Fields.AUTHOR, Fields.TITLE, Fields.YEAR],
        "software": [Fields.AUTHOR, Fields.TITLE, Fields.URL],
        "online": [Fields.AUTHOR, Fields.TITLE, Fields.URL],
        "other": [Fields.AUTHOR, Fields.TITLE, Fields.YEAR],
    }
    """Fields requirements for respective ENTRYTYPE"""

    # book, inbook: author <- editor

    msg = DefectCodes.MISSING

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
                source="MissingFieldChecker",
                masterdata_repository=False,
                replace_source=False,
            )

    def __ignore_exceptions(self, *, record: colrev.record.Record) -> None:
        # No authors for complementary materials or errata required
        if (
            any(
                x == record.data.get(Fields.TITLE, FieldValues.UNKNOWN).lower()
                for x in self.__complementary_material_strings
            )
            or any(
                x in record.data.get(Fields.TITLE, FieldValues.UNKNOWN).lower()
                for x in self.__complementary_material_keywords
            )
            or any(
                x in record.data.get(Fields.TITLE, FieldValues.UNKNOWN).lower()
                for x in ["errata", "erratum", "corrigendum"]
            )
        ):
            if Fields.AUTHOR in record.data[Fields.MD_PROV] and any(
                x == DefectCodes.MISSING
                for x in record.data[Fields.MD_PROV][Fields.AUTHOR]["note"].split(",")
            ):
                record.remove_field(
                    key=Fields.AUTHOR, not_missing_note=True, source="ignored_exception"
                )

    def __has_missing_fields(self, *, record: colrev.record.Record) -> bool:
        if any(
            DefectCodes.MISSING in x["note"].split(",")
            for x in record.data[Fields.MD_PROV].values()
        ):
            return True
        return False

    def __check_forthcoming(self, *, record: colrev.record.Record) -> None:
        if record.data.get(Fields.YEAR, "") != "forthcoming":
            record.remove_masterdata_provenance_note(
                key=Fields.VOLUME, note="forthcoming"
            )
            record.remove_masterdata_provenance_note(
                key=Fields.NUMBER, note="forthcoming"
            )
            return
        source = "NA"
        if Fields.YEAR in record.data[Fields.MD_PROV]:
            source = record.data[Fields.MD_PROV][Fields.YEAR]["source"]
        if record.data.get(Fields.VOLUME, "") in ["", FieldValues.UNKNOWN]:
            record.remove_masterdata_provenance_note(
                key=Fields.VOLUME, note=DefectCodes.MISSING
            )
            record.remove_masterdata_provenance_note(
                key=Fields.VOLUME, note=DefectCodes.NOT_MISSING
            )
            record.add_masterdata_provenance(
                key=Fields.VOLUME, source=source, note="forthcoming"
            )
        if record.data.get(Fields.NUMBER, "") in ["", FieldValues.UNKNOWN]:
            record.remove_masterdata_provenance_note(
                key=Fields.NUMBER, note=DefectCodes.MISSING
            )
            record.remove_masterdata_provenance_note(
                key=Fields.NUMBER, note=DefectCodes.NOT_MISSING
            )
            record.add_masterdata_provenance(
                key=Fields.NUMBER, source=source, note="forthcoming"
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
            if required_fields_key in record.data[Fields.MD_PROV]:
                if (
                    DefectCodes.NOT_MISSING
                    in record.data[Fields.MD_PROV][required_fields_key]["note"]
                ):
                    not_missing_note = True

            if (
                record.data.get(required_fields_key, FieldValues.UNKNOWN)
                == FieldValues.UNKNOWN
                and not not_missing_note
            ):
                record.update_field(
                    key=required_fields_key,
                    value=FieldValues.UNKNOWN,
                    source=source,
                    note=self.msg,
                    append_edit=False,
                )

        for required_field in [Fields.AUTHOR, Fields.TITLE, Fields.YEAR]:
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

        if Fields.VOLUME in applicable_curation_restrictions:
            if (
                applicable_curation_restrictions[Fields.VOLUME]
                and Fields.VOLUME not in record.data
            ):
                colrev.record.Record(data=record.data).add_masterdata_provenance(
                    key=Fields.VOLUME,
                    source="colrev_curation.curation_restrictions",
                    note=self.msg,
                )
            else:
                colrev.record.Record(
                    data=record.data
                ).remove_masterdata_provenance_note(
                    key=Fields.VOLUME,
                    note=self.msg,
                )

        if Fields.NUMBER in applicable_curation_restrictions:
            if (
                applicable_curation_restrictions[Fields.NUMBER]
                and Fields.NUMBER not in record.data
            ):
                colrev.record.Record(data=record.data).add_masterdata_provenance(
                    key=Fields.NUMBER,
                    source="colrev_curation.curation_restrictions",
                    note=self.msg,
                )
            else:
                colrev.record.Record(
                    data=record.data
                ).remove_masterdata_provenance_note(
                    key=Fields.VOLUME,
                    note=self.msg,
                )

        self.apply_curation_restrictions(record=record)

    def __get_applicable_curation_restrictions(
        self, *, record: colrev.record.Record
    ) -> dict:
        """Get the applicable curation restrictions"""

        if not str(record.data.get(Fields.YEAR, "NA")).isdigit():
            return {}

        start_year_values = list(self.curation_restrictions.keys())
        year_index_diffs = [
            int(record.data[Fields.YEAR]) - int(x) for x in start_year_values
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

        for field in [Fields.JOURNAL, Fields.BOOKTITLE]:
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
            Fields.NUMBER in applicable_curation_restrictions
            and not applicable_curation_restrictions[Fields.NUMBER]
            and Fields.NUMBER in record.data
        ):
            record.remove_field(
                key=Fields.NUMBER,
                not_missing_note=True,
                source="colrev_curation.curation_restrictions",
            )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(MissingFieldChecker(quality_model))
