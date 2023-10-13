#! /usr/bin/env python
"""Checker for inconsistent-with-doi-metadata."""
from __future__ import annotations

from thefuzz import fuzz

import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.crossref as crossref_connector
import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class InconsistentWithDOIMetadataChecker:
    """The InconsistentWithDOIMetadataChecker"""

    msg = DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    __fields_to_check = [
        Fields.AUTHOR,
        Fields.TITLE,
        Fields.JOURNAL,
        Fields.YEAR,
        Fields.VOLUME,
        Fields.NUMBER,
    ]

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model
        self.__etiquette = crossref_connector.CrossrefSearchSource.get_etiquette(
            review_manager=quality_model.review_manager
        )

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the inconsistent-with-doi-metadata checks"""

        if Fields.DOI not in record.data:
            return
        if Fields.DOI in record.data.get(Fields.D_PROV, {}):
            if "md_curated.bib" in record.data[Fields.D_PROV][Fields.DOI]["source"]:
                return

        if self.__doi_metadata_conflicts(record=record):
            record.add_masterdata_provenance_note(key=Fields.DOI, note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key=Fields.DOI, note=self.msg)

    def __doi_metadata_conflicts(self, *, record: colrev.record.Record) -> bool:
        record_copy = record.copy_prep_rec()

        try:
            crossref_md = crossref_connector.CrossrefSearchSource.query_doi(
                doi=record_copy.data[Fields.DOI], etiquette=self.__etiquette
            )

            for key, value in crossref_md.data.items():
                if key not in self.__fields_to_check:
                    continue
                if not isinstance(value, str):
                    continue
                if key not in record.data:
                    continue
                if record.data[key] == FieldValues.UNKNOWN:
                    continue
                if key not in [Fields.AUTHOR, Fields.TITLE, Fields.JOURNAL]:
                    continue
                if len(crossref_md.data[key]) < 5 or len(record.data[key]) < 5:
                    continue
                if (
                    fuzz.partial_ratio(
                        record.data[key].lower(), crossref_md.data[key].lower()
                    )
                    < 60
                ):
                    return True

        except (
            colrev_exceptions.RecordNotFoundInPrepSourceException,
            colrev_exceptions.RecordNotParsableException,
        ):
            return False
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentWithDOIMetadataChecker(quality_model))
