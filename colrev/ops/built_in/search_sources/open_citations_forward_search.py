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

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class OpenCitationsSearchSource(JsonSchemaMixin):
    """Performs a forward search based on OpenCitations
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "fwsearch_ref"
    search_type = colrev.settings.SearchType.FORWARD_SEARCH
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "OpenCitations forward search"
    link = (
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
                "scope": {"colrev_status": "rev_included|rev_synthesized"}
            },
            load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
            comment="",
        )

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "scope" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "Scope required in the search_parameters"
            )

        if (
            source.search_parameters["scope"]["colrev_status"]
            != "rev_included|rev_synthesized"
        ):
            raise colrev_exceptions.InvalidQueryException(
                "search_parameters/scope/colrev_status must be rev_included|rev_synthesized"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __fw_search_condition(self, *, record: dict) -> bool:
        if "doi" not in record:
            return False

        # rev_included/rev_synthesized required, but record not in rev_included/rev_synthesized
        if (
            "colrev_status" in self.search_source.search_parameters["scope"]
            and self.search_source.search_parameters["scope"]["colrev_status"]
            == "rev_included|rev_synthesized"
            and record["colrev_status"]
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
                retrieved_record.data["ID"] = retrieved_record.data["doi"]
                forward_citations.append(retrieved_record.data)
        except json.decoder.JSONDecodeError:
            self.review_manager.logger.info(
                f"Error retrieving citations from Opencitations for {record_dict['ID']}"
            )

        return forward_citations

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a forward search based on OpenCitations"""

        # pylint: disable=too-many-branches

        records = search_operation.review_manager.dataset.load_records_dict()

        if not records:
            print("No records imported. Cannot run forward search yet.")
            return

        forward_search_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        for record in records.values():
            if not self.__fw_search_condition(record=record):
                continue

            search_operation.review_manager.logger.info(
                f'Run forward search for {record["ID"]}'
            )

            new_records = self.__get_forward_search_records(record_dict=record)

            for new_record in new_records:
                new_record["fwsearch_ref"] = (
                    record["ID"] + "_forward_search_" + new_record["ID"]
                )
                new_record["cites_IDs"] = record["ID"]

                try:
                    forward_search_feed.set_id(record_dict=new_record)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if new_record["ID"] in forward_search_feed.feed_records:
                    prev_record_dict_version = forward_search_feed.feed_records[
                        new_record["ID"]
                    ]

                added = forward_search_feed.add_record(
                    record=colrev.record.Record(data=new_record),
                )

                if added:
                    forward_search_feed.nr_added += 1
                elif rerun:
                    # Note : only re-index/update
                    changed = search_operation.update_existing_record(
                        records=records,
                        record_dict=new_record,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        forward_search_feed.nr_changed += 1

        forward_search_feed.save_feed_file()
        forward_search_feed.print_post_run_search_infos(records=records)

        if search_operation.review_manager.dataset.has_changes():
            search_operation.review_manager.create_commit(
                msg="Forward search", script_call="colrev search"
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for forward searches (OpenCitations)"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        return cls.get_default_source()

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
        """Load fixes for forward searches (OpenCitations)"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for forward searches (OpenCitations)"""
        return record
