#! /usr/bin/env python
"""Checker for name-format-titles."""
from __future__ import annotations

import re

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class NameFormatTitleChecker:
    """The NameFormatTitleChecker"""

    fields_to_check = [Fields.AUTHOR, Fields.EDITOR]
    titles = ["Dr", "PhD", "Prof", "Dipl Ing"]
    _words_rgx = re.compile(r"(\w[\w']*\w|\w)")

    msg = DefectCodes.NAME_FORMAT_TITLES

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the name-format-titles checks"""

        for key in self.fields_to_check:
            if key not in record.data or record.ignored_defect(
                key=key, defect=self.msg
            ):
                continue
            if record.masterdata_is_curated():
                continue

            if self._title_in_name(name=record.data[key]):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)

    def _title_in_name(self, *, name: str) -> bool:
        name_parts = self._words_rgx.findall(name.lower().replace(".", ""))
        return any(title.lower() in name_parts for title in self.titles)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameFormatTitleChecker(quality_model))
