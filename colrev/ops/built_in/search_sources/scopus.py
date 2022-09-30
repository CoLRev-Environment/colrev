#! /usr/bin/env python
"""SearchSource: Scopus"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
@dataclass
class ScopusSearchSource(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{url}}"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0.0}
        if "source={Scopus}," in data:
            result["confidence"] = 1.0
            return result
        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        if "document_type" in record.data:
            if record.data["document_type"] == "Conference Paper":
                record.data["ENTRYTYPE"] = "inproceedings"
                if "journal" in record.data:
                    record.rename_field(key="journal", new_key="booktitle")
            elif record.data["document_type"] == "Conference Review":
                record.data["ENTRYTYPE"] = "proceedings"
                if "journal" in record.data:
                    record.rename_field(key="journal", new_key="booktitle")

            elif record.data["document_type"] == "Article":
                record.data["ENTRYTYPE"] = "article"

            record.remove_field(key="document_type")

        if "Start_Page" in record.data and "End_Page" in record.data:
            if record.data["Start_Page"] != "nan" and record.data["End_Page"] != "nan":
                record.data["pages"] = (
                    record.data["Start_Page"] + "--" + record.data["End_Page"]
                )
                record.data["pages"] = record.data["pages"].replace(".0", "")
                record.remove_field(key="Start_Page")
                record.remove_field(key="End_Page")

        if "note" in record.data:
            if "cited By " in record.data["note"]:
                record.rename_field(key="note", new_key="cited_by")
                record.data["cited_by"] = record.data["cited_by"].replace(
                    "cited By ", ""
                )

        if "author" in record.data:
            record.data["author"] = record.data["author"].replace("; ", " and ")

        drop = ["source"]
        for field_to_drop in drop:
            record.remove_field(key=field_to_drop)

        return record


if __name__ == "__main__":
    pass
