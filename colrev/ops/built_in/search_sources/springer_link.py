#! /usr/bin/env python
"""SearchSource: Springer Link"""
from __future__ import annotations

import re
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

# Note : API requires registration
# https://dev.springernature.com/


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class SpringerLinkSearchSource(JsonSchemaMixin):
    """SearchSource for Springer Link"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "url"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = False
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Springer Link"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/springer_link.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

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

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Springer Link"""

        result = {"confidence": 0.1}

        if filename.suffix == ".csv":
            if data.count("http://link.springer.com") == data.count("\n"):
                result["confidence"] = 1.0
                return result

        # Note : no features in bib file for identification

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of SpringerLink"""

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
        """Load fixes for Springer Link"""

        # pylint: disable=too-many-branches

        for record_dict in records.values():
            if "item_title" in record_dict:
                record_dict["title"] = record_dict["item_title"]
                del record_dict["item_title"]

            if "content_type" in record_dict:
                record = colrev.record.Record(data=record_dict)
                if record_dict["content_type"] == "Article":
                    if "publication_title" in record_dict:
                        record_dict["journal"] = record_dict["publication_title"]
                        del record_dict["publication_title"]
                    record.change_entrytype(new_entrytype="article")

                if record_dict["content_type"] == "Book":
                    if "publication_title" in record_dict:
                        record_dict["series"] = record_dict["publication_title"]
                        del record_dict["publication_title"]
                    record.change_entrytype(new_entrytype="book")

                if record_dict["content_type"] == "Chapter":
                    record_dict["chapter"] = record_dict["title"]
                    if "publication_title" in record_dict:
                        record_dict["title"] = record_dict["publication_title"]
                        del record_dict["publication_title"]
                    record.change_entrytype(new_entrytype="inbook")

                del record_dict["content_type"]

            if "item_doi" in record_dict:
                record_dict["doi"] = record_dict["item_doi"]
                del record_dict["item_doi"]
            if "journal_volume" in record_dict:
                record_dict["volume"] = record_dict["journal_volume"]
                del record_dict["journal_volume"]
            if "journal_issue" in record_dict:
                record_dict["number"] = record_dict["journal_issue"]
                del record_dict["journal_issue"]

            # Fix authors
            if "author" in record_dict:
                # a-bd-z: do not match McDonald
                record_dict["author"] = re.sub(
                    r"([a-bd-z]{1})([A-Z]{1})",
                    r"\g<1> and \g<2>",
                    record_dict["author"],
                )

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Springer Link"""

        return record


if __name__ == "__main__":
    pass
