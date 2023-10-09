#! /usr/bin/env python
"""SearchSource: ACM Digital Library"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_bib
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ACMDigitalLibrarySearchSource(JsonSchemaMixin):
    """ACM digital Library"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.acm_digital_library"
    # Note : the ID contains the doi
    # "https://dl.acm.org/doi/{{ID}}"
    source_identifier = "doi"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "ACM Digital Library"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/"
        + "ops/built_in/search_sources/acm_digital_library.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ACM dDigital Library"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "publisher = {Association for Computing Machinery}," in data:
            result["confidence"] = 0.7
            return result
        # We may also check whether the ID=doi=url
        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
        filename: typing.Optional[Path],
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if params != "":
            # TODO : add API param search
            raise NotImplementedError

        # Interactively add DB search
        if filename is None:
            print("DB search mode")
            print("- Go to https://dl.acm.org/")
            print("- Search for your query")
            filename = operation.get_unique_filename(
                file_path_string="acm_digital_library"
            )
            print(f"- Save search results in {filename}")

        query_file = operation.get_query_filename(filename=filename, instantiate=True)

        add_source = colrev.settings.SearchSource(
            endpoint=cls.endpoint,
            filename=filename,
            search_type=colrev.settings.SearchType.DB,
            search_parameters={"query_file": str(query_file)},
            comment="",
        )
        return add_source

    def run_search(self, rerun: bool) -> None:
        """Run a search of ACM Digital Library"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            if self.review_manager.in_ci_environment():
                raise colrev_exceptions.SearchNotAutomated(
                    "DB search for ACM DL not automated."
                )

            if self.search_source.filename.suffix in [".bib"]:
                print("DB search mode")
                print(
                    f"- Go to {colors.ORANGE}https://dl.acm.org/{colors.END} "
                    "and run the following query:"
                )
                query = Path(
                    self.search_source.search_parameters["query_file"]
                ).read_text(encoding="utf-8")
                print()
                print(f"{colors.ORANGE}{query}{colors.END}")
                print()
                print(
                    f"- Replace search results in {colors.ORANGE}"
                    + str(self.search_source.filename)
                    + colors.END
                )
                input("Press enter to continue")
                # TODO : validate?
                # TODO : print statistics (#added, #changed)
                self.review_manager.dataset.add_changes(
                    path=self.search_source.filename
                )
                return

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

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for ACM Digital Library"""
        record.remove_field(key="url")
        record.remove_field(key="numpages")
        record.remove_field(key="issue_date")
        record.remove_field(key="publisher")
        record.remove_field(key="address")
        record.remove_field(key="month")

        return record
