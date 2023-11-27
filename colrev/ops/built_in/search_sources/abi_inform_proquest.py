#! /usr/bin/env python
"""SearchSource: ABI/INFORM (ProQuest)"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.load_utils_bib
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
class ABIInformProQuestSearchSource(JsonSchemaMixin):
    """ABI/INFORM (ProQuest)"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    endpoint = "colrev.abi_inform_proquest"
    source_identifier = "{{ID}}"
    search_types = [colrev.settings.SearchType.DB]

    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "ABI/INFORM (ProQuest)"
    docs_link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/colrev/"
        + "ops/built_in/search_sources/abi_inform_proquest.md"
    )

    db_url = "https://search.proquest.com/abicomplete/advanced"

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.source_operation = source_operation
        self.quality_model = self.review_manager.get_qm()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for ABI/INFORM (ProQuest)"""

        result = {"confidence": 0.0}

        if "proquest.com" in data:  # nosec
            if data.count("proquest.com") >= data.count("\n@"):
                result["confidence"] = 1.0
            if data.count("proquest.com") >= data.count("TY  -"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: dict,
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint"""

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params
        )

        if search_type == colrev.settings.SearchType.DB:
            return operation.add_db_source(
                search_source_cls=cls,
                params=params,
            )

        raise NotImplementedError

    def run_search(self, rerun: bool) -> None:
        """Run a search of ABI/INFORM"""

        if self.search_source.search_type == colrev.settings.SearchType.DB:
            self.source_operation.run_db_search(  # type: ignore
                search_source_cls=self.__class__,
                source=self.search_source,
            )

    def __remove_duplicates(self, *, records: dict) -> None:
        to_delete = []
        for record in records.values():
            if re.search(r"-\d{1,2}$", record[Fields.ID]):
                original_record_id = re.sub(r"-\d{1,2}$", "", record[Fields.ID])
                if original_record_id not in records:
                    continue
                original_record = records[original_record_id]

                # Note: between duplicate records,
                # there are variations in spelling and completeness
                if (
                    colrev.record.Record.get_record_similarity(
                        record_a=colrev.record.Record(data=record),
                        record_b=colrev.record.Record(data=original_record),
                    )
                    < 0.9
                ):
                    continue

                if original_record_id not in records:
                    continue
                to_delete.append(record[Fields.ID])
        if to_delete:
            for rid in to_delete:
                self.review_manager.logger.info(f" remove duplicate {rid}")
                del records[rid]

            self.review_manager.dataset.save_records_dict_to_file(
                records=records, save_path=self.search_source.filename
            )

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
            "BOOK": ENTRYTYPES.BOOK,
            "THES": ENTRYTYPES.PHDTHESIS,
        }
        key_map = {
            ENTRYTYPES.ARTICLE: {
                "PY": Fields.YEAR,
                "AU": Fields.AUTHOR,
                "T1": Fields.TITLE,
                "JF": Fields.JOURNAL,
                "AB": Fields.ABSTRACT,
                "VL": Fields.VOLUME,
                "IS": Fields.NUMBER,
                "KW": Fields.KEYWORDS,
                "DO": Fields.DOI,
                "PB": Fields.PUBLISHER,
                "SP": Fields.PAGES,
                "PMID": Fields.PUBMED_ID,
                "SN": Fields.ISSN,
                "AN": "accession_number",
            },
            ENTRYTYPES.PHDTHESIS: {
                "PY": Fields.YEAR,
                "AU": Fields.AUTHOR,
                "T1": Fields.TITLE,
                "UR": Fields.URL,
                "PB": Fields.PUBLISHER,
                "KW": Fields.KEYWORDS,
                "AN": "accession_number",
            },
        }
        list_fields = {"AU": " and ", "KW": ", "}
        ris_loader = colrev.ops.load_utils_ris.RISLoader(
            load_operation=load_operation,
            source=self.search_source,
            list_fields=list_fields,
            unique_id_field="accession_number",
        )
        records = ris_loader.load_ris_records()

        for counter, record_dict in enumerate(records.values()):
            _id = str(counter + 1).zfill(5)
            record_dict[Fields.ID] = _id

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

            # RIS-keys > standard keys
            for ris_key in list(record_dict.keys()):
                if ris_key in ["ENTRYTYPE", "ID", "accession_number"]:
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

        if self.search_source.filename.suffix == ".bib":
            records = colrev.ops.load_utils_bib.load_bib_file(
                load_operation=load_operation, source=self.search_source
            )
            self.__remove_duplicates(records=records)
            return records

        if self.search_source.filename.suffix == ".ris":
            return self.__load_ris(load_operation)

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for ABI/INFORM (ProQuest)"""

        if (
            record.data.get(Fields.JOURNAL, "")
            .lower()
            .endswith("conference proceedings.")
        ):
            record.change_entrytype(
                new_entrytype="inproceedings", qm=self.quality_model
            )

        if Fields.LANGUAGE in record.data:
            if record.data[Fields.LANGUAGE] in ["ENG", "English"]:
                record.update_field(
                    key=Fields.LANGUAGE,
                    value="eng",
                    source="prep_abi_inform_proquest_source",
                )

        return record
