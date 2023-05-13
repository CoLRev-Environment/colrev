#! /usr/bin/env python
"""Checker for inconsistent-content."""
from __future__ import annotations

import colrev.qm.quality_model
import colrev.record

# pylint: disable=too-few-public-methods


class InconsistentContentChecker:
    """The InconsistentContentChecker"""

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the inconsistent-content checks"""

        if "journal" in record.data and any(
            x in record.data["journal"].lower() for x in ["conference", "workshop"]
        ):
            record.add_masterdata_provenance_note(
                key="journal", note="inconsistent-content"
            )

        if "booktitle" in record.data and any(
            x in record.data["booktitle"].lower() for x in ["journal"]
        ):
            record.add_masterdata_provenance_note(
                key="booktitle", note="inconsistent-content"
            )


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentContentChecker(quality_model))
