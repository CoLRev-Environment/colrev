#! /usr/bin/env python
"""Checker for name-format-separators fields."""
from __future__ import annotations

import re

import colrev.env.utils
import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class NameFormatSeparatorsChecker:
    """The NameFormatSeparatorsChecker"""

    msg = DefectCodes.NAME_FORMAT_SEPARTORS

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the name-format-separators checks"""
        for key in [Fields.AUTHOR, Fields.EDITOR]:
            if (
                key not in record.data
                or record.ignored_defect(key=key, defect=self.msg)
                or record.data[key] == FieldValues.UNKNOWN
            ):
                continue

            if record.masterdata_is_curated():
                continue

            if self._name_separator_error(record=record, key=key):
                record.add_field_provenance_note(key=key, note=self.msg)
            else:
                record.remove_field_provenance_note(key=key, note=self.msg)

    def _name_separator_error(
        self, *, record: colrev.record.record.Record, key: str
    ) -> bool:
        if "," not in record.data[key]:
            return True

        santized_names = colrev.env.utils.remove_accents(record.data[key])
        sanitized_names = re.sub(r"[{}]|\(\w*\b\)|\"\w*\"", "", santized_names)
        sanitized_names_list = sanitized_names.split(" and ")
        if not all(
            re.findall(
                r"^[\w .‐'’-]*, [\w .‐'’-]*$",
                sanitized_name,
                re.UNICODE,
            )
            for sanitized_name in sanitized_names_list
        ):
            return True

        # At least one upper case letter per name part
        if not all(
            any(char.isupper() for char in name_part)
            for sanitized_name in sanitized_names_list
            for name_part in sanitized_name.split(",")
        ):
            return True

        return False


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(NameFormatSeparatorsChecker(quality_model))
