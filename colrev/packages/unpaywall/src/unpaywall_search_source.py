#! /usr/bin/env python
"""SearchSource: Unpaywall"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.ops.screen
import colrev.ops.search_api_feed
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.settings
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from utils import get_email

# selbst importiert, löschen vor merge und absprache


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class UnpaywallSearchSource(JsonSchemaMixin):
    """Unpaywall Search Source"""

    # achtung hier habe ich von DefaultSettings zu DefaultSourceSettings geändert,da ich Fehler wie "DefaultSettings has no atrribute get_api_feed"
    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
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

    # hilfsmethode um suche zu starten -> getapi bekommt man SearchAPIFeed object deswegen kann ich auch mit .save etc. arbeiten
    def _start_api_search(
        self, *, unpaywall_feed: colrev.ops.search_api_feed.SearchAPIFeed, rerun: bool
    ) -> None:
        for record in self.get_query_record():
            unpaywall_feed.add_update_record(record)

        unpaywall_feed.save()

    def _build_url(self) -> str:
        """Building of search_url"""
        url = "https://api.unpaywall.org/v2/"
        params = self.search_source.search_parameters
        query = params["query"]
        is_oa = params["is_oa"]
        email = get_email
        return f"{url}?search={query}&is_oa={is_oa}&email={email}"

    # hierrüber bekommt man die records von der abfrage über die itteriert wird

    def get_query_record(self) -> typing.Iterator[colrev.record.record.Record]:
        """Gets Records to save in API feed"""
        search_url = self._build_url()

        response = requests.get(search_url, timeout=60)
        if response.status_code != 200:
            return
        # TODO: weitere verarbeitung impelemtieren -> warten auf fertigstellung von _build_url

    def search(self, rerun: bool) -> None:
        """Run a search of Unpaywall"""
        unpaywall_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        # TODO: API search
        self._start_api_search(unpaywall_feed=unpaywall_feed, rerun=rerun)

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
