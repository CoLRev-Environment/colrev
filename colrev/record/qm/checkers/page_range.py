#! /usr/bin/env python
"""Checker for page-range."""
from __future__ import annotations

import re

import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class PageRangeChecker:
    """The PageRangeChecker"""

    msg = DefectCodes.PAGE_RANGE

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the page-range checks"""

        if (
            Fields.PAGES not in record.data
            or record.ignored_defect(key=Fields.PAGES, defect=self.msg)
            or not re.match(r"^\d+\-\-\d+$", record.data[Fields.PAGES])
        ):
            return
        if record.masterdata_is_curated():
            return

        if self._pages_descending(pages=record.data[Fields.PAGES]):
            record.add_field_provenance_note(key=Fields.PAGES, note=self.msg)
        else:
            record.remove_field_provenance_note(key=Fields.PAGES, note=self.msg)

    def _pages_descending(self, *, pages: str) -> bool:
        from_page, to_page = re.findall(r"(\d+)", pages)
        if int(from_page) > int(to_page):
            return True

        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(PageRangeChecker(quality_model))
