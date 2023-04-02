#! /usr/bin/env python
"""SearchSource: GoogleScholar"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class GoogleScholarSearchSource(JsonSchemaMixin):
    """SearchSource for GoogleScholar"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "url"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = False
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "GoogleScholar"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/google_scholar.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

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
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "query_file" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                f"Source missing query_file search_parameter ({source.filename})"
            )

        if not Path(source.search_parameters["query_file"]).is_file():
            raise colrev_exceptions.InvalidQueryException(
                f"File does not exist: query_file {source.search_parameters['query_file']} "
                f"for ({source.filename})"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of GoogleScholar"""

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for GoogleScholar"""

        return records

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
                source = record.data["colrev_data_provenance"]["note"]["source"]
                record.rename_field(key="note", new_key="cited_by")
                record.update_field(
                    key="cited_by",
                    value=record.data["cited_by"][
                        : record.data["cited_by"].find(" cites: ")
                    ],
                    source="replace_link",
                )
                record.update_field(
                    key="cited_by_link",
                    value=note[note.find("cites: ") + 7 :],
                    append_edit=False,
                    source=source + "|extract-from-note",
                )
        if "abstract" in record.data:
            # Note: abstracts provided by GoogleScholar are very incomplete
            record.remove_field(key="abstract")

        return record


if __name__ == "__main__":
    pass
