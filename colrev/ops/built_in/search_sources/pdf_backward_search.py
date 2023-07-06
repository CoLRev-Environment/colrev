#! /usr/bin/env python
"""SearchSource: backward search (based on PDFs and GROBID)"""
from __future__ import annotations

import json
import typing
from dataclasses import dataclass
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

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
class BackwardSearchSource(JsonSchemaMixin):
    """Performs a backward search extracting references from PDFs using GROBID
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    __api_url = "https://opencitations.net/index/coci/api/v1/references/"

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "bwsearch_ref"
    search_type = colrev.settings.SearchType.BACKWARD_SEARCH
    api_search_supported = True
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "PDF backward search"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/pdf_backward_search.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        if "min_intext_citations" not in settings["search_parameters"]:
            settings["search_parameters"]["min_intext_citations"] = 3

        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        # Do not run in continuous-integration environment
        if not source_operation.review_manager.in_ci_environment():
            self.grobid_service = source_operation.review_manager.get_grobid_service()
            self.grobid_service.start()

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
            endpoint="colrev.pdf_backward_search",
            filename=Path("data/search/pdf_backward_search.bib"),
            search_type=colrev.settings.SearchType.BACKWARD_SEARCH,
            search_parameters={
                "scope": {"colrev_status": "rev_included|rev_synthesized"},
                "min_intext_citations": 3,
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

        if source.search_parameters["scope"].get("file", "") == "paper.md":
            pass
        else:
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

    def __bw_search_condition(self, *, record: dict) -> bool:
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

        # Note: this is for peer_reviews
        if "file" in self.search_source.search_parameters["scope"]:
            if (
                self.search_source.search_parameters["scope"]["file"] == "paper.pdf"
            ) and "data/pdfs/paper.pdf" != record.get("file", ""):
                return False

        if not (self.review_manager.path / Path(record["file"])).is_file():
            self.review_manager.logger.error(f'File not found for {record["ID"]}')
            return False

        return True

    def __get_reference_records(self, *, record_dict: dict) -> list:
        references = []

        url = f"{self.__api_url}{record_dict['doi']}"
        # headers = {"authorization": "YOUR-OPENCITATIONS-ACCESS-TOKEN"}
        headers: typing.Dict[str, str] = {}
        ret = requests.get(url, headers=headers, timeout=300)
        try:
            items = json.loads(ret.text)

            for doi in [x["cited"] for x in items]:
                try:
                    retrieved_record = self.crossref_connector.query_doi(
                        doi=doi, etiquette=self.__etiquette
                    )
                    # if not crossref_query_return:
                    #     raise colrev_exceptions.RecordNotFoundInPrepSourceException()
                    retrieved_record.data["ID"] = retrieved_record.data["doi"]
                    references.append(retrieved_record.data)
                except (
                    colrev_exceptions.RecordNotFoundInPrepSourceException,
                    colrev_exceptions.RecordNotParsableException,
                ):
                    pass
        except json.decoder.JSONDecodeError:
            self.review_manager.logger.info(
                f"Error retrieving citations from Opencitations for {record_dict['ID']}"
            )

        return references

    def __get_similarity(
        self, *, record: colrev.record.Record, retrieved_record_dict: dict
    ) -> float:
        title_similarity = fuzz.partial_ratio(
            retrieved_record_dict.get("title", "NA").lower(),
            record.data.get("title", "").lower(),
        )
        container_similarity = fuzz.partial_ratio(
            colrev.record.PrepRecord(data=retrieved_record_dict)
            .get_container_title()
            .lower(),
            record.get_container_title().lower(),
        )
        weights = [0.6, 0.4]
        similarities = [title_similarity, container_similarity]

        similarity = sum(similarities[g] * weights[g] for g in range(len(similarities)))
        return similarity

    def __complement_with_open_citations_data(
        self,
        *,
        pdf_backward_search_feed: colrev.ops.search.GeneralOriginFeed,
        records: dict,
    ) -> None:
        self.review_manager.logger.info("Comparing records with open-citations data")
        for parent_record_id in {
            x["cited_by_ID"] for x in pdf_backward_search_feed.feed_records.values()
        }:
            parent_record = records[parent_record_id]

            if "doi" not in parent_record:
                continue

            backward_references = self.__get_reference_records(
                record_dict=parent_record
            )
            updated = 0
            overall = 0
            for feed_record_dict in pdf_backward_search_feed.feed_records.values():
                if feed_record_dict["cited_by_ID"] != parent_record_id:
                    continue
                overall += 1
                feed_record = colrev.record.Record(data=feed_record_dict)
                max_similarity = 0.0
                pos = -1
                for i, backward_reference in enumerate(backward_references):
                    similarity = self.__get_similarity(
                        record=feed_record, retrieved_record_dict=backward_reference
                    )
                    if similarity > max_similarity:
                        pos = i
                        max_similarity = similarity
                if max_similarity > 0.9:
                    feed_record.data.update(**backward_references[pos - 1])
                    # del backward_references[pos-1]
                    updated += 1
            self.review_manager.logger.info(
                f" updated {updated}/{overall} records cited by {parent_record_id}"
            )

    def __run_backward_search_on_pdf(
        self,
        *,
        record: dict,
        pdf_backward_search_feed: colrev.ops.search.GeneralOriginFeed,
        search_operation: colrev.ops.search.Search,
        records: dict,
        rerun: bool,
    ) -> None:
        # Note: IDs generated by GROBID for cited references
        # may change across grobid versions
        # -> challenge for key-handling/updating searches...

        self.review_manager.logger.info(f' run backward search for {record["ID"]}')

        pdf_path = self.review_manager.path / Path(record["file"])
        tei = self.review_manager.get_tei(
            pdf_path=pdf_path,
        )

        new_records = tei.get_bibliography(
            min_intext_citations=self.search_source.search_parameters[
                "min_intext_citations"
            ]
        )

        for new_record in new_records:
            if "tei_id" in new_record:
                del new_record["tei_id"]
            new_record["bwsearch_ref"] = (
                record["ID"] + "_backward_search_" + new_record["ID"]
            )
            try:
                pdf_backward_search_feed.set_id(record_dict=new_record)
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

            prev_record_dict_version = {}
            if new_record["ID"] in pdf_backward_search_feed.feed_records:
                prev_record_dict_version = pdf_backward_search_feed.feed_records[
                    new_record["ID"]
                ]

            added = pdf_backward_search_feed.add_record(
                record=colrev.record.Record(data=new_record),
            )

            if added:
                pdf_backward_search_feed.nr_added += 1
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
                    pdf_backward_search_feed.nr_changed += 1

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of PDFs (backward search based on GROBID)"""

        # Do not run in continuous-integration environment
        if search_operation.review_manager.in_ci_environment():
            return

        records = search_operation.review_manager.dataset.load_records_dict()

        if not records:
            search_operation.review_manager.logger.info(
                "No records imported. Cannot run backward search yet."
            )
            return

        search_operation.review_manager.logger.info(
            "Set min_intext_citations="
            f"{self.search_source.search_parameters['min_intext_citations']}"
        )

        pdf_backward_search_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        for record in records.values():
            try:
                if not self.__bw_search_condition(record=record):
                    continue

                self.__run_backward_search_on_pdf(
                    record=record,
                    pdf_backward_search_feed=pdf_backward_search_feed,
                    search_operation=search_operation,
                    records=records,
                    rerun=rerun,
                )

            except colrev_exceptions.TEIException:
                search_operation.review_manager.logger.info("Eror accessing TEI")

        self.__complement_with_open_citations_data(
            pdf_backward_search_feed=pdf_backward_search_feed, records=records
        )

        pdf_backward_search_feed.print_post_run_search_infos(
            records=records,
        )
        pdf_backward_search_feed.save_feed_file()

        if search_operation.review_manager.dataset.has_changes():
            search_operation.review_manager.create_commit(
                msg="Backward search", script_call="colrev search"
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for PDF backward searches (GROBID)"""

        result = {"confidence": 0.0}
        if str(filename).endswith("_ref_list.pdf"):
            result["confidence"] = 1.0
            return result
        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if query == "default":
            return cls.get_default_source()

        if query.startswith("min_intext_citations="):
            source = cls.get_default_source()
            min_intext_citations = query.replace("min_intext_citations=", "")
            assert min_intext_citations.isdigit()
            source.search_parameters["min_intext_citations"] = int(min_intext_citations)
            return source

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add backward_search endpoint with query {query}"
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for PDF backward searches (GROBID)"""

        return records

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for PDF backward searches (GROBID)"""

        record.format_if_mostly_upper(key="title", case="sentence")
        record.format_if_mostly_upper(key="journal", case="title")
        record.format_if_mostly_upper(key="booktitle", case="title")
        record.format_if_mostly_upper(key="author", case="title")

        if (
            "multimedia appendix"
            in record.data.get("title", "").lower()
            + record.data.get("journal", "").lower()
        ):
            record.prescreen_exclude(reason="grobid-error")

        if record.data["ENTRYTYPE"] == "misc" and "publisher" in record.data:
            record.data["ENTRYTYPE"] = "book"

        return record
