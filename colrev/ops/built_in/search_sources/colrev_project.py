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
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "CoLRev project"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/colrev_project.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
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

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of a CoLRev project"""

        # pylint: disable=too-many-locals

        pdf_get_operation = search_operation.review_manager.get_pdf_get_operation()

        colrev_project_search_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        project_identifier = self.search_source.search_parameters["scope"]["url"]
        try:
            project_review_manager = search_operation.review_manager.get_review_manager(
                path_str=project_identifier
            )
        except colrev_exceptions.RepoSetupError as exc:
            search_operation.review_manager.logger.error(
                f"Error retrieving records from colrev project {project_identifier} ({exc})"
            )
            return

        remote_url = project_review_manager.dataset.get_remote_url()
        if remote_url != "NA":
            project_identifier = remote_url.rstrip(".git")

        project_review_manager.get_load_operation(
            notify_state_transition_operation=False,
        )
        search_operation.review_manager.logger.info(
            f'Loading records from {self.search_source.search_parameters["scope"]["url"]}'
        )
        records_to_import = project_review_manager.dataset.load_records_dict()

        keys_to_drop = [
            "colrev_masterdata_provenance",
            "colrev_data_provenance",
            "colrev_id",
            "colrev_status",
            "colrev_origin",
            "screening_criteria",
            "grobid-version",
        ]

        search_operation.review_manager.logger.info("Importing selected records")
        nr_added = 0
        for record_to_import in tqdm(list(records_to_import.values())):
            if "condition" in self.search_source.search_parameters["scope"]:
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
                        f"{self.search_source.search_parameters['scope']['condition']}"
                    )
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    pass

                if len(res) == 0:
                    continue

            if "file" in record_to_import:
                record_to_import["file"] = (
                    Path(self.search_source.search_parameters["scope"]["url"])
                    / record_to_import["file"]
                )

                pdf_get_operation.import_file(
                    record=colrev.record.Record(data=record_to_import)
                )

            record_to_import["colrev_project_identifier"] = (
                project_identifier + record_to_import["ID"]
            )
            record_to_import = {
                k: v for k, v in record_to_import.items() if k not in keys_to_drop
            }

            try:
                colrev_project_search_feed.set_id(record_dict=record_to_import)
                added = colrev_project_search_feed.add_record(
                    record=colrev.record.Record(data=record_to_import),
                )
                if added:
                    nr_added += 1
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

        colrev_project_search_feed.save_feed_file()
        search_operation.review_manager.logger.info(
            f"{colors.GREEN}Retrieved {nr_added} new records {colors.END}"
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
