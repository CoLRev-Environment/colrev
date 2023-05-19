#! /usr/bin/env python
"""Checker for name-format-separators fields."""
from __future__ import annotations

import re

import colrev.env.utils
import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class NameFormatSeparatorsChecker:
    """The NameFormatSeparatorsChecker"""

    msg = "name-format-separators"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the name-format-separators checks"""
        for key in ["author", "editor"]:
            if key not in record.data:
                continue
            if record.data[key] == "UNKNOWN":
                continue

            if self.__name_separator_error(record=record, key=key):
                record.add_masterdata_provenance_note(key=key, note=self.msg)
            else:
                record.remove_masterdata_provenance_note(key=key, note=self.msg)

    def __name_separator_error(self, *, record: colrev.record.Record, key: str) -> bool:
        if "," not in record.data[key]:
            return False
        sanitized_names_list = re.sub(
            "[^a-zA-Z, ;1]+",
            "",
            colrev.env.utils.remove_accents(input_str=record.data[key]),
        ).split(" and ")

        if not all(
            re.findall(
                r"^[\w .'’-]*, [\w .'’-]*$",
                sanitized_name,
                re.UNICODE,
            )
            for sanitized_name in sanitized_names_list
        ):
            return True

        # At least two capital letters per name
        if not all(
            re.findall(
                r"[A-Z]+",
                name_part,
                re.UNICODE,
            )
            for sanitized_name in sanitized_names_list
            for name_part in sanitized_name.split(",")
        ):
            return True

        # Note : patterns like "I N T R O D U C T I O N"
        # that may result from grobid imports
        if re.search(r"[A-Z] [A-Z] [A-Z] [A-Z]", record.data[key]):
            return True
        if len(record.data[key]) < 5:
            return True

        return False


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameFormatSeparatorsChecker(quality_model))
