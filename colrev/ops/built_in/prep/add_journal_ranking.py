#! /usr/bin/env python
"""adds journal rankings to metadata"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class AddJournalRanking(JsonSchemaMixin):
    # wenn man an bestimmten Settings interessiert ist evtl. für Abfrage
    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    ci_supported: bool = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)        

    def search_in_database(self, journal, database) -> str:
        pointer = database.cursor()
        pointer.execute("SELECT * FROM main.Ranking WHERE Name = ?", (journal))
        content = pointer.fetchall()
        if content is None:
            return "Not in a ranking"
        else:
            return "is ranked"

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
        ) -> colrev.record.Record:
        """Add Journalranking to Metadata"""

        journal = record.data.get("journal")
        database = sqlite3.connect("~/Home/Project/colrev/ranking.db")
        ranking = self.search_in_database(journal, database)
        database.close()
        record.add_data_provenance_note(key="journal_ranking", note=ranking)

        return record



if __name__ == "__main__":
    pass
