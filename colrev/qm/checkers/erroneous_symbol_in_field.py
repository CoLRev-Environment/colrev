#! /usr/bin/env python
"""Checker for erroneous-symbol-in-field."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class ErroneousSymbolInFieldChecker:
    """The ErroneousSymbolInFieldChecker"""

    fields_to_check = ["author", "title", "editor", "journal", "booktitle"]
    erroneous_symbols = ["�", "™"]
    msg = "erroneous-symbol-in-field"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the erroneous-symbol-in-field checks"""

        for key in self.fields_to_check:
            if key not in record.data:
                continue

            if any(x in record.data[key] for x in self.erroneous_symbols):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ErroneousSymbolInFieldChecker(quality_model))
