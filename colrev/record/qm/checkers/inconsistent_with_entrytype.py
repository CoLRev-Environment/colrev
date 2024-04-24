#! /usr/bin/env python
"""Checker for fields that are inconsistent with the ENTRYTYPE."""
from __future__ import annotations

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class InconsistentWithEntrytypeChecker:
    """The InconsistentWithEntrytypeChecker"""

    record_field_inconsistencies: dict[str, list[str]] = {
        "article": [Fields.BOOKTITLE, Fields.ISBN],
        "inproceedings": ["issue", Fields.NUMBER, Fields.JOURNAL],
        "incollection": [],
        "inbook": [Fields.JOURNAL],
        "book": ["issue", Fields.NUMBER, Fields.JOURNAL],
        "phdthesis": [
            Fields.VOLUME,
            "issue",
            Fields.NUMBER,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
            Fields.ISBN,
        ],
        "masterthesis": [
            Fields.VOLUME,
            "issue",
            Fields.NUMBER,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
            Fields.ISBN,
        ],
        "techreport": [
            Fields.VOLUME,
            "issue",
            Fields.NUMBER,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
            Fields.ISBN,
        ],
        "unpublished": [
            Fields.VOLUME,
            "issue",
            Fields.NUMBER,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
            Fields.ISBN,
        ],
        "online": [Fields.JOURNAL, Fields.BOOKTITLE, Fields.ISBN],
        "misc": [Fields.JOURNAL, Fields.BOOKTITLE, Fields.ISBN],
    }
    """Fields considered inconsistent with the respective ENTRYTYPE"""

    msg = DefectCodes.INCONSISTENT_WITH_ENTRYTYPE

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the completeness checks"""

        if "ENTRYTYPE" not in record.data:
            return

        if record.data["ENTRYTYPE"] not in self.record_field_inconsistencies:
            return

        inconsistent_fields = self.record_field_inconsistencies[
            record.data["ENTRYTYPE"]
        ]
        for key in list(record.data.keys()):
            if record.ignored_defect(key=key, defect=self.msg):
                continue
            if key in inconsistent_fields:
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentWithEntrytypeChecker(quality_model))
