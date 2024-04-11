#! /usr/bin/env python
"""Checker for pubmedid-not-matching-pattern."""
from __future__ import annotations

import re

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class PubmedIDPatternChecker:
    """The PubmedIDPatternChecker"""

    msg = DefectCodes.PUBMED_ID_NOT_MATCHING_PATTERN

    _PMID_REGEX = r"^\d{1,8}(\.\d)?$"

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the pubmedid-not-matching-pattern checks"""

        if Fields.PUBMED_ID not in record.data or record.ignored_defect(
            key=Fields.PUBMED_ID, defect=self.msg
        ):
            return

        if not re.match(self._PMID_REGEX, record.data[Fields.PUBMED_ID]):
            record.add_field_provenance_note(key=Fields.PUBMED_ID, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.PUBMED_ID, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(PubmedIDPatternChecker(quality_model))
