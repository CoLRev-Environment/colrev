#! /usr/bin/env python
"""SearchSource: CoLRev project"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pandasql as ps
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from pandasql.sqldf import PandaSQLException
from tqdm import tqdm

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ColrevProjectSearchSource(JsonSchemaMixin):
    """Performs a search in a CoLRev project"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    # TODO : add a colrev_projet_origin field and use it as the identifier?
    source_identifier = "project"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        if "url" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "url field required in search_parameters"
            )
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of a CoLRev project"""

        if not self.settings.filename.is_file():
            records = []
            imported_ids = []
        else:
            with open(self.settings.filename, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            imported_ids = [x["ID"] for x in records]

        project_review_manager = search_operation.review_manager.get_review_manager(
            path_str=self.settings.search_parameters["scope"]["url"]
        )
        project_review_manager.get_load_operation(
            notify_state_transition_operation=False,
        )
        search_operation.review_manager.logger.info(
            f'Loading records from {self.settings.search_parameters["scope"]["url"]}'
        )
        records_to_import = project_review_manager.dataset.load_records_dict()
        records_to_import = {
            ID: rec for ID, rec in records_to_import.items() if ID not in imported_ids
        }
        records_to_import_list = [
            {k: str(v) for k, v in r.items()} for r in records_to_import.values()
        ]

        search_operation.review_manager.logger.info("Importing selected records")
        for record_to_import in tqdm(records_to_import_list):
            if "selection_clause" in self.settings.search_parameters:
                res = []
                try:
                    # pylint: disable=possibly-unused-variable
                    rec_df = pd.DataFrame.from_records([record_to_import])
                    query = (
                        "SELECT * FROM rec_df WHERE "
                        f"{self.settings.search_parameters['selection_clause']}"
                    )
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    pass

                if len(res) == 0:
                    continue

            colrev.record.Record(data=record_to_import).import_file(
                review_manager=search_operation.review_manager
            )

            records = records + [record_to_import]

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

            search_operation.save_feed_file(
                records=records_dict, feed_file=self.settings.filename
            )

        else:
            print("No records retrieved.")

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for CoLRev projects"""

        # TODO : heuristic for colrev project SearchSource?
        result = {"confidence": 0.0}

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for CoLRev projects"""

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        """Source-specific preparation for CoLRev projects"""

        return record


if __name__ == "__main__":
    pass
