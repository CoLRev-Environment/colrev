#! /usr/bin/env python
"""SearchSource: Transport Research International Documentation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.load_utils_ris
import colrev.ops.search
import colrev.record
from colrev.constants import Fields


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class TransportResearchInternationalDocumentation(JsonSchemaMixin):
    """Transport Research International Documentation"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.trid"
    source_identifier = "biburl"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "TRID"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/trid.md"
    )
    db_url = "https://trid.trb.org/"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Transport Research International Documentation"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "UR  - https://trid.trb.org/view/" in data:
            result["confidence"] = 0.9
            return result
        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        return operation.add_db_source(
            search_source_cls=cls,
            params=params,
        )

    def run_search(self, rerun: bool) -> None:
        """Run a search of TRID"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def __ris_fixes(self, *, entries: dict) -> None:
        for entry in entries:
            # pylint: disable=colrev-missed-constant-usage
            if "title" in entry and "primary_title" not in entry:
                entry["primary_title"] = entry.pop("title")
            if entry["type_of_reference"] in ["JOUR"]:
                if "journal_name" in entry:
                    entry["secondary_title"] = entry.pop("journal_name")
            if "publication_year" in entry:
                entry[Fields.YEAR] = entry.pop("publication_year")

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".ris":
            ris_loader = colrev.ops.load_utils_ris.RISLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="accession_number",
            )
            ris_entries = ris_loader.load_ris_entries()
            self.__ris_fixes(entries=ris_entries)
            records = ris_loader.convert_to_records(entries=ris_entries)
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Transport Research International Documentation"""

        return record
