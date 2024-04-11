#! /usr/bin/env python
"""Checker for isbn-not-matching-pattern."""
from __future__ import annotations

import re
import typing

from colrev.constants import DefectCodes
from colrev.constants import Fields

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.record.qm.quality_model

# pylint: disable=too-few-public-methods


class ISBNPatternChecker:
    """The ISBNPatternChecker"""

    msg = DefectCodes.ISBN_NOT_MATCHING_PATTERN

    _ISBN_REGEX = re.compile(
        "^(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}$|[-0-9X ]{13}$|[0-9X]{10}$)|"
        "(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]$"
    )

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the isbn-not-matching-pattern checks"""

        if Fields.ISBN not in record.data or record.ignored_defect(
            key=Fields.ISBN, defect=self.msg
        ):
            return

        if not re.match(self._ISBN_REGEX, record.data[Fields.ISBN]):
            record.add_field_provenance_note(key=Fields.ISBN, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.ISBN, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ISBNPatternChecker(quality_model))
