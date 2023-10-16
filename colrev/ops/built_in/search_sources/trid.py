#! /usr/bin/env python
"""SearchSource: Transport Research International Documentation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.load_utils_ris
import colrev.ops.search
import colrev.record
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class TransportResearchInternationalDocumentation(JsonSchemaMixin):
    """Transport Research International Documentation"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.trid"
    source_identifier = "biburl"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "TRID"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/trid.md"
    )
    db_url = "https://trid.trb.org/"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.operation = source_operation
        self.review_manager = source_operation.review_manager

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Transport Research International Documentation"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "UR  - https://trid.trb.org/view/" in data:
            result["confidence"] = 0.9
            return result
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

    def run_search(self, rerun: bool) -> None:
        """Run a search of TRID"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            self.operation.run_db_search()  # type: ignore

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
        references_types = {
            "JOUR": ENTRYTYPES.ARTICLE,
            "RPRT": ENTRYTYPES.TECHREPORT,
            "CHAP": ENTRYTYPES.INBOOK,
            "ABST": ENTRYTYPES.ARTICLE,
        }
        key_map = {
            ENTRYTYPES.ARTICLE: {
                "PY": Fields.YEAR,
                "AU": Fields.AUTHOR,
                "TI": Fields.TITLE,
                "JO": Fields.JOURNAL,
                "AB": Fields.ABSTRACT,
                "VL": Fields.VOLUME,
                "IS": Fields.NUMBER,
                "DO": Fields.DOI,
                "PB": Fields.PUBLISHER,
                "KW": Fields.KEYWORDS,
                "UR": Fields.URL,
                "SP": Fields.PAGES,
                "AN": "accession_number",
            },
            ENTRYTYPES.TECHREPORT: {
                "PY": Fields.YEAR,
                "AU": Fields.AUTHOR,
                "TI": Fields.TITLE,
                "UR": Fields.URL,
                "PB": Fields.PUBLISHER,
                "KW": Fields.KEYWORDS,
                "SP": Fields.PAGES,
                "AN": "accession_number",
            },
        }
        list_fields = {"AU": " and ", "KW": ", ", "UR": ", "}
        ris_loader = colrev.ops.load_utils_ris.RISLoader(
            load_operation=load_operation,
            source=self.search_source,
            list_fields=list_fields,
            unique_id_field="ID",
        )
        records = ris_loader.load_ris_records()
        print(records)

        for record_dict in records.values():
            # pylint: disable=colrev-missed-constant-usage
            record_dict["ID"] = record_dict["AN"]
            if record_dict["TY"] not in references_types:
                msg = (
                    f"{Colors.RED}TY={record_dict['TY']} not yet supported{Colors.END}"
                )
                if not self.review_manager.force_mode:
                    raise NotImplementedError(msg)
                self.review_manager.logger.error(msg)
                continue
            entrytype = references_types[record_dict["TY"]]
            record_dict[Fields.ENTRYTYPE] = entrytype

            # fixes
            if entrytype == ENTRYTYPES.ARTICLE:
                if "T1" in record_dict and "TI" not in record_dict:
                    record_dict["TI"] = record_dict.pop("T1")

            # RIS-keys > standard keys
            for ris_key in list(record_dict.keys()):
                if ris_key in ["accession_number", "ENTRYTYPE", "ID"]:
                    continue
                if ris_key not in key_map[entrytype]:
                    del record_dict[ris_key]
                    # print/notify: ris_key
                    continue
                standard_key = key_map[entrytype][ris_key]
                record_dict[standard_key] = record_dict.pop(ris_key)

        return records

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".ris":
            return self.__load_ris(load_operation)

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Transport Research International Documentation"""

        return record
