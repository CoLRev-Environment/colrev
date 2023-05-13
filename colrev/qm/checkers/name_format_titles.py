#! /usr/bin/env python
"""Checker for name-format-titles."""
from __future__ import annotations

import colrev.qm.quality_model
import colrev.record

# pylint: disable=too-few-public-methods


class NameFormatTitleChecker:
    """The NameFormatTitleChecker"""

    fields_to_check = ["author", "editor"]
    titles = ["MD", "Dr", "PhD", "Prof", "Dipl Ing"]

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the name-format-titles checks"""

        for key in self.fields_to_check:
            if key not in record.data:
                continue

            if any(title in record.data[key] for title in self.titles):
                record.add_masterdata_provenance_note(
                    key=key, note="name-format-titles"
                )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameFormatTitleChecker(quality_model))
