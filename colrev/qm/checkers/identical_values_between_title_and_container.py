#! /usr/bin/env python
"""Checker for identical-values-between-title-and-container."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class IdenticalValuesChecker:
    """The IdenticalValuesChecker"""

    msg = "identical-values-between-title-and-container"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the identical-values-between-title-and-container checks"""

        if self.__identical_values_between_title_and_container(record=record):
            record.add_masterdata_provenance_note(key="title", note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key="title", note=self.msg)

    def __identical_values_between_title_and_container(
        self, *, record: colrev.record.Record
    ) -> bool:
        if (
            "booktitle" in record.data
            and "title" in record.data
            and record.data["title"].lower() == record.data["booktitle"].lower()
        ):
            return True
        if (
            "journal" in record.data
            and "title" in record.data
            and record.data["title"].lower() == record.data["journal"].lower()
        ):
            return True
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(IdenticalValuesChecker(quality_model))
