"""SearchSource: Scopus"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import requests
from pydantic import Field

import colrev.loader.bib
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType


class ScopusSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Scopus"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.scopus"
    source_identifier = "url"
    search_types = [SearchType.DB, SearchType.API]
    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    db_url = "https://www.scopus.com/search/form.uri?display=advanced"

    def __init__(
        self, *, source_operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = self.settings_class(**settings)
        self.quality_model = self.review_manager.get_qm()
        self.operation = source_operation

    def _simple_api_search(self, query: str) -> None:

        api_key = os.getenv("SCOPUS_API_KEY")
        if not api_key:
            self.review_manager.logger.info(
                "No API key found - using DB search instead"
            )
            return

        try:
            url = "https://api.elsevier.com/content/search/scopus"
            params = {
                "query": query,
                # The response.text showed that the count was too high.
                # To retrieve all results, you might need to paginate (using 'start' and 'count').
                "count": 10,
                "start": 0,
                "apiKey": api_key,
            }

            response = requests.get(url, params=params, timeout=30)
            print(response.json())

            if response.status_code == 200:
                data = response.json()
                entries = data.get("search-results", {}).get("entry", [])
                self.review_manager.logger.info(f"Found {len(entries)} results via API")

                output_json_path = Path(
                    self.search_source.search_parameters.get(
                        "output_json", "scopus_results.json"
                    )
                )
                output_bib_path = Path(
                    self.search_source.search_parameters.get(
                        "output_bib", "scopus_results.bib"
                    )
                )

                self._save_simple_results(entries, output_json_path, output_bib_path)
            else:
                self.review_manager.logger.info(f"API Error: {response.status_code}")
        except Exception as e:
            self.review_manager.logger.info(f"API search error: {str(e)}")

    def _save_simple_results(
        self, entries: list, json_path: Path, bib_path: Path
    ) -> None:
        results = []

        for entry in entries:
            record = {
                "ID": entry.get("dc:identifier", "").replace("SCOPUS_ID:", ""),
                "title": entry.get("dc:title", ""),
                "author": self._simple_parse_authors(entry.get("author", [])),
                "year": (
                    entry.get("prism:coverDate", "")[:4]
                    if entry.get("prism:coverDate")
                    else ""
                ),
                "journal": entry.get("prism:publicationName", ""),
                "doi": entry.get("prism:doi", ""),
                "ENTRYTYPE": "article",
            }
            results.append(record)

        with open(json_path, "w" , encoding= "utf-8") as f_json:
            json.dump(results, f_json, indent=2)
        self.review_manager.logger.info(f"Results saved to {json_path}")

        self._convert_to_bib(results, bib_path)

    def _convert_to_bib(self, records: list, bib_path: Path) -> None:
        with open(bib_path, "w") as f:
            for record in records:
                f.write(f"@{record['ENTRYTYPE']}{{{record['ID']},\n")
                for key, value in record.items():
                    if key not in ["ENTRYTYPE", "ID"] and value:
                        f.write(f"  {key} = {{{value}}},\n")
                f.write("}\n\n")
        self.review_manager.logger.info(f"BibTeX file saved to {bib_path}")

    def _simple_parse_authors(self, authors: list) -> str:
        if not isinstance(authors, list):
            return ""
        names = []
        for author in authors[:3]:
            if isinstance(author, dict):
                surname = author.get("surname", "")
                initials = author.get("initials", "")
                if surname:
                    names.append(f"{surname} {initials}".strip())
        return ", ".join(names)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0.0}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
        elif "www.scopus.com" in data:
            if data.count("www.scopus.com") >= data.count("\n@"):
                result["confidence"] = 1.0
        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.settings.SearchSource:
        # TODO: users should have the option to add a DB or API search here.
        # the pubmed SearchSource could be used as an example
        search_source = operation.create_db_source(
            search_source_cls=cls,
            params={},
        )
        operation.add_source_and_search(search_source)
        return search_source

    def search(self, rerun: bool) -> None:
        query = self.search_source.search_parameters.get("query", "")
        # TODO : make sure the query variable is set correctly (based on the search source settings)

        if query and self.search_source.search_type == SearchType.API:
            self.review_manager.logger.info("Attempting API search...")
            self._simple_api_search(query)
            return

        if self.search_source.search_type == SearchType.DB:
            self.operation.run_db_search(
                search_source_cls=self.__class__,
                source=self.search_source,
            )
            return

        raise NotImplementedError

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        return record

    @classmethod
    def _load_bib(cls, *, filename: Path, logger: logging.Logger) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if "document_type" in record_dict:
                if record_dict["document_type"] == "Conference Paper":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
                elif record_dict["document_type"] == "Conference Review":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.PROCEEDINGS
                elif record_dict["document_type"] == "Article":
                    record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE

        def field_mapper(record_dict: dict) -> None:
            if record_dict[Fields.ENTRYTYPE] in [
                ENTRYTYPES.INPROCEEDINGS,
                ENTRYTYPES.PROCEEDINGS,
            ]:
                record_dict[Fields.BOOKTITLE] = record_dict.pop(Fields.JOURNAL, None)

            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
                if (
                    Fields.JOURNAL in record_dict
                    and Fields.BOOKTITLE not in record_dict
                ):
                    record_dict[Fields.BOOKTITLE] = record_dict.pop(Fields.TITLE, None)
                    record_dict[Fields.TITLE] = record_dict.pop(Fields.JOURNAL, None)

            if "art_number" in record_dict:
                record_dict[f"{cls.endpoint}.art_number"] = record_dict.pop(
                    "art_number"
                )
            if "note" in record_dict:
                record_dict[f"{cls.endpoint}.note"] = record_dict.pop("note")
            if "document_type" in record_dict:
                record_dict[f"{cls.endpoint}.document_type"] = record_dict.pop(
                    "document_type"
                )
            if "source" in record_dict:
                record_dict[f"{cls.endpoint}.source"] = record_dict.pop("source")

            if "Start_Page" in record_dict and "End_Page" in record_dict:
                if (
                    record_dict["Start_Page"] != "nan"
                    and record_dict["End_Page"] != "nan"
                ):
                    record_dict[Fields.PAGES] = (
                        record_dict["Start_Page"] + "--" + record_dict["End_Page"]
                    ).replace(".0", "")
                    del record_dict["Start_Page"]
                    del record_dict["End_Page"]

        colrev.loader.bib.run_fix_bib_file(filename, logger=logger)
        records = colrev.loader.load_utils.load(
            filename=filename,
            unique_id_field="ID",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
        )
        return records

    @classmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        if filename.suffix == ".bib":
            return cls._load_bib(filename=filename, logger=logger)
        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        return record
