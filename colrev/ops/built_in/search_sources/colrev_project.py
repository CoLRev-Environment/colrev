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
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class ColrevProjectSearchSource(JsonSchemaMixin):
    """Performs a search in a CoLRev project"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "colrev_project"

    search_type = colrev.settings.SearchType.OTHER

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if source.source_identifier != self.source_identifier:
            raise colrev_exceptions.InvalidQueryException(
                f"Invalid source_identifier: {source.source_identifier} "
                f"(should be {self.source_identifier})"
            )

        if "scope" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "url" not in source.search_parameters["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "url field required in search_parameters"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of a CoLRev project"""

        # pylint: disable=too-many-locals

        pdf_get_operation = search_operation.review_manager.get_pdf_get_operation()

        records, imported_ids = [], []
        if self.settings.filename.is_file():
            with open(self.settings.filename, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

            imported_ids = [x["ID"] for x in records]

        project_review_manager = search_operation.review_manager.get_review_manager(
            path_str=self.settings.search_parameters["scope"]["url"]
        )

        project_identifier = self.settings.search_parameters["scope"]["url"]
        remote_url = project_review_manager.dataset.get_remote_url()
        if "NA" != remote_url:
            project_identifier = remote_url.rstrip(".git")

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

        nr_record_to_import = len(records_to_import)
        search_operation.review_manager.logger.info(
            f"{colors.GREEN}Retrieved {nr_record_to_import} records {colors.END}"
        )
        search_operation.review_manager.logger.info("Importing selected records")
        for record_to_import in tqdm(list(records_to_import.values())):
            if "condition" in self.settings.search_parameters["scope"]:
                res = []
                try:
                    stringified_copy = colrev.record.Record(
                        data=record_to_import
                    ).get_data(stringify=True)
                    stringified_copy = {k: str(v) for k, v in stringified_copy.items()}
                    # pylint: disable=possibly-unused-variable
                    rec_df = pd.DataFrame.from_records([stringified_copy])
                    query = (
                        "SELECT * FROM rec_df WHERE "
                        f"{self.settings.search_parameters['scope']['condition']}"
                    )
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    pass

                if len(res) == 0:
                    continue

            if "file" in record_to_import:
                record_to_import["file"] = (
                    Path(self.settings.search_parameters["scope"]["url"])
                    / record_to_import["file"]
                )

                pdf_get_operation.import_file(
                    record=colrev.record.Record(data=record_to_import)
                )

            record_to_import["colrev_project"] = project_identifier

            records = records + [record_to_import]

        keys_to_drop = [
            "colrev_masterdata_provenance",
            "colrev_data_provenance",
            "colrev_id",
            "colrev_status",
            "colrev_origin",
            "screening_criteria",
            "grobid-version",
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

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for CoLRev projects"""

        result = {"confidence": 0.0}
        if "colrev_project" in data:
            result["confidence"] = 1.0

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for CoLRev projects"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for CoLRev projects"""

        return record


if __name__ == "__main__":
    pass
