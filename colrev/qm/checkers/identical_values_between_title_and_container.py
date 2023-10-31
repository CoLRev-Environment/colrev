#! /usr/bin/env python
"""Checker for identical-values-between-title-and-container."""
from __future__ import annotations

import colrev.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class IdenticalValuesChecker:
    """The IdenticalValuesChecker"""

    msg = DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the identical-values-between-title-and-container checks"""

        if self.__identical_values_between_title_and_container(record=record):
            record.add_masterdata_provenance_note(key=Fields.TITLE, note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key=Fields.TITLE, note=self.msg)

    def __identical_values_between_title_and_container(
        self, *, record: colrev.record.Record
    ) -> bool:
        if record.data.get(Fields.TITLE, FieldValues.UNKNOWN) == FieldValues.UNKNOWN:
            return False
        if (
            Fields.BOOKTITLE in record.data
            and Fields.TITLE in record.data
            and record.data[Fields.TITLE].lower().replace("the ", "")
            == record.data[Fields.BOOKTITLE].lower().replace("the ", "")
        ):
            return True
        if (
            Fields.JOURNAL in record.data
            and Fields.TITLE in record.data
            and record.data[Fields.TITLE].lower().replace("the ", "")
            == record.data[Fields.JOURNAL].lower().replace("the ", "")
        ):
            return True
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(IdenticalValuesChecker(quality_model))
