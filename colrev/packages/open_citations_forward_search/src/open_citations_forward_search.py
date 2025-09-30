#! /usr/bin/env python
"""SearchSource: OpenCitations"""
from __future__ import annotations

import json
import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.ops.check
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.crossref.src.crossref_api import query_doi
from colrev.packages.open_citations_forward_search.src import open_citations_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class OpenCitationsSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Forward search based on OpenCitations
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.open_citations_forward_search"
    source_identifier = "fwsearch_ref"
    search_types = [SearchType.FORWARD_SEARCH]

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.supported

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.search_source = search_file

        # TODO / TBD: replace review_manager?
        import colrev.review_manager

        self.review_manager = colrev.review_manager.ReviewManager()
        colrev.ops.check.CheckOperation(self.review_manager)
        self.api = open_citations_api.OpenCitationsAPI()

    @classmethod
    def get_default_source(cls) -> colrev.search_file.ExtendedSearchFile:
        """Get the default SearchSource settings"""
        return colrev.search_file.ExtendedSearchFile(
            version=cls.CURRENT_SYNTAX_VERSION,
            platform="colrev.open_citations_forward_search",
            search_results_path=Path("data/search/forward_search.bib"),
            search_type=SearchType.FORWARD_SEARCH,
            search_string="",
            search_parameters={
                "scope": {Fields.STATUS: "rev_included|rev_synthesized"}
            },
            comment="",
        )

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source

        self.logger.debug(f"Validate SearchSource {source.search_results_path}")

        assert source.search_type == SearchType.FORWARD_SEARCH

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

        self.logger.debug("SearchSource %s validated", source.search_results_path)

    def _fw_search_condition(self, *, record: dict) -> bool:
        if Fields.DOI not in record:
            return False

        # rev_included/rev_synthesized required, but record not in rev_included/rev_synthesized
        if (
            Fields.STATUS in self.search_source.search_parameters["scope"]
            and self.search_source.search_parameters["scope"][Fields.STATUS]
            == "rev_included|rev_synthesized"
            and record[Fields.STATUS]
            not in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]
        ):
            return False

        return True

    def _get_forward_search_records(self, *, record_dict: dict) -> typing.List[dict]:
        forward_citations: typing.List[dict] = []

        url = f"https://opencitations.net/index/coci/api/v1/citations/{record_dict['doi']}"

        try:
            ret = self.api.get(url, timeout=300)
        except open_citations_api.OpenCitationsAPIError:
            self.logger.info(
                "Error retrieving citations from Opencitations for %s",
                record_dict[Fields.ID],
            )
            return forward_citations
        try:
            items = json.loads(ret.text)

            for doi in [x["citing"] for x in items]:
                retrieved_record = query_doi(doi=doi)
                # if not crossref_query_return:
                #     raise colrev_exceptions.RecordNotFoundInPrepSourceException()
                retrieved_record.data[Fields.ID] = retrieved_record.data[Fields.DOI]
                forward_citations.append(retrieved_record.data)
        except json.decoder.JSONDecodeError:
            self.logger.info(
                "Error retrieving citations from Opencitations for %s",
                record_dict[Fields.ID],
            )

        return forward_citations

    def search(self, rerun: bool) -> None:
        """Run a forward search based on OpenCitations"""

        # pylint: disable=too-many-branches

        self._validate_source()

        self.logger.info("Scope: %s", self.search_source.search_parameters["scope"])

        records = self.review_manager.dataset.load_records_dict()

        if not records:
            print("No records imported. Cannot run forward search yet.")
            return

        forward_search_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        relevant_records = [
            record
            for record in records.values()
            if self._fw_search_condition(record=record)
        ]
        self.logger.info("Run forward search for %s records", len(relevant_records))

        for record in relevant_records:

            self.logger.info("Run forward search for %s", record[Fields.ID])

            new_records = self._get_forward_search_records(record_dict=record)

            for new_record in new_records:
                try:
                    new_record["fwsearch_ref"] = (
                        record[Fields.ID] + "_forward_search_" + new_record[Fields.ID]
                    )
                    new_record["cites_ids"] = record[Fields.ID]
                    retrieved_record = colrev.record.record.Record(new_record)

                    forward_search_feed.add_update_record(
                        retrieved_record=retrieved_record
                    )
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

        forward_search_feed.save()

        if self.review_manager.dataset.git_repo.has_record_changes():
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
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint"""

        search_source = cls.get_default_source()
        return search_source

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for forward searches (OpenCitations)"""
        return record
