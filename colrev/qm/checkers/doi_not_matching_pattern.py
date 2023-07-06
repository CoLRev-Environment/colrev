#! /usr/bin/env python
"""Checker for doi-not-matching-pattern."""
from __future__ import annotations

import re

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class DOIPatternChecker:
    """The DOIPatternChecker"""

    msg = "doi-not-matching-pattern"
    # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
    __DOI_REGEX = r"^10.\d{4,9}\/"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the doi-not-matching-pattern checks"""

        if "doi" not in record.data:
            return

        if not re.match(self.__DOI_REGEX, record.data["doi"]):
            record.add_masterdata_provenance_note(key="doi", note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key="doi", note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(DOIPatternChecker(quality_model))
