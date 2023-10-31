#! /usr/bin/env python
"""SearchSource: IEEEXplore"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.ieee_api
import colrev.ops.load_utils_ris
import colrev.ops.prep
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
class IEEEXploreSearchSource(JsonSchemaMixin):
    """IEEEXplore"""

    flag = True
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "ID"
    search_types = [colrev.settings.SearchType.API]
    endpoint = "colrev.ieee"

    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.oni
    short_name = "IEEE Xplore"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/ieee.md"
    )
    db_url = "https://ieeexplore.ieee.org/Xplore/home.jsp"
    SETTINGS = {
        "api_key": "packages.search_source.colrev.ieee.api_key",
    }

    # pylint: disable=colrev-missed-constant-usage
    API_FIELDS = [
        "abstract",
        "author_url",
        "accessType",
        "article_number",
        "author_order",
        "author_terms",
        "affiliation",
        "citing_paper_count",
        "conference_dates",
        "conference_location",
        "content_type",
        "doi",
        "publisher",
        "pubtype",
        "d-year",
        "end_page",
        "facet",
        "full_name",
        "html_url",
        "ieee_terms",
        "isbn",
        "issn",
        "issue",
        "pdf_url",
        "publication_year",
        "publication_title",
        "standard_number",
        "standard_status",
        "start_page",
        "title",
        "totalfound",
        "totalsearched",
        "volume",
    ]

    FIELD_MAPPING = {
        "citing_paper_count": "citations",
        "publication_year": Fields.YEAR,
        "html_url": Fields.URL,
        "pdf_url": Fields.FULLTEXT,
        "issue": Fields.NUMBER,
    }

    def __init__(
        self,
        *,
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager

        if settings:
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            self.search_source = colrev.settings.SearchSource(
                endpoint=self.endpoint,
                filename=Path("data/search/ieee.bib"),
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={},
                comment="",
            )
        self.operation = source_operation

    # For run_search, a Python SDK would be available:
    # https://developer.ieee.org/Python_Software_Development_Kit

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for IEEEXplore"""

        result = {"confidence": 0.1}

        if "Date Added To Xplore" in data:
            result["confidence"] = 0.9
            return result

        return result

    @classmethod
    def add_endpoint(
        cls, operation: colrev.ops.search.Search, params: dict
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params
        )

        if search_type == colrev.settings.SearchType.API:
            if len(params) == 0:
                add_source = operation.add_api_source(endpoint=cls.endpoint)
                return add_source

            # pylint: disable=colrev-missed-constant-usage
            if (
                "https://ieeexploreapi.ieee.org/api/v1/search/articles?"
                in params["url"]
            ):
                query = (
                    params["url"]
                    .replace(
                        "https://ieeexploreapi.ieee.org/api/v1/search/articles?", ""
                    )
                    .lstrip("&")
                )

                parameter_pairs = query.split("&")
                search_parameters = {}
                for parameter in parameter_pairs:
                    key, value = parameter.split("=")
                    search_parameters[key] = value

                last_value = list(search_parameters.values())[-1]

                filename = operation.get_unique_filename(
                    file_path_string=f"ieee_{last_value}"
                )

                add_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename,
                    search_type=colrev.settings.SearchType.API,
                    search_parameters=search_parameters,
                    comment="",
                )
                return add_source

        # if search_type == colrev.settings.SearchType.API:

        raise NotImplementedError

    def run_search(self, rerun: bool) -> None:
        """Run a search of IEEEXplore"""

        ieee_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type == colrev.settings.SearchType.API:
            self.__run_api_search(ieee_feed=ieee_feed, rerun=rerun)

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore

        else:
            raise NotImplementedError

    def __get_api_key(self) -> str:
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )
        if api_key is None or len(api_key) != 24:
            api_key = input("Please enter api key: ")
            self.review_manager.environment_manager.update_registry(
                self.SETTINGS["api_key"], api_key
            )
        return api_key

    # pylint: disable=colrev-missed-constant-usage
    def __run_api_query(self) -> colrev.ops.built_in.search_sources.ieee_api.XPLORE:
        api_key = self.__get_api_key()
        query = colrev.ops.built_in.search_sources.ieee_api.XPLORE(api_key)
        query.dataType("json")
        query.dataFormat("object")
        query.maximumResults(50000)
        query.usingOpenAccess = False

        parameter_methods = {}
        parameter_methods["article_number"] = query.articleNumber
        parameter_methods["doi"] = query.doi
        parameter_methods["author"] = query.authorText
        parameter_methods["isbn"] = query.isbn
        parameter_methods["issn"] = query.issn
        parameter_methods["publication_year"] = query.publicationYear
        parameter_methods["queryText"] = query.queryText
        parameter_methods["parameter"] = query.queryText

        parameters = self.search_source.search_parameters
        for key, value in parameters.items():
            if key in parameter_methods:
                method = parameter_methods[key]
                method(value)
        return query

    def __run_api_search(
        self, ieee_feed: colrev.ops.search_feed.GeneralOriginFeed, rerun: bool
    ) -> None:
        query = self.__run_api_query()
        query.startRecord = 1
        response = query.callAPI()
        while "articles" in response:
            records = self.review_manager.dataset.load_records_dict()
            articles = response["articles"]

            for article in articles:
                prev_record_dict_version: dict = {}
                record_dict = self.__create_record_dict(article)
                record = colrev.record.Record(data=record_dict)
                added = ieee_feed.add_record(record=record)

                if added:
                    self.review_manager.logger.info(
                        " retrieve " + record.data[Fields.ID]
                    )
                else:
                    changed = ieee_feed.update_existing_record(
                        records=records,
                        record_dict=record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        self.review_manager.logger.info(
                            " update " + record.data[Fields.ID]
                        )

            query.startRecord += 200
            response = query.callAPI()

        ieee_feed.print_post_run_search_infos(records=records)
        ieee_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)

    def __update_special_case_fields(self, *, record_dict: dict, article: dict) -> None:
        if "start_page" in article:
            record_dict[Fields.PAGES] = article.pop("start_page")
            if "end_page" in article:
                record_dict[Fields.PAGES] += "--" + article.pop("end_page")

        if "authors" in article and "authors" in article["authors"]:
            author_list = []
            for author in article["authors"]["authors"]:
                author_list.append(author["full_name"])
            record_dict[Fields.AUTHOR] = colrev.record.PrepRecord.format_author_field(
                input_string=" and ".join(author_list)
            )

        if (
            "index_terms" in article
            and "author_terms" in article["index_terms"]
            and "terms" in article["index_terms"]["author_terms"]
        ):
            record_dict[Fields.KEYWORDS] = ", ".join(
                article["index_terms"]["author_terms"]["terms"]
            )

    def __create_record_dict(self, article: dict) -> dict:
        record_dict = {Fields.ID: article["article_number"]}
        # self.review_manager.p_printer.pprint(article)

        if article["content_type"] == "Conferences":
            record_dict[Fields.ENTRYTYPE] = "inproceedings"
            if "publication_title" in article:
                record_dict[Fields.BOOKTITLE] = article.pop("publication_title")
        else:
            record_dict[Fields.ENTRYTYPE] = "article"
            if "publication_title" in article:
                record_dict[Fields.JOURNAL] = article.pop("publication_title")

        for field in self.API_FIELDS:
            if article.get(field) is None:
                continue
            record_dict[field] = str(article.get(field))

        for api_field, rec_field in self.FIELD_MAPPING.items():
            if api_field not in record_dict:
                continue
            record_dict[rec_field] = record_dict.pop(api_field)

        self.__update_special_case_fields(record_dict=record_dict, article=article)

        return record_dict

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def __load_ris(self, load_operation: colrev.ops.load.Load) -> dict:
        entrytype_map = {
            "JOUR": ENTRYTYPES.ARTICLE,
            "CONF": ENTRYTYPES.INPROCEEDINGS,
        }
        key_map = {
            ENTRYTYPES.ARTICLE: {
                "PY": Fields.YEAR,
                "AU": Fields.AUTHOR,
                "TI": Fields.TITLE,
                "T2": Fields.JOURNAL,
                "AB": Fields.ABSTRACT,
                "VL": Fields.VOLUME,
                "IS": Fields.NUMBER,
                "DO": Fields.DOI,
                "PB": Fields.PUBLISHER,
                "UR": Fields.URL,
                "SP": Fields.PAGES,
            },
            ENTRYTYPES.INPROCEEDINGS: {
                "PY": Fields.YEAR,
                "AU": Fields.AUTHOR,
                "TI": Fields.TITLE,
                "T2": Fields.BOOKTITLE,
                "DO": Fields.DOI,
                "SP": Fields.PAGES,
            },
        }

        ris_loader = colrev.ops.load_utils_ris.RISLoader(
            load_operation=load_operation,
            source=self.search_source,
            list_fields={"AU": " and "},
        )
        records = ris_loader.load_ris_records()

        for record_dict in records.values():
            ris_loader.apply_entrytype_mapping(
                record_dict=record_dict, entrytype_map=entrytype_map
            )

            # fixes
            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                if "T1" in record_dict and "TI" not in record_dict:
                    record_dict["TI"] = record_dict.pop("T1")

            ris_loader.map_keys(record_dict=record_dict, key_map=key_map)

        return records

    def __fix_csv_records(self, *, records: dict) -> None:
        for record in records.values():
            record[Fields.FULLTEXT] = record.pop("pdf_link")
            if "article_citation_count" in record:
                record[Fields.CITED_BY] = record.pop("article_citation_count")
            if "author_keywords" in record:
                record[Fields.KEYWORDS] = record.pop("author_keywords")
            record[Fields.TITLE] = record.pop("document_title")
            if "start_page" in record and "end_page" in record:
                record[Fields.PAGES] = record["start_page"] + "--" + record["end_page"]
                del record["start_page"]
                del record["end_page"]
            if "isbns" in record:
                record[Fields.ISBN] = record.pop("isbns")
            if record["document_identifier"] == "IEEE Conferences":
                record[Fields.ENTRYTYPE] = "inproceedings"
                record[Fields.BOOKTITLE] = record.pop("publication_title")
            elif record["document_identifier"] == "IEEE Journals":
                record[Fields.ENTRYTYPE] = "article"
                record[Fields.JOURNAL] = record.pop("publication_title")
            elif record["document_identifier"] == "IEEE Standards":
                record[Fields.ENTRYTYPE] = "techreport"
                record["key"] = record.pop("publication_title")

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".ris":
            return self.__load_ris(load_operation)

        if self.search_source.filename.suffix == ".csv":
            csv_loader = colrev.ops.load_utils_table.CSVLoader(
                load_operation=load_operation,
                source=self.search_source,
                unique_id_field="accession_number",
            )
            table_entries = csv_loader.load_table_entries()
            for entry_id, entry in table_entries.items():
                table_entries[entry_id]["accession_number"] = entry["pdf_link"].split(
                    "="
                )[-1]
            records = csv_loader.convert_to_records(entries=table_entries)
            self.__fix_csv_records(records=records)
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for IEEEXplore"""

        if source.filename.suffix == ".csv":
            if Fields.AUTHOR in record.data:
                record.data[
                    Fields.AUTHOR
                ] = colrev.record.PrepRecord.format_author_field(
                    input_string=record.data[Fields.AUTHOR]
                )
            return record
        return record
