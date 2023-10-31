#! /usr/bin/env python
"""SearchSource: ACM Digital Library"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.load_utils_bib
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ACMDigitalLibrarySearchSource(JsonSchemaMixin):
    """ACM digital Library"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.acm_digital_library"
    # Note : the ID contains the doi
    # "https://dl.acm.org/doi/{{ID}}"
    source_identifier = "doi"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "ACM Digital Library"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/"
        + "ops/built_in/search_sources/acm_digital_library.md"
    )
    db_url = "https://dl.acm.org/"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ACM dDigital Library"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params
        )

        if search_type == colrev.settings.SearchType.DB:
            return operation.add_db_source(
                search_source_cls=cls,
                params=params,
            )

        raise NotImplementedError

    def run_search(self, rerun: bool) -> None:
        """Run a search of ACM Digital Library"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            if self.search_source.filename.suffix in [".bib"]:
                self.operation.run_db_search(  # type: ignore
                    search_source_cls=self.__class__,
                    source=self.search_source,
                )
                return

            raise NotImplementedError

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    # pylint: disable=colrev-missed-constant-usage
    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for ACM Digital Library"""
        record.remove_field(key="url")
        record.remove_field(key="publisher")
        record.remove_field(key="numpages")
        record.remove_field(key="issue_date")
        record.remove_field(key="address")
        record.remove_field(key="month")

        return record
