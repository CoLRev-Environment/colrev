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
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class BackwardSearchSource(JsonSchemaMixin):
    """Backward search extracting references from PDFs using GROBID
    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)
    """

    __api_url = "https://opencitations.net/index/coci/api/v1/references/"

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.pdf_backward_search"
    source_identifier = "bwsearch_ref"
    search_types = [colrev.settings.SearchType.BACKWARD_SEARCH]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "PDF backward search"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/pdf_backward_search.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        if "min_intext_citations" not in settings["search_parameters"]:
            settings["search_parameters"]["min_intext_citations"] = 3

        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        # Do not run in continuous-integration environment
        if not self.review_manager.in_ci_environment():
            self.grobid_service = self.review_manager.get_grobid_service()
            self.grobid_service.start()

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
            comment="",
        )

    def __validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""
        source = self.search_source
        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

        assert source.search_type == colrev.settings.SearchType.BACKWARD_SEARCH

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

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def __bw_search_condition(self, *, record: dict) -> bool:
        # rev_included/rev_synthesized required, but record not in rev_included/rev_synthesized
        if (
            "colrev_status" in self.search_source.search_parameters["scope"]
            and self.search_source.search_parameters["scope"]["colrev_status"]
            == "rev_included|rev_synthesized"
            and record[Fields.STATUS]
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
            ) and "data/pdfs/paper.pdf" != record.get(Fields.FILE, ""):
                return False

        if not (self.review_manager.path / Path(record[Fields.FILE])).is_file():
            self.review_manager.logger.error(f"File not found for {record[Fields.ID]}")
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
                    retrieved_record.data[Fields.ID] = retrieved_record.data[Fields.DOI]
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
            retrieved_record_dict.get(Fields.TITLE, "NA").lower(),
            record.data.get(Fields.TITLE, "").lower(),
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
        pdf_backward_search_feed: colrev.ops.search_feed.GeneralOriginFeed,
        records: dict,
    ) -> None:
        self.review_manager.logger.info("Comparing records with open-citations data")
        for parent_record_id in {
            x["bwsearch_ref"] for x in pdf_backward_search_feed.feed_records.values()
        }:
            parent_record = records[
                parent_record_id[: parent_record_id.find("_backward_search_")]
            ]

            if Fields.DOI not in parent_record:
                continue

            backward_references = self.__get_reference_records(
                record_dict=parent_record
            )
            updated = 0
            overall = 0
            for feed_record_dict in pdf_backward_search_feed.feed_records.values():
                if feed_record_dict["bwsearch_ref"] != parent_record_id:
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
        pdf_backward_search_feed: colrev.ops.search_feed.GeneralOriginFeed,
        records: dict,
        rerun: bool,
    ) -> None:
        # Note: IDs generated by GROBID for cited references
        # may change across grobid versions
        # -> challenge for key-handling/updating searches...

        self.review_manager.logger.info(f" run backward search for {record[Fields.ID]}")

        pdf_path = self.review_manager.path / Path(record[Fields.FILE])
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
                record[Fields.ID] + "_backward_search_" + new_record[Fields.ID]
            )
            try:
                pdf_backward_search_feed.set_id(record_dict=new_record)
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

            prev_record_dict_version = {}
            if new_record[Fields.ID] in pdf_backward_search_feed.feed_records:
                prev_record_dict_version = pdf_backward_search_feed.feed_records[
                    new_record[Fields.ID]
                ]

            added = pdf_backward_search_feed.add_record(
                record=colrev.record.Record(data=new_record),
            )

            if not added and rerun:
                # Note : only re-index/update
                pdf_backward_search_feed.update_existing_record(
                    records=records,
                    record_dict=new_record,
                    prev_record_dict_version=prev_record_dict_version,
                    source=self.search_source,
                    update_time_variant_fields=rerun,
                )

    def run_search(self, rerun: bool) -> None:
        """Run a search of PDFs (backward search based on GROBID)"""

        self.__validate_source()

        # Do not run in continuous-integration environment
        if self.review_manager.in_ci_environment():
            raise colrev_exceptions.SearchNotAutomated(
                "PDF Backward Search not automated."
            )

        records = self.review_manager.dataset.load_records_dict()

        if not records:
            self.review_manager.logger.info(
                "No records imported. Cannot run backward search yet."
            )
            return

        self.review_manager.logger.info(
            "Set min_intext_citations="
            f"{self.search_source.search_parameters['min_intext_citations']}"
        )

        pdf_backward_search_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
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
                    records=records,
                    rerun=rerun,
                )

            except colrev_exceptions.TEIException:
                self.review_manager.logger.info("Eror accessing TEI")

        self.__complement_with_open_citations_data(
            pdf_backward_search_feed=pdf_backward_search_feed, records=records
        )

        pdf_backward_search_feed.print_post_run_search_infos(
            records=records,
        )
        pdf_backward_search_feed.save_feed_file()

        if self.review_manager.dataset.has_changes():
            self.review_manager.create_commit(
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
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        add_source = cls.get_default_source()
        if "min_intext_citations" in params:
            assert params["min_intext_citations"].isdigit()
            add_source.search_parameters["min_intext_citations"] = int(
                params["min_intext_citations"]
            )
        return add_source

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        raise NotImplementedError

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

        record.format_if_mostly_upper(key=Fields.TITLE, case="sentence")
        record.format_if_mostly_upper(key=Fields.JOURNAL, case=Fields.TITLE)
        record.format_if_mostly_upper(key=Fields.BOOKTITLE, case=Fields.TITLE)
        record.format_if_mostly_upper(key=Fields.AUTHOR, case=Fields.TITLE)

        if (
            "multimedia appendix"
            in record.data.get(Fields.TITLE, "").lower()
            + record.data.get(Fields.JOURNAL, "").lower()
        ):
            record.prescreen_exclude(reason="grobid-error")

        if (
            record.data[Fields.ENTRYTYPE] == ENTRYTYPES.MISC
            and Fields.PUBLISHER in record.data
        ):
            record.data[Fields.ENTRYTYPE] = ENTRYTYPES.BOOK

        return record
