#! /usr/bin/env python
"""Checker for record-not-in-toc."""
from __future__ import annotations

import colrev.env.local_index
import colrev.exceptions as colrev_exceptions
import colrev.record.qm.quality_model
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# pylint: disable=too-few-public-methods


class RecordNotInTOCChecker:
    """The RecordNotInTOCChecker"""

    msg = DefectCodes.RECORD_NOT_IN_TOC

    def __init__(
        self, quality_model: colrev.record.qm.quality_model.QualityModel
    ) -> None:
        self.quality_model = quality_model
        self.local_index = colrev.env.local_index.LocalIndex(verbose_mode=False)

    def run(self, *, record: colrev.record.record.Record) -> None:
        """Run the record-not-in-toc checks"""

        if record.data[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
            if record.ignored_defect(key=Fields.JOURNAL, defect=self.msg):
                return
            if not self._is_in_toc(record):
                record.add_field_provenance_note(key=Fields.JOURNAL, note=self.msg)
            else:
                record.remove_field_provenance_note(key=Fields.JOURNAL, note=self.msg)
            return

        if record.data[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
            if record.ignored_defect(key=Fields.BOOKTITLE, defect=self.msg):
                return
            if not self._is_in_toc(record):
                record.add_field_provenance_note(key=Fields.BOOKTITLE, note=self.msg)
            else:
                record.remove_field_provenance_note(key=Fields.BOOKTITLE, note=self.msg)
            return

    def _is_in_toc(self, record: colrev.record.record.Record) -> bool:

        try:
            self.quality_model.local_index_lock.acquire(timeout=60)
            # Search within the table-of-content in local_index
            self.local_index.retrieve_from_toc(record)
            return True

        except colrev_exceptions.RecordNotInIndexException:
            pass
        except colrev_exceptions.RecordNotInTOCException:
            return False
        finally:
            try:
                self.quality_model.local_index_lock.release()
            except ValueError:
                pass
        return True


def register(quality_model: colrev.record.qm.quality_model.QualityModel) -> None:
    """Register the checker"""
    quality_model.register_checker(RecordNotInTOCChecker(quality_model))
