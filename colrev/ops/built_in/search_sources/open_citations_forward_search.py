#! /usr/bin/env python
"""SearchSource: OpenCitations"""
from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.crossref
import colrev.ops.search
import colrev.record
from colrev.constants import Fields

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class OpenCitationsSearchSource(JsonSchemaMixin):
    """Forward search based on OpenCitations
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.open_citations_forward_search"
    source_identifier = "fwsearch_ref"
    search_types = [colrev.settings.SearchType.FORWARD_SEARCH]

    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "OpenCitations forward search"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/open_citations_forward_search.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager
        self.crossref_connector = (
            colrev.ops.built_in.search_sources.crossref.CrossrefSearchSource(
                source_operation=source_operation
            )
        )
        self.__etiquette = self.crossref_connector.get_etiquette(
            review_manager=self.review_manager
        )

    @classmethod
    def get_default_source(cls) -> colrev.settings.SearchSource:
        """Get the default SearchSource settings"""
        return colrev.settings.SearchSource(
            endpoint="colrev.open_citations_forward_search",
            filename=Path("data/search/forward_search.bib"),
            search_type=colrev.settings.SearchType.FORWARD_SEARCH,
            search_parameters={
                "scope": {Fields.STATUS: "rev_included|rev_synthesized"}
            },
            comment="",
        )

    def __validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source

        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        assert source.search_type == colrev.settings.SearchType.FORWARD_SEARCH

        if "scope" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "Scope required in the search_parameters"
            )

        if (
            source.search_parameters["scope"][Fields.STATUS]
            != "rev_included|rev_synthesized"
        ):
            raise colrev_exceptions.InvalidQueryException(
                "search_parameters/scope/colrev_status must be rev_included|rev_synthesized"
            )

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def __fw_search_condition(self, *, record: dict) -> bool:
        if Fields.DOI not in record:
            return False

        # rev_included/rev_synthesized required, but record not in rev_included/rev_synthesized
        if (
            Fields.STATUS in self.search_source.search_parameters["scope"]
            and self.search_source.search_parameters["scope"][Fields.STATUS]
            == "rev_included|rev_synthesized"
            and record[Fields.STATUS]
            not in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]
        ):
            return False

        return True

    def __get_forward_search_records(self, *, record_dict: dict) -> list:
        forward_citations = []

        url = f"https://opencitations.net/index/coci/api/v1/citations/{record_dict['doi']}"
        # headers = {"authorization": "YOUR-OPENCITATIONS-ACCESS-TOKEN"}
        headers: typing.Dict[str, str] = {}

        ret = requests.get(url, headers=headers, timeout=300)
        try:
            items = json.loads(ret.text)

            for doi in [x["citing"] for x in items]:
                retrieved_record = self.crossref_connector.query_doi(
                    doi=doi, etiquette=self.__etiquette
                )
                # if not crossref_query_return:
                #     raise colrev_exceptions.RecordNotFoundInPrepSourceException()
                retrieved_record.data[Fields.ID] = retrieved_record.data[Fields.DOI]
                forward_citations.append(retrieved_record.data)
        except json.decoder.JSONDecodeError:
            self.review_manager.logger.info(
                f"Error retrieving citations from Opencitations for {record_dict['ID']}"
            )

        return forward_citations

    def run_search(self, rerun: bool) -> None:
        """Run a forward search based on OpenCitations"""

        # pylint: disable=too-many-branches

        self.__validate_source()

        records = self.review_manager.dataset.load_records_dict()

        if not records:
            print("No records imported. Cannot run forward search yet.")
            return

        forward_search_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        for record in records.values():
            if not self.__fw_search_condition(record=record):
                continue

            self.review_manager.logger.info(
                f"Run forward search for {record[Fields.ID]}"
            )

            new_records = self.__get_forward_search_records(record_dict=record)

            for new_record in new_records:
                new_record["fwsearch_ref"] = (
                    record[Fields.ID] + "_forward_search_" + new_record[Fields.ID]
                )
                new_record["cites_IDs"] = record[Fields.ID]

                try:
                    forward_search_feed.set_id(record_dict=new_record)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if new_record[Fields.ID] in forward_search_feed.feed_records:
                    prev_record_dict_version = forward_search_feed.feed_records[
                        new_record[Fields.ID]
                    ]

                added = forward_search_feed.add_record(
                    record=colrev.record.Record(data=new_record),
                )

                if added:
                    pass
                elif rerun:
                    # Note : only re-index/update
                    forward_search_feed.update_existing_record(
                        records=records,
                        record_dict=new_record,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )

        forward_search_feed.save_feed_file()
        forward_search_feed.print_post_run_search_infos(records=records)

        if self.review_manager.dataset.has_changes():
            self.review_manager.create_commit(
                msg="Forward search", script_call="colrev search"
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for forward searches (OpenCitations)"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint"""

        add_source = cls.get_default_source()
        return add_source

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
        """Source-specific preparation for forward searches (OpenCitations)"""
        return record
