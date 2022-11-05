#! /usr/bin/env python
"""SearchSource: Pubmed"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class PubMedSearchSource(JsonSchemaMixin):
    """SearchSource for Pubmed"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "https://pubmed.ncbi.nlm.nih.gov/{{pmid}}"
    search_type = colrev.settings.SearchType.DB

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Pubmed"""

        result = {"confidence": 0.0}

        # Simple heuristic:
        if "PMID,Title,Authors,Citation,First Author,Journal/Book," in data:
            result["confidence"] = 1.0
            return result
        if "PMID- " in data:
            result["confidence"] = 0.7
            return result

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of Pubmed"""

        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for Pubmed"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Pubmed"""

        if "first_author" in record.data:
            record.remove_field(key="first_author")
        if "journal/book" in record.data:
            record.rename_field(key="journal/book", new_key="journal")
        if "UNKNOWN" == record.data.get("author") and "authors" in record.data:
            record.remove_field(key="author")
            record.rename_field(key="authors", new_key="author")

        if "UNKNOWN" == record.data.get("year"):
            record.remove_field(key="year")
            if "publication_year" in record.data:
                record.rename_field(key="publication_year", new_key="year")

        if "author" in record.data:
            record.data["author"] = colrev.record.PrepRecord.format_author_field(
                input_string=record.data["author"]
            )

        # TBD: how to distinguish other types?
        record.change_entrytype(new_entrytype="article")
        record.import_provenance(source_identifier=self.source_identifier)

        return record


if __name__ == "__main__":
    pass
