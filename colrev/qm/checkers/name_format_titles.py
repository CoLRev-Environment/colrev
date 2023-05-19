#! /usr/bin/env python
"""Checker for name-format-titles."""
from __future__ import annotations

import re

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class NameFormatTitleChecker:
    """The NameFormatTitleChecker"""

    fields_to_check = ["author", "editor"]
    titles = ["MD", "Dr", "PhD", "Prof", "Dipl Ing"]
    __words_rgx = re.compile(r"(\w[\w']*\w|\w)")

    msg = "name-format-titles"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the name-format-titles checks"""

        for key in self.fields_to_check:
            if key not in record.data:
                continue

            if self.__title_in_name(name=record.data[key]):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)

    def __title_in_name(self, *, name: str) -> bool:
        name_parts = self.__words_rgx.findall(name.lower())
        return any(title.lower() in name_parts for title in self.titles)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameFormatTitleChecker(quality_model))
