#! /usr/bin/env python
"""Checker for container-title-abbreviated."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class ContainerTitleAbbreviatedChecker:
    """The ContainerTitleAbbreviatedChecker"""

    fields_to_check = [Fields.JOURNAL, Fields.BOOKTITLE]
    msg = DefectCodes.CONTAINER_TITLE_ABBREVIATED

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the container-title-abbreviated checks"""

        for key in self.fields_to_check:
            if key not in record.data or record.ignored_defect(
                key=key, defect=self.msg
            ):
                continue
            if record.masterdata_is_curated():  # pragma: no cover
                continue

            if self.__container_title_abbreviated(record=record, key=key):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)

    def __container_title_abbreviated(
        self, *, record: colrev.record.record.Record, key: str
    ) -> bool:
        if len(record.data[key]) < 6 and record.data[key].isupper():
            return True
        if key == Fields.BOOKTITLE and "Proc." in record.data[Fields.BOOKTITLE]:
            return True
        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ContainerTitleAbbreviatedChecker(quality_model))
