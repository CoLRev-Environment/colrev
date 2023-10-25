#! /usr/bin/env python
"""Checker for erroneous-title-field."""
from __future__ import annotations

import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class ErroneousTitleFieldChecker:
    """The ErroneousTitleFieldChecker"""

    msg = DefectCodes.ERRONEOUS_TITLE_FIELD

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the erroneous-title-field checks"""

        if Fields.TITLE not in record.data:
            return

        if self.__title_has_errors(title=record.data[Fields.TITLE]):
            record.add_masterdata_provenance_note(key=Fields.TITLE, note=self.msg)

        else:
            record.remove_masterdata_provenance_note(key=Fields.TITLE, note=self.msg)

    def __title_has_errors(self, *, title: str) -> bool:
        # Cover common errors
        if title in {
            "A I S ssociation for nformation ystems",
            "The International Journal of Information Systems Applications Chairman of the Editorial Board",
        }:
            return True

        if " " not in title and (
            any(x in title for x in ["_", "."]) or any(char.isdigit() for char in title)
        ):
            return True
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ErroneousTitleFieldChecker(quality_model))
