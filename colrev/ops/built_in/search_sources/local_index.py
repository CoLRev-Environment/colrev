#! /usr/bin/env python
"""SearchSource: LocalIndex"""
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
import colrev.ui_cli.cli_colors as colors

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class LocalIndexSearchSource(JsonSchemaMixin):
    """Performs a search in the LocalIndex"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "colrev_local_index"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        self.settings = from_dict(data_class=self.settings_class, data=settings)

        self.index_identifier = source_operation.review_manager.email

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of local-index"""

        params = self.settings.search_parameters
        feed_file = self.settings.filename

        records: list = []
        imported_ids = []
        if feed_file.is_file():
            with open(feed_file, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            imported_ids = [x["ID"] for x in records]

        local_index = search_operation.review_manager.get_local_index()

        def retrieve_from_index(params: dict) -> typing.List[dict]:

            # query = {
            #     "query": {
            #         "simple_query_string": {
            #             "query": "...",
            #             "fields": selected_fields,
            #         },
            #     }
            # }
            query = params

            returned_records = local_index.search(query=query)

            records_to_import = [r.get_data() for r in returned_records]

            return records_to_import

        records_to_import = retrieve_from_index(params)

        for record in records_to_import:
            record["colrev_local_index"] = self.index_identifier

        records_to_import = [r for r in records_to_import if r]
        records_to_import = [
            x for x in records_to_import if x["ID"] not in imported_ids
        ]
        nr_record_to_import = len(records_to_import)
        search_operation.review_manager.logger.info(
            f"{colors.GREEN}Retrieved {nr_record_to_import} records {colors.END}"
        )
        records = records + records_to_import

        keys_to_drop = [
            "colrev_status",
            "colrev_origin",
            "screening_criteria",
        ]
        records = [
            {key: item[key] for key in item.keys() if key not in keys_to_drop}
            for item in records
        ]

        if len(records) > 0:
            records_dict = {r["ID"]: r for r in records}
            search_operation.save_feed_file(records=records_dict, feed_file=feed_file)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for local-index"""

        result = {"confidence": 0.0}
        if "colrev_local_index" in data:
            result["confidence"] = 1

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for local-index"""

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        """Source-specific preparation for local-index"""

        return record


if __name__ == "__main__":
    pass
