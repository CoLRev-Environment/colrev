#! /usr/bin/env python
"""SearchSource: SYNERGY-datasets"""
from __future__ import annotations

import datetime
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from git import Repo

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.crossref
import colrev.ops.load_utils_bib
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument

# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class SYNERGYDatasetsSearchSource(JsonSchemaMixin):
    """SearchSource for SYNERGY-datasets

    https://github.com/asreview/synergy-dataset

    csv files available in the releases (output directories) are supported:
    https://github.com/asreview/synergy-dataset/tags

    csv files containing article IDs are supported by source-specific preparation.
    metadata is added based on dois and pubmedid (openalex is not yet supported)

    """

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "ID"
    search_type = colrev.settings.SearchType.OTHER
    api_search_supported = True
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "SYNERGY-datasets"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/synergy_datasets.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.Operation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.quality_model = source_operation.review_manager.get_qm()
        self.review_manager = source_operation.review_manager

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for SYNERGY-datasets"""

        result = {"confidence": 0.0}

        if "doi,pmid,openalex_id,label_included" in data:
            result["confidence"] = 1.0

        if '"doi","pmid","openalex_id","label_included"' in data:
            result["confidence"] = 1.0

        if (
            "record_id,pubmedID,title,authors,abstract,year,label_included,label_abstract_screening"
            in data
        ):
            result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(cls, operation: colrev.ops.search.Search, params: str) -> None:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if params is None or not params.startswith("dataset="):
            operation.review_manager.logger.info("Retrieving available datasets")
            date_now_string = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            temp_path = tempfile.gettempdir() / Path(f"{date_now_string}-synergy")
            temp_path.mkdir()
            Repo.clone_from(
                "https://github.com/asreview/synergy-dataset", temp_path, depth=1
            )
            data_path = temp_path / Path("datasets")
            files = data_path.glob("**/*_ids.csv")
            print("https://github.com/asreview/synergy-dataset")
            print(
                "\n- "
                + "\n- ".join([str(f.parent.name) + "/" + str(f.name) for f in files])
            )
            params = input("Enter dataset:")
            params = "dataset=" + params

        if params.startswith("dataset="):
            dataset = params.replace("dataset=", "")
            filename = operation.get_unique_filename(
                file_path_string=f"SYNERGY_{dataset.replace('/', '_').replace('_ids.csv', '')}"
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.synergy_datasets",
                filename=filename,
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={"dataset": dataset},
                comment="",
            )
            operation.review_manager.settings.sources.append(add_source)
            return

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add SYNERGY endpoint with query {params}"
        )

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

    def __load_dataset(self) -> pd.DataFrame:
        date_now_string = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        temp_path = tempfile.gettempdir() / Path(f"{date_now_string}-synergy")
        temp_path.mkdir()
        Repo.clone_from(
            "https://github.com/asreview/synergy-dataset", temp_path, depth=1
        )
        dataset_name = self.search_source.search_parameters["dataset"]
        dataset_df = pd.read_csv(temp_path / Path("datasets") / dataset_name)

        # check data structure
        if not all(x in dataset_df for x in ["doi", "pmid", "openalex_id"]):
            raise colrev_exceptions.SearchSourceException(
                f"Missing doi/pmid/openalex_id in {dataset_name}"
            )
        if "pmid" not in dataset_df:
            dataset_df["pmid"] = pd.NA
        missing_metadata = (
            dataset_df[["doi", "pmid", "openalex_id"]].isna().all(axis="columns")
        )
        missing_metadata_percentage = missing_metadata.sum() / dataset_df.shape[0]
        if missing_metadata_percentage > 0.1:
            self.review_manager.logger.error(
                f"Missing metadata percentage: {missing_metadata_percentage}"
            )
            input("ENTER to continue anyway")
        else:
            self.review_manager.logger.info(
                f"Missing metadata: {missing_metadata_percentage:.2%}"
            )
        return dataset_df

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of the SYNERGY datasets"""

        dataset_df = self.__load_dataset()

        synergy_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=False,
        )
        for i, record in enumerate(dataset_df.to_dict(orient="records")):
            record["ID"] = i
            record["ENTRYTYPE"] = "article"
            for k in list(record.keys()):
                if str(record[k]) == "nan":
                    del record[k]
            if "doi" in record.keys():
                record["doi"] = str(record["doi"]).replace("https://doi.org/", "")
            if "pmid" in record.keys():
                record["pmid"] = str(record["pmid"]).replace(
                    "https://pubmed.ncbi.nlm.nih.gov/", ""
                )
            if "openalex_id" in record.keys():
                record["openalex_id"] = str(record["openalex_id"]).replace(
                    "https://openalex.org/", ""
                )

            # Skip records without metadata
            if {"ID", "ENTRYTYPE", "label_included"} == set(record.keys()):
                continue

            synergy_feed.set_id(record_dict=record)
            synergy_feed.add_record(record=colrev.record.Record(data=record))

            # The linking of doi/... should happen in the prep operation

        synergy_feed.save_feed_file()

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
                load_operation=load_operation,
                source=self.search_source,
                check_bib_file=False,
            )
            for record in records.values():
                if "pmid" in record:
                    record["pubmedid"] = record["pmid"].replace(
                        "https://pubmed.ncbi.nlm.nih.gov/", ""
                    )
                    del record["pmid"]
            return records

        raise NotImplementedError

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for SYNERGY-datasets"""
        if not any(x in record.data for x in ["pmid", "doi", "openalex_id"]):
            record.prescreen_exclude(reason="no-metadata-available")
        return record
