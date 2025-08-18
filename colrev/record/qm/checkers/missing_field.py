#! /usr/bin/env python
"""Checker for missing fields."""
from __future__ import annotations

import colrev.env.utils
import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPE_FIELD_REQUIREMENTS
from colrev.constants import Fields
from colrev.constants import FieldValues

# pylint: disable=too-few-public-methods


class MissingFieldChecker:
    """The MissingFieldChecker"""

    # book, inbook: author <- editor

    msg = DefectCodes.MISSING

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the missing-field checks"""

        if record.data[Fields.ENTRYTYPE] not in ENTRYTYPE_FIELD_REQUIREMENTS:
            return

        if record.masterdata_is_curated():  # pragma: no cover
            return

        required_fields_keys = ENTRYTYPE_FIELD_REQUIREMENTS[
            record.data[Fields.ENTRYTYPE]
        ]
        for required_fields_key in required_fields_keys:
            if record.ignored_defect(key=required_fields_key, defect=self.msg):
                continue

            if self._is_missing(record=record, key=required_fields_key):
                record.update_field(
                    key=required_fields_key,
                    value=FieldValues.UNKNOWN,
                    source="generic_field_requirements",
                )
                record.add_field_provenance_note(key=required_fields_key, note=self.msg)
            else:
                record.remove_field_provenance_note(
                    key=required_fields_key, note=self.msg
                )

    def _is_missing(self, *, key: str, record: colrev.record.record.Record) -> bool:
        if not self._required_in_forthcoming(key=key, record=record):
            return False
        if key in record.data and record.data[key] != FieldValues.UNKNOWN:
            return False
        return True

    def _required_in_forthcoming(
        self, *, key: str, record: colrev.record.record.Record
    ) -> bool:
        if record.data.get(Fields.YEAR, "") != FieldValues.FORTHCOMING:
            return True

        # Forthcoming for the following conditions:
        if key == Fields.YEAR:
            return True

        if key == Fields.VOLUME:
            record.add_field_provenance_note(key=key, note=f"IGNORE:{self.msg}")
            return False
        if key == Fields.NUMBER:
            record.add_field_provenance_note(key=key, note=f"IGNORE:{self.msg}")
            return False

        return True


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(MissingFieldChecker(quality_model))
