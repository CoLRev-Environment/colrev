#! /usr/bin/env python
"""SearchSource: GoogleScholar"""
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
from colrev.constants import Fields


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class GoogleScholarSearchSource(JsonSchemaMixin):
    """GoogleScholar"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.google_scholar"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "GoogleScholar"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/google_scholar.md"
    )
    db_url = "https://scholar.google.de/"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for GoogleScholar"""

        result = {"confidence": 0.0}
        if data.count("https://scholar.google.com/scholar?q=relat") > 0.9 * data.count(
            "\n@"
        ):
            result["confidence"] = 1.0
            return result

        if data.count("{pop0") > 0.9 * data.count("\n@"):
            result["confidence"] = 1.0
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
        """Run a search of GoogleScholar"""

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

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for GoogleScholar"""
        if "note" in record.data:
            if (
                "cites: https://scholar.google.com/scholar?cites="
                in record.data["note"]
            ):
                note = record.data["note"]
                source = record.data[Fields.D_PROV]["note"]["source"]
                record.rename_field(key="note", new_key=Fields.CITED_BY)
                record.update_field(
                    key=Fields.CITED_BY,
                    value=record.data[Fields.CITED_BY][
                        : record.data[Fields.CITED_BY].find(" cites: ")
                    ],
                    source="replace_link",
                )
                record.update_field(
                    key="cited_by_link",
                    value=note[note.find("cites: ") + 7 :],
                    append_edit=False,
                    source=source + "|extract-from-note",
                )
        if Fields.ABSTRACT in record.data:
            # Note: abstracts provided by GoogleScholar are very incomplete
            record.remove_field(key=Fields.ABSTRACT)

        return record
