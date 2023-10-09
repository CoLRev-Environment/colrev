#! /usr/bin/env python
"""SearchSource: EBSCOHost"""
from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_bib
import colrev.ops.load_utils_table
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class EbscoHostSearchSource(JsonSchemaMixin):
    """EBSCOHost"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    endpoint = "colrev.ebsco_host"
    # https://connect.ebsco.com/s/article/
    # What-is-the-Accession-Number-AN-in-EBSCOhost-records?language=en_US
    # Note : ID is the accession number.
    source_identifier = "{{ID}}"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "EBSCOHost"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/ebsco_host.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for EBSCOHost"""

        result = {"confidence": 0.0}

        if data.count("@") >= 1:
            if "URL = {https://search.ebscohost.com/" in data:
                if re.match(r"@.*{\d{17}\,\n", data):
                    result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
        filename: typing.Optional[Path],
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint"""

        print("Manual search mode")
        print("- Go to https://search.ebscohost.com/")
        print("- Search for your query")
        filename = operation.get_unique_filename(file_path_string="ebsco_host")
        query_file = str(filename).replace(".bib", "_query.txt")
        with open(query_file, "w", encoding="utf-8") as file:
            file.write("")
        print(f"- Save search results in {filename}")
        print(f"- Save query in {query_file}")
        input("Press Enter to complete")

        add_source = colrev.settings.SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=colrev.settings.SearchType.DB,
            search_parameters={"query_file": query_file},
            comment="",
        )
        return add_source

    def run_search(self, rerun: bool) -> None:
        """Run a search of EbscoHost"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            if self.review_manager.in_ci_environment():
                raise colrev_exceptions.SearchNotAutomated(
                    "DB search for Ebsco Host not automated."
                )

            query = Path(self.search_source.search_parameters["query_file"]).read_text(
                encoding="utf-8"
            )
            print("- Go do https://search.ebscohost.com/")
            print(f"- Search for your query:\n {query}")

            # TODO: depends on whether running IDs were used as origins...
            input("TO update the search results, replace the file!?!??! ")

        else:
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

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            return records

        if self.search_source.filename.suffix == ".csv":
            csv_loader = colrev.ops.load_utils_table.CSVLoader(
                load_operation=load_operation, source=self.search_source
            )
            # TODO: any unique_id??
            table_entries = csv_loader.load_table_entries()
            records = csv_loader.convert_to_records(entries=table_entries)
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for EBSCOHost"""

        return record
