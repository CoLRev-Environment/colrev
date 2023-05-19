#! /usr/bin/env python
"""Checker for record-not-in-toc."""
from __future__ import annotations

import colrev.env.local_index
import colrev.exceptions as colrev_exceptions
import colrev.qm.quality_model

# pylint: disable=too-few-public-methods


class RecordNotInTOCChecker:
    """The RecordNotInTOCChecker"""

    msg = "record-not-in-toc"

    def __init__(self, quality_model: colrev.qm.quality_model.QualityModel) -> None:
        self.quality_model = quality_model
        self.local_index = colrev.env.local_index.LocalIndex(verbose_mode=False)

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the record-not-in-toc checks"""

        try:
            # Search within the table-of-content in local_index
            self.local_index.retrieve_from_toc(
                record_dict=record.data,
                similarity_threshold=0.9,
                include_file=False,
            )
            if "journal" in record.data:
                record.remove_masterdata_provenance_note(key="journal", note=self.msg)
            elif "booktitle" in record.data:
                record.remove_masterdata_provenance_note(key="booktitle", note=self.msg)
        except colrev.exceptions.RecordNotInIndexException:
            pass
        except colrev_exceptions.RecordNotInTOCException:
            if "journal" in record.data:
                record.add_masterdata_provenance_note(key="journal", note=self.msg)
            elif "booktitle" in record.data:
                record.add_masterdata_provenance_note(key="booktitle", note=self.msg)


def register(quality_model: colrev.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(RecordNotInTOCChecker(quality_model))
