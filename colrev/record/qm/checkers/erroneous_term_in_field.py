#! /usr/bin/env python
"""Checker for erroneous-term-in-field."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class ErroneousTermInFieldChecker:
    """The ErroneousTermInFieldChecker"""

    erroneous_terms = {
        Fields.AUTHOR: [
            "http",
            "University",
            "orcid",
            "student",
            "Harvard",
            "Conference",
            "Mrs",
            "Hochschule",
        ],
        Fields.TITLE: [
            "research paper",
            "completed research",
            "research in progress",
            "full research paper",
        ],
    }
    msg = DefectCodes.ERRONEOUS_TERM_IN_FIELD

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the erroneous-term-in-field checks"""

        for key, erroneous_term_list in self.erroneous_terms.items():
            if key not in record.data or record.ignored_defect(
                key=key, defect=self.msg
            ):
                continue

            if record.masterdata_is_curated():
                continue

            if any(x.lower() in record.data[key].lower() for x in erroneous_term_list):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ErroneousTermInFieldChecker(quality_model))
