#! /usr/bin/env python
"""Checker for thesis-with-multiple-authors."""
from __future__ import annotations

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class ThesisWithMultipleAuthorsChecker:
    """The ThesisWithMultipleAuthorsChecker"""

    msg = "thesis-with-multiple-authors"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the thesis-with-multiple-authors checks"""

        if self.__multiple_authored_thesis(record=record):
            record.add_masterdata_provenance_note(key="author", note=self.msg)
        else:
            record.remove_masterdata_provenance_note(key="author", note=self.msg)

    def __multiple_authored_thesis(self, *, record: colrev.record.Record) -> bool:
        if "thesis" in record.data["ENTRYTYPE"] and " and " in record.data.get(
            "author", ""
        ):
            return True
        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(ThesisWithMultipleAuthorsChecker(quality_model))
