#! /usr/bin/env python
"""SearchSource: Scopus"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class ScopusSearchSource(JsonSchemaMixin):
    """Scopus"""

    settings_class = colrev.package_manager.package_settings.DefaultSourceSettings
    endpoint = "colrev.scopus"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "url"
    search_types = [SearchType.DB]

    ci_supported: bool = False
    heuristic_status = SearchSourceHeuristicStatus.supported
    short_name = "Scopus"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/packages/search_sources/scopus.md"
    )
    db_url = "https://www.scopus.com/search/form.uri?display=advanced"

    def __init__(
        self, *, source_operation: colrev.process.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.quality_model = self.review_manager.get_qm()
        self.operation = source_operation

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Scopus"""

        result = {"confidence": 0.0}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
            return result

        if "www.scopus.com" in data:
            if data.count("www.scopus.com") >= data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        return operation.add_db_source(
            search_source_cls=cls,
            params=params,
        )

    def search(self, rerun: bool) -> None:
        """Run a search of Scopus"""

        if self.search_source.search_type == SearchType.DB:
            self.operation.run_db_search(  # type: ignore
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
        """Not implemented"""
        return record

    def _load_bib(self) -> dict:
        def field_mapper(record_dict: dict) -> None:
            if "art_number" in record_dict:
                record_dict[f"{self.endpoint}.art_number"] = record_dict.pop(
                    "art_number"
                )
            if "note" in record_dict:
                record_dict[f"{self.endpoint}.note"] = record_dict.pop("note")
            if "document_type" in record_dict:
                record_dict[f"{self.endpoint}.document_type"] = record_dict.pop(
                    "document_type"
                )
            if "source" in record_dict:
                record_dict[f"{self.endpoint}.source"] = record_dict.pop("source")

        records = colrev.loader.load_utils.load(
            filename=self.search_source.filename,
            unique_id_field="ID",
            field_mapper=field_mapper,
            logger=self.review_manager.logger,
        )
        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":
            return self._load_bib()

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.record.Record:
        """Source-specific preparation for Scopus"""

        if "conference" == record.data[Fields.ENTRYTYPE]:
            record.data[Fields.ENTRYTYPE] = "inproceedings"

        if "book" == record.data[Fields.ENTRYTYPE]:
            if Fields.JOURNAL in record.data and Fields.BOOKTITLE not in record.data:
                record.rename_field(key=Fields.TITLE, new_key=Fields.BOOKTITLE)
                record.rename_field(key=Fields.JOURNAL, new_key=Fields.TITLE)

        if "colrev.scopus.document_type" in record.data:
            if record.data["colrev.scopus.document_type"] == "Conference Paper":
                record.change_entrytype(
                    new_entrytype="inproceedings", qm=self.quality_model
                )

            elif record.data["colrev.scopus.document_type"] == "Conference Review":
                record.change_entrytype(
                    new_entrytype="proceedings", qm=self.quality_model
                )

            elif record.data["colrev.scopus.document_type"] == "Article":
                record.change_entrytype("article", qm=self.quality_model)

            record.remove_field(key="colrev.scopus.document_type")

        if (
            "colrev.scopus.Start_Page" in record.data
            and "colrev.scopus.End_Page" in record.data
        ):
            if (
                record.data["colrev.scopus.Start_Page"] != "nan"
                and record.data["colrev.scopus.End_Page"] != "nan"
            ):
                record.data[Fields.PAGES] = (
                    record.data["colrev.scopus.Start_Page"]
                    + "--"
                    + record.data["colrev.scopus.End_Page"]
                )
                record.data[Fields.PAGES] = record.data[Fields.PAGES].replace(".0", "")
                record.remove_field(key="colrev.scopus.Start_Page")
                record.remove_field(key="colrev.scopus.End_Page")

        if "colrev.scopus.note" in record.data:
            if "cited By " in record.data["colrev.scopus.note"]:
                record.rename_field(key="colrev.scopus.note", new_key=Fields.CITED_BY)
                record.data[Fields.CITED_BY] = record.data[Fields.CITED_BY].replace(
                    "cited By ", ""
                )

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = record.data[Fields.AUTHOR].replace(
                "; ", " and "
            )

        record.remove_field(key="colrev.scopus.source")

        return record
