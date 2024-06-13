#! /usr/bin/env python
"""SearchSource: Springer Link"""
from __future__ import annotations

import re
import requests
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
import colrev.settings

# pylint: disable=unused-argument
# pylint: disable=duplicate-code

# Note : API requires registration
# https://dev.springernature.com/


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class SpringerLinkSearchSource(JsonSchemaMixin):
    """Springer Link"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.springer_link"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [SearchType.DB, SearchType.API]

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.supported
    short_name = "Springer Link"
    SETTINGS = {
        "api_key": "packages.search_source.colrev.springer_link.api_key",
    }
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/springer_link.md"
    )
    db_url = "https://link.springer.com/"

    def __init__(
        self, *, source_operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.quality_model = self.review_manager.get_qm()
        self.source_operation = source_operation

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
        params: str,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.DB:
            search_source = operation.create_db_source(
                search_source_cls=cls,
                params={},
            )

        elif search_type == SearchType.API:

            filename = operation.get_unique_filename(file_path_string="springer_link")

            add_settings = colrev.settings.SearchSource(
                endpoint=cls.endpoint,
                filename=filename,
                search_type=SearchType.API,
                search_parameters={},
                comment="",
            )
            params_dict.update(vars(add_settings))
            instance = cls(source_operation=operation, settings=params_dict)
            instance.api_ui()
            search_source = operation.create_api_source(endpoint=cls.endpoint)
            

        else:
            raise NotImplementedError

        operation.add_source_and_search(search_source)
        return search_source

    def search(self, rerun: bool) -> None:
        """Run a search of SpringerLink"""

        if self.search_source.search_type == SearchType.DB:
            self.source_operation.run_db_search(  # type: ignore
                search_source_cls=self.__class__,
                source=self.search_source,
            )
            return
        
        if self.search_source.search_type == SearchType.API:
            query = self.search_source.search_parameters.get("query", "")
            api_key = self.get_api_key()
            self._api_search(query=query, api_key=api_key)
            return

        raise NotImplementedError
    
    def _api_search(self, query: str, api_key: str) -> None:
        
        api_search_url = f"https://api.springernature.com/meta/v2/json?q=keyword:{query}&api_key={api_key}"
        print(api_search_url)
        response = requests.get(api_search_url)
        print(response)
        return

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def _load_csv(self) -> dict:
        def entrytype_setter(record_dict: dict) -> None:
            if record_dict["Content Type"] == "Article":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            elif record_dict["Content Type"] == "Book":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.BOOK
            elif record_dict["Content Type"] == "Chapter":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INBOOK
            else:
                record_dict[Fields.ENTRYTYPE] = "misc"

        def field_mapper(record_dict: dict) -> None:
            record_dict[Fields.TITLE] = record_dict.pop("Item Title", "")
            if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
                record_dict[Fields.JOURNAL] = record_dict.pop("Publication Title", "")
            elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK:
                record_dict[Fields.BOOKTITLE] = record_dict.pop("Book Series Title", "")
            elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.INBOOK:
                record_dict[Fields.CHAPTER] = record_dict.pop("Item Title", "")
                record_dict[Fields.TITLE] = record_dict.pop("Publication Title", "")
            record_dict[Fields.VOLUME] = record_dict.pop("Journal Volume", "")
            record_dict[Fields.NUMBER] = record_dict.pop("Journal Issue", "")
            record_dict[Fields.DOI] = record_dict.pop("Item DOI", "")
            record_dict[Fields.AUTHOR] = record_dict.pop("Authors", "")
            record_dict[Fields.YEAR] = record_dict.pop("Publication Year", "")
            record_dict[Fields.URL] = record_dict.pop("URL", "")
            record_dict.pop("Content Type", None)

            # Fix authors
            # pylint: disable=colrev-missed-constant-usage
            if Fields.AUTHOR in record_dict:
                # a-bd-z: do not match McDonald
                record_dict[Fields.AUTHOR] = re.sub(
                    r"([a-bd-z]{1})([A-Z]{1})",
                    r"\g<1> and \g<2>",
                    record_dict["author"],
                )

            for key in list(record_dict.keys()):
                value = record_dict[key]
                record_dict[key] = str(value)
                if value == "" or pd.isna(value):
                    del record_dict[key]

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            unique_id_field="Item DOI",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=self.review_manager.logger,
        )
        return records
    
    def api_ui(self) -> None:
        """User API key insertion"""
        run = True

        api_key = self.get_api_key()        

        print("\n API key is required for search \n\n")

        while run:

            if api_key:
                print("Api_key vorhanden")

            else: 
                api_key = input("Please enter your Springer Link API key: ")
                if api_key:
                    self.review_manager.environment_manager.update_registry(
                        self.SETTINGS["api_key"], api_key
                    )
                    run = False
                else:
                    print("Invalid input. Please enter a valid API key.")
        return

    def get_api_key(self) -> str:
        """Get API key from settings"""
        api_key = self.review_manager.environment_manager.get_settings_by_key(
            self.SETTINGS["api_key"]
        )
        return api_key if api_key else ""
        

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".csv":
            return self._load_csv()

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Springer Link"""

        return record
