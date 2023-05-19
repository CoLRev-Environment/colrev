#! /usr/bin/env python
"""Checker for name-abbreviated."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class NameAbbreviatedChecker:
    """The NameAbbreviatedChecker"""

    fields_to_check = ["author", "editor"]
    abbreviations = ["and others", "et al", "..."]

    msg = "name-abbreviated"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the name-abbreviated checks"""

        for key in self.fields_to_check:
            if key not in record.data:
                continue

            if any(
                record.data[key].rstrip(" .").endswith(abbrev)
                for abbrev in self.abbreviations
            ):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameAbbreviatedChecker(quality_model))
