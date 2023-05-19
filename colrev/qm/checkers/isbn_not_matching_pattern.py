#! /usr/bin/env python
"""Checker for isbn-not-matching-pattern."""
from __future__ import annotations

import re

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class ISBNPatternChecker:
    """The ISBNPatternChecker"""

    msg = "isbn-not-matching-pattern"

    __ISBN_REGEX = re.compile(
        "^(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}$|[-0-9X ]{13}$|[0-9X]{10}$)|"
        "(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]$"
    )

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the isbn-not-matching-pattern checks"""

        if "isbn" not in record.data:
            return

        if not re.match(self.__ISBN_REGEX, record.data["isbn"]):
            record.add_masterdata_provenance_note(key="isbn", note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key="isbn", note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ISBNPatternChecker(quality_model))
