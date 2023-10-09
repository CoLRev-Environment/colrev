#! /usr/bin/env python
"""Checker for html-tags."""
from __future__ import annotations

import re

import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class HTMLTagChecker:
    """The HTMLTagChecker"""

    msg = "html-tags"
    __fields_to_check = [
        "title",
        "journal",
        "booktitle",
        "author",
        "publisher",
        "editor",
    ]

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the html-tags checks"""

        for key in self.__fields_to_check:
            if key in record.data:
                if re.search(r"&#\d+;", record.data[key]):
                    record.add_masterdata_provenance_note(key=key, note=self.msg)
                else:
                    record.remove_masterdata_provenance_note(key=key, note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(HTMLTagChecker(quality_model))
