#! /usr/bin/env python
"""SearchSource: CoLRev project"""
from __future__ import annotations

import shutil
import tempfile
import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pandasql as ps
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from git import Repo
from pandasql.sqldf import PandaSQLException
from tqdm import tqdm

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
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
    source_identifier = "colrev_project_identifier"
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
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = source_operation.review_manager

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
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        if query.startswith("url="):
            filename = search_operation.get_unique_filename(
                file_path_string=query.split("/")[-1]
            )
            return colrev.settings.SearchSource(
                endpoint="colrev.colrev_project",
                filename=filename,
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={"scope": {"url": query[4:]}},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )

        raise NotImplementedError

    def __load_records_to_import(self, *, project_url: str, project_name: str) -> dict:
        temp_path = tempfile.gettempdir() / Path(project_name)
        temp_path.mkdir()
        Repo.clone_from(project_url, temp_path, depth=1)

        try:
            project_review_manager = self.review_manager.get_connecting_review_manager(
                path_str=str(temp_path)
            )
        except colrev_exceptions.RepoSetupError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Error retrieving records from colrev project {project_url} ({exc})"
            ) from exc

        # remote_url = project_review_manager.dataset.get_remote_url()
        # if remote_url != "NA":
        #     project_identifier = remote_url.rstrip(".git")

        project_review_manager.get_load_operation(
            notify_state_transition_operation=False,
        )
        self.review_manager.logger.info(
            f'Loading records from {self.search_source.search_parameters["scope"]["url"]}'
        )
        records_to_import = project_review_manager.dataset.load_records_dict()
        shutil.rmtree(temp_path)
        return records_to_import

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of a CoLRev project"""

        # pylint: disable=too-many-locals
        # pdf_get_operation =
        # self.review_manager.get_pdf_get_operation(notify_state_transition_operation=False)

        colrev_project_search_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )
        project_url = self.search_source.search_parameters["scope"]["url"]
        project_name = project_url.split("/")[-1].rstrip(".git")
        records_to_import = self.__load_records_to_import(
            project_url=project_url, project_name=project_name
        )

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
        records = search_operation.review_manager.dataset.load_records_dict()
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
                    query_select = "SELECT * FROM rec_df WHERE"
                    query = (
                        f"{query_select} "
                        + f"{self.search_source.search_parameters['scope']['condition']}"
                    )
                    res = ps.sqldf(query, locals())
                except PandaSQLException:
                    pass

                if len(res) == 0:
                    continue

            # Note : we need local paths for the PDFs
            # to get local_paths, we need to lookup in the registry.json
            # otherwise, we may also consider retrieving PDFs from local_index automatically
            # if "file" in record_to_import:
            #     record_to_import["file"] = (
            #         Path(self.search_source.search_parameters["scope"]["url"])
            #         / record_to_import["file"]
            #     )

            #     pdf_get_operation.import_file(
            #         record=colrev.record.Record(data=record_to_import)
            #     )

            record_to_import[
                "colrev_project_identifier"
            ] = f"{project_url}#{record_to_import['ID']}"
            record_to_import = {
                k: v for k, v in record_to_import.items() if k not in keys_to_drop
            }

            try:
                colrev_project_search_feed.set_id(record_dict=record_to_import)
                added = colrev_project_search_feed.add_record(
                    record=colrev.record.Record(data=record_to_import),
                )
                if added:
                    colrev_project_search_feed.nr_added += 1
            except colrev_exceptions.NotFeedIdentifiableException:
                print("not identifiable")
                continue

        colrev_project_search_feed.print_post_run_search_infos(records=records)
        colrev_project_search_feed.save_feed_file()

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
