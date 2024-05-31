#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.settings
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# selbst importiert, löschen vor merge und absprache


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class UnpaywallSearchSource(JsonSchemaMixin):
    """Unpaywall Search Source"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    # TODO ABSPRECHEN ENTKOMMENTIERT!
    source_identifier = "ID"
    search_types = [SearchType.API]
    endpoint = "colrev.unpaywall"

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.oni
    # docs_link

    short_name = "Unpaywall"
    # API_FIELDS
    # FIELD_MAPPING

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        if settings:
            # Unpaywall as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/unpaywall.bib"),
                search_type=SearchType.API,
                search_parameters={},
                comment="",
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Unpaywall"""
        # Not yet implemented
        result = {"confidence": 0.0}
        return result

    @classmethod
    def add_endpoint(
        cls, operation: colrev.ops.search.Search, params: dict
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        """Not implemented"""

    def search(self, rerun: bool) -> None:
        """Run a search of Unpaywall"""
        """Not implemented"""
        unpaywall_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        # TODO: API search

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                logger=self.review_manager.logger,
            )
            return records

        raise NotImplementedError

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Unpaywall"""
        """Not implemented"""
        return record


if __name__ == "__main__":
    instance = UnpaywallSearchSource()
    instance.search()
