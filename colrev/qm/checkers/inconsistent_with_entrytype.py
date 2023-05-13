#! /usr/bin/env python
"""Checker for fields that are inconsistent with the ENTRYTYPE."""
from __future__ import annotations

import colrev.qm.quality_model
import colrev.record

# pylint: disable=too-few-public-methods


class InconsistentWithEntrytypeChecker:
    """The InconsistentWithEntrytypeChecker"""

    record_field_inconsistencies: dict[str, list[str]] = {
        "article": ["booktitle"],
        "inproceedings": ["issue", "number", "journal"],
        "incollection": [],
        "inbook": ["journal"],
        "book": ["volume", "issue", "number", "journal"],
        "phdthesis": ["volume", "issue", "number", "journal", "booktitle"],
        "masterthesis": ["volume", "issue", "number", "journal", "booktitle"],
        "techreport": ["volume", "issue", "number", "journal", "booktitle"],
        "unpublished": ["volume", "issue", "number", "journal", "booktitle"],
    }
    """Fields considered inconsistent with the respective ENTRYTYPE"""

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the completeness checks"""

        if record.data["ENTRYTYPE"] not in self.record_field_inconsistencies:
            return

        inconsistent_fields = self.record_field_inconsistencies[
            record.data["ENTRYTYPE"]
        ]
        for inconsistent_field in inconsistent_fields:
            if inconsistent_field in record.data:
                record.add_masterdata_provenance_note(
                    key=inconsistent_field, note="inconsistent-with-entrytype"
                )

    # def __check_inconsistencies(self) -> set:
    #     inconsistencies = self.get_inconsistencies()
    #     if inconsistencies:
    #         for inconsistency in inconsistencies:
    #             self.add_masterdata_provenance_note(
    #                 key=inconsistency,
    #                 note="inconsistent with ENTRYTYPE",
    #             )
    #     else:
    #         self.set_masterdata_consistent()
    #     return inconsistencies

    # def get_inconsistencies(self) -> set:
    #     """Get inconsistencies (between fields)"""
    #     inconsistent_field_keys = set()
    #     if self.data["ENTRYTYPE"] in self.record_field_inconsistencies:
    #         incons_fields = self.record_field_inconsistencies[self.data["ENTRYTYPE"]]
    #         inconsistent_field_keys = {x for x in incons_fields if x in self.data}
    #     # Note: a thesis should be single-authored
    #     if "thesis" in self.data["ENTRYTYPE"] and " and " in self.data.get(
    #         "author", ""
    #     ):
    #         inconsistent_field_keys.add("author")
    #     return inconsistent_field_keys


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(InconsistentWithEntrytypeChecker(quality_model))
