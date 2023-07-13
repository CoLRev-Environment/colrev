#! /usr/bin/env python
"""Checker for erroneous-term-in-field."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class ErroneousTermInFieldChecker:
    """The ErroneousTermInFieldChecker"""

    erroneous_terms = {
        "author": [
            "http",
            "University",
            "orcid",
            "student",
            "Harvard",
            "Conference",
            "Mrs",
            "Hochschule",
        ],
        "title": [
            "research paper",
            "completed research",
            "research in progress",
            "full research paper",
        ],
    }
    msg = "erroneous-term-in-field"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the erroneous-term-in-field checks"""

        for key, erroneous_term_list in self.erroneous_terms.items():
            if key not in record.data:
                continue

            if any(x.lower() in record.data[key].lower() for x in erroneous_term_list):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ErroneousTermInFieldChecker(quality_model))
