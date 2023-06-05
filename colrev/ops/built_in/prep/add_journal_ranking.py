#! /usr/bin/env python
"""adds journal rankings to metadata"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record
import sqlite3

@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class AddJournalRanking(JsonSchemaMixin):

    #wenn man an bestimmten Settings interessiert ist evtl. für Abfrage
    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True
     
    def add_journal_ranking_to_metadata(self, record: colrev.record.PrepRecord, database) -> None:
            
        
        journal = record["journal"]
        database = sqlite3.connect("~/Home/Project/colrev/ranking.db")
        self.search_in_database(journal, database)

        record.add_data_provenance_note(
            key="journal_ranking", 
            note=self)

        return record

    def search_in_database(journal, database) -> str:
        pointer = database.cursor()
        pointer.execute('SELECT * FROM main.Ranking WHERE Name = ?', (journal))
        content = pointer.fetchall()
        if content is None:
            return "Not in a ranking"
        else:
            for row in content:
                return "is ranked"
        database.close() 


if __name__ == "__main__":  
    pass
