#! /usr/bin/env python
"""Checker for inconsistent-with-doi-metadata."""
from __future__ import annotations

from rapidfuzz import fuzz

import colrev.exceptions as colrev_exceptions
import colrev.packages.crossref.src.crossref_search_source as crossref_connector
import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class InconsistentWithDOIMetadataChecker:
    """The InconsistentWithDOIMetadataChecker"""

    msg = DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    _fields_to_check = [
        Fields.AUTHOR,
        Fields.TITLE,
        Fields.JOURNAL,
        Fields.YEAR,
        Fields.VOLUME,
        Fields.NUMBER,
    ]

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model
        self._etiquette = crossref_connector.CrossrefSearchSource.get_etiquette()

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the inconsistent-with-doi-metadata checks"""

        if Fields.DOI not in record.data or record.ignored_defect(
            key=Fields.DOI, defect=self.msg
        ):
            return

        if "md_curated.bib" in record.get_field_provenance_source(Fields.DOI):
            return

        if self._doi_metadata_conflicts(record=record):
            record.add_field_provenance_note(key=Fields.DOI, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.DOI, note=self.msg)

    def _doi_metadata_conflicts(self, *, record: colrev.record.record.Record) -> bool:
        record_copy = record.copy_prep_rec()

        try:
            crossref_md = crossref_connector.CrossrefSearchSource.query_doi(
                doi=record_copy.data[Fields.DOI], etiquette=self._etiquette
            )

            for key in crossref_md.data.keys():
                if key not in self._fields_to_check:
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


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentWithDOIMetadataChecker(quality_model))
