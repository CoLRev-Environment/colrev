#! /usr/bin/env python
"""Checker for page-range."""
from __future__ import annotations

import re

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class PageRangeChecker:
    """The PageRangeChecker"""

    msg = "page-range"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the page-range checks"""

        if "pages" not in record.data:
            return
        if not re.match(r"^\d+\-\-\d+$", record.data["pages"]):
            return

        if self.__pages_descending(pages=record.data["pages"]):
            record.add_masterdata_provenance_note(key="pages", note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key="pages", note=self.msg)

    def __pages_descending(self, *, pages: str) -> bool:
        from_page, to_page = re.findall(r"(\d+)", pages)
        if int(from_page) > int(to_page):
            return True

        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(PageRangeChecker(quality_model))
