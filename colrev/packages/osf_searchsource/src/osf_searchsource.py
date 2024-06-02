"""Searchsource:OSF"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.loader.load_utils
import colrev.ops.load
import colrev.ops.prep
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.packages.ieee.src.ieee_api
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class OSFSearchSource(JsonSchemaMixin):
    """OSF"""
    def __init__(self,* ,source_operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
       
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager

    def heuristic():



    def add_endpoint():



    def search():



    def get_api_key():



    def run_api_query():



    def _create_record_dict():
       #need info about the data retrieved from the api to turn the file(s) into a .bib file for further analysis

    def _load_bib(self) -> dict:

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            logger=self.review_manager.logger,
            unique_id_field="ID",
        )
        for record_dict in records.values():
            record_dict.pop("type", None)

        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""
        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()
        raise NotImplementedError


    def prepare():
        #need the dict method to create the prepare method
        