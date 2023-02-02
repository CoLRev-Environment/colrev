#! /usr/bin/env python
"""SearchSource: OpenCitations"""
from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import requests
import zope.interface
from crossref.restful import Etiquette
from crossref.restful import Works
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors

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
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "OpenCitations forward search"
    link = "https://opencitations.net/"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager
        self.etiquette = Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/geritwagner/colrev",
            source_operation.review_manager.email,
        )

    @classmethod
    def get_default_source(cls) -> colrev.settings.SearchSource:
        """Get the default SearchSource settings"""
        return colrev.settings.SearchSource(
            endpoint="colrev_built_in.open_citations_forward_search",
            filename=Path("data/search/forward_search.bib"),
            search_type=colrev.settings.SearchType.FORWARD_SEARCH,
            search_parameters={
                "scope": {"colrev_status": "rev_included|rev_synthesized"}
            },
            load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibtex"},
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

        # rev_included/rev_synthesized
        if "colrev_status" in self.search_source.search_parameters["scope"]:
            if (
                self.search_source.search_parameters["scope"]["colrev_status"]
                == "rev_included|rev_synthesized"
            ) and record["colrev_status"] not in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                return False

        return True

    def __get_forward_search_records(self, *, record_dict: dict) -> list:

        forward_citations = []

        url = f"https://opencitations.net/index/coci/api/v1/citations/{record_dict['doi']}"
        # headers = {"authorization": "YOUR-OPENCITATIONS-ACCESS-TOKEN"}
        headers: typing.Dict[str, str] = {}

        ret = requests.get(url, headers=headers)
        try:
            items = json.loads(ret.text)

            for doi in [x["citing"] for x in items]:
                works = Works(etiquette=self.etiquette)
                crossref_query_return = works.doi(doi)
                if not crossref_query_return:
                    raise colrev_exceptions.RecordNotFoundInPrepSourceException()
                retrieved_record_dict = connector_utils.json_to_record(
                    item=crossref_query_return
                )
                retrieved_record_dict["ID"] = retrieved_record_dict["doi"]
                forward_citations.append(retrieved_record_dict)
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

        nr_added, nr_changed = 0, 0
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
                    nr_added += 1
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
                        nr_changed += 1
        forward_search_feed.save_feed_file()

        if nr_added > 0:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}Retrieved {nr_added} records{colors.END}"
            )
        else:
            search_operation.review_manager.logger.info(
                f"{colors.GREEN}No additional records retrieved{colors.END}"
            )

        if rerun:
            if nr_changed > 0:
                search_operation.review_manager.logger.info(
                    f"{colors.GREEN}Updated {nr_changed} records{colors.END}"
                )
            else:
                if records:
                    search_operation.review_manager.logger.info(
                        f"{colors.GREEN}Records (data/records.bib) up-to-date{colors.END}"
                    )

        if search_operation.review_manager.dataset.has_changes():
            search_operation.review_manager.create_commit(
                msg="Forward search", script_call="colrev search"
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for forward searches (OpenCitations)"""

        result = {"confidence": 0.0}

        return result

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


if __name__ == "__main__":
    pass
