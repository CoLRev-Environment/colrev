#! /usr/bin/env python
"""SearchSource: plos"""
from _future_ import annotations

import datetime
import typing
from multiprocessing import Lock
from pathlib import Path
import colrev.colrev.settings

import colrev.process
import colrev.process.operation
import inquirer
import requests
import zope.interface
from pydantic import Field

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_settings
import colrev.packages.doi_org.src.doi_org as doi_connector
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.plos.src import plos_api


if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.settings


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
class PlosSearchSource:
    "Plos API"

    endpoint = "colrev.plos"
    source_identifier=Fields.DOI

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    search_types = [
        SearchType.API,
        SearchType.MD,
    ]

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.oni

    _api_url = "http://api.plos.org/"

    def _init_(
            self, 
            *, 
            source_operation: colrev.process.operation.Operation,
            settings: typing.Optional[dict] = None,
 
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = self._get_search_source(settings)
        self.plos_lock = Lock()
        self.language_service = colrev.env.language_service.LanguageService()

    
    #Function to define the search source. 
    #   If setting exist, use that settings
    #   If not, return the .bib
    #   If it does not exist, create new one (.bib) 
    def _get_search_source(
        self, settings: typing.Optional[dict]
    ) -> colrev.settings.SearchSource:
        if settings:
            # plos as a search_source
            return self.settings_class(**settings)

        # plos as an md-prep source
        plos_md_filename = Path("data/search/md_plos.bib")
        plos_md_source_l = [
            s
            for s in self.review_manager.settings.sources
            if s.filename == plos_md_filename
        ]
        if plos_md_source_l:
            return plos_md_source_l[0]

        return colrev.settings.SearchSource(
            endpoint="colrev.plos",
            filename=plos_md_filename,
            search_type=SearchType.MD,
            search_parameters={},
            comment="",
        )

    def search(self, rerun: bool) -> None:
        "Run a search of plos"

        #Validate search source

        #Create the Object SearchAPIFeed which mange the search on the API
        plos_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.search_type ==SearchType.API:
            self._run_api_search( 
                plos_feed=plos_feed,
                rerun=rerun
            )
        elif self.search_source.search_type == SearchType.MD:
            self._run_md_search(plos_feed)
        else:
            raise NotImplementedError
