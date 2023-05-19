#! /usr/bin/env python
"""Checker for mostly-all-caps fields."""
from __future__ import annotations

import colrev.env.utils
import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class MostlyAllCapsFieldChecker:
    """The MostlyAllCapsFieldChecker"""

    msg = "mostly-all-caps"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the mostly-all-caps checks"""
        for key in ["author", "title", "journal", "booktitle", "editor"]:
            if key not in record.data:
                continue
            if record.data[key] == "UNKNOWN":
                continue
            if (
                colrev.env.utils.percent_upper_chars(
                    record.data[key].replace(" and ", "")
                )
                < 0.7
            ):
                record.remove_masterdata_provenance_note(key=key, note=self.msg)
                continue

            # container-title-abbreviated
            if key in ["journal", "booktitle"] and len(record.data[key]) < 6:
                continue

            record.add_masterdata_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(MostlyAllCapsFieldChecker(quality_model))
