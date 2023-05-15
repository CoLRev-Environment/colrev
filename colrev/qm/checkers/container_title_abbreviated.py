#! /usr/bin/env python
"""Checker for container-title-abbreviated."""
from __future__ import annotations

import colrev.qm.quality_model
import colrev.record

# pylint: disable=too-few-public-methods


class ContainerTitleAbbreviatedChecker:
    """The ContainerTitleAbbreviatedChecker"""

    fields_to_check = ["journal", "booktitle"]

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the container-title-abbreviated checks"""

        for key in self.fields_to_check:
            if key not in record.data:
                continue

            if len(record.data[key]) < 6 and record.data[key].isupper():
                record.add_masterdata_provenance_note(
                    key=key, note="container-title-abbreviated"
                )
            else:
                record.remove_masterdata_provenance_note(
                    key=key, note="container-title-abbreviated"
                )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ContainerTitleAbbreviatedChecker(quality_model))
