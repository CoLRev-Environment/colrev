#! /usr/bin/env python
"""Checker for html-tags."""
from __future__ import annotations

import re

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class HTMLTagChecker:
    """The HTMLTagChecker"""

    msg = DefectCodes.HTML_TAGS
    _fields_to_check = [
        Fields.TITLE,
        Fields.JOURNAL,
        Fields.BOOKTITLE,
        Fields.AUTHOR,
        Fields.PUBLISHER,
        Fields.EDITOR,
    ]

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the html-tags checks"""

        for key in self._fields_to_check:
            if key not in record.data or record.ignored_defect(
                key=key, defect=self.msg
            ):
                continue
            if record.masterdata_is_curated():
                continue
            if re.search(r"&#\d+;", record.data[key]):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(HTMLTagChecker(quality_model))
