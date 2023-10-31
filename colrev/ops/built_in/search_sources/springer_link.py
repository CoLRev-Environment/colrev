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
import colrev.ops.load_utils_table
import colrev.ops.search
import colrev.record
from colrev.constants import Fields

# pylint: disable=unused-argument
# pylint: disable=duplicate-code

# Note : API requires registration
# https://dev.springernature.com/


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class SpringerLinkSearchSource(JsonSchemaMixin):
    """Springer Link"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.springer_link"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Springer Link"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/springer_link.md"
    )
    db_url = "https://link.springer.com/"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.quality_model = self.review_manager.get_qm()
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Springer Link"""

        result = {"confidence": 0.0}

        if filename.suffix == ".csv":
            if data.count("http://link.springer.com") > data.count("\n") - 2:
                result["confidence"] = 1.0
                return result

        # Note : no features in bib file for identification

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
        """Run a search of SpringerLink"""

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

        if self.search_source.filename.suffix == ".csv":
            csv_loader = colrev.ops.load_utils_table.CSVLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="item_doi",
            )
            table_entries = csv_loader.load_table_entries()
            records = csv_loader.convert_to_records(entries=table_entries)
            self.__load_fixes(records=records)
            return records

        raise NotImplementedError

    def __load_fixes(
        self,
        records: typing.Dict,
    ) -> None:
        """Load fixes for Springer Link"""

        # pylint: disable=too-many-branches

        for record_dict in records.values():
            if "item_title" in record_dict:
                record_dict[Fields.TITLE] = record_dict["item_title"]
                del record_dict["item_title"]

            if record_dict.get("book_series_title", "") == "nan":
                del record_dict["book_series_title"]

            if "content_type" in record_dict:
                record = colrev.record.Record(data=record_dict)
                if record_dict["content_type"] == "Article":
                    if "publication_title" in record_dict:
                        record_dict[Fields.JOURNAL] = record_dict["publication_title"]
                        del record_dict["publication_title"]
                    record.change_entrytype(
                        new_entrytype="article", qm=self.quality_model
                    )

                if record_dict["content_type"] == "Book":
                    if "publication_title" in record_dict:
                        record_dict[Fields.SERIES] = record_dict["publication_title"]
                        del record_dict["publication_title"]
                    record.change_entrytype(new_entrytype="book", qm=self.quality_model)

                if record_dict["content_type"] == "Chapter":
                    record_dict[Fields.CHAPTER] = record_dict[Fields.TITLE]
                    if "publication_title" in record_dict:
                        record_dict[Fields.TITLE] = record_dict["publication_title"]
                        del record_dict["publication_title"]
                    record.change_entrytype(
                        new_entrytype="inbook", qm=self.quality_model
                    )

                del record_dict["content_type"]

            if "item_doi" in record_dict:
                record_dict[Fields.DOI] = record_dict["item_doi"]
                del record_dict["item_doi"]
            if "journal_volume" in record_dict:
                record_dict[Fields.VOLUME] = record_dict["journal_volume"]
                del record_dict["journal_volume"]
            if "journal_issue" in record_dict:
                record_dict[Fields.NUMBER] = record_dict["journal_issue"]
                del record_dict["journal_issue"]

            # Fix authors
            # pylint: disable=colrev-missed-constant-usage
            if Fields.AUTHOR in record_dict:
                # a-bd-z: do not match McDonald
                record_dict[Fields.AUTHOR] = re.sub(
                    r"([a-bd-z]{1})([A-Z]{1})",
                    r"\g<1> and \g<2>",
                    record_dict["author"],
                )

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Springer Link"""

        return record
