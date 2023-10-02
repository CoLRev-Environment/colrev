#! /usr/bin/env python
"""Checker for pubmedid-not-matching-pattern."""
from __future__ import annotations

import re

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class PubmedIDPatternChecker:
    """The PubmedIDPatternChecker"""

    msg = "pubmedid-not-matching-pattern"

    __PMID_REGEX = r"^\d{1,8}(\.\d)?$"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the pubmedid-not-matching-pattern checks"""

        if "colrev.pubmed.pubmedid" not in record.data:
            return

        if not re.match(self.__PMID_REGEX, record.data["colrev.pubmed.pubmedid"]):
            record.add_masterdata_provenance_note(
                key="colrev.pubmed.pubmedid", note=self.msg
            )
        else:
            record.remove_masterdata_provenance_note(
                key="colrev.pubmed.pubmedid", note=self.msg
            )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(PubmedIDPatternChecker(quality_model))
