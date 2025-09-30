#! /usr/bin/env python
"""SearchSource: SYNERGY-datasets"""
from __future__ import annotations

import datetime
import logging
import tempfile
import typing
from pathlib import Path

import inquirer
import pandas as pd
from git import Repo
from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.search_file
import colrev.utils
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType

# pylint: disable=unused-argument

# pylint: disable=duplicate-code


class SYNERGYDatasetsSearchSource(base_classes.SearchSourcePackageBaseClass):
    """SYNERGY-datasets

    https://github.com/asreview/synergy-dataset

    csv files available in the releases (output directories) are supported:
    https://github.com/asreview/synergy-dataset/tags

    csv files containing article IDs are supported by source-specific preparation.
    metadata is added based on dois and pubmedid (openalex is not yet supported)

    """

    CURRENT_SYNTAX_VERSION = "0.1.0"

    endpoint = "colrev.synergy_datasets"
    # pylint: disable=colrev-missed-constant-usage
    source_identifier = "ID"
    search_types = [SearchType.API]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.search_source = search_file

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
    def __select_datset_interactively(cls) -> str:
        date_now_string = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        temp_path = tempfile.gettempdir() / Path(f"{date_now_string}-synergy")
        temp_path.mkdir()
        Repo.clone_from(
            "https://github.com/asreview/synergy-dataset", temp_path, depth=1
        )
        data_path = temp_path / Path("datasets")
        files = data_path.glob("**/*_ids.csv")

        print("https://github.com/asreview/synergy-dataset")

        choices = [f"{f.parent.name}/{f.name}" for f in files]
        if not choices:
            print("No datasets found.")
            raise ValueError
        questions = [
            inquirer.List(
                "dataset",
                message="Select a dataset:",
                choices=choices,
            )
        ]
        answers = inquirer.prompt(questions)
        dataset = answers.get("dataset", None)

        if not dataset:
            print("No dataset selected.")
            raise ValueError
        print(f"Selected dataset: {dataset}")
        return dataset

    @classmethod
    def add_endpoint(
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            for item in params.split(";"):
                key, value = item.split("=")
                params_dict[key] = value

        print("Retrieving available datasets")
        dataset = cls.__select_datset_interactively()

        filename = colrev.utils.get_unique_filename(
            base_path=path,
            file_path_string=f"SYNERGY_{dataset.replace('/', '_').replace('_ids.csv', '')}",
        )
        search_source = colrev.search_file.ExtendedSearchFile(
            version=cls.CURRENT_SYNTAX_VERSION,
            platform="colrev.synergy_datasets",
            search_results_path=filename,
            search_type=SearchType.API,
            search_string="",
            search_parameters={"dataset": dataset},
            comment="",
        )
        return search_source

    def _load_dataset(self) -> pd.DataFrame:
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
            self.logger.error(
                "Missing metadata percentage: %s", missing_metadata_percentage
            )
            input("ENTER to continue anyway")
        else:
            self.logger.info(
                "Missing metadata: %s", f"{missing_metadata_percentage:.2%}"
            )
        return dataset_df

    def _update_decisions(self, *, decisions: dict, record: dict) -> None:
        if "doi" in record:
            doi = record["doi"].lower()
            if doi in decisions["doi"]:
                decisions["doi"][doi].append(record["label_included"])
            else:
                decisions["doi"][doi] = [record["label_included"]]

        if "pmid" in record:
            pmid = record["pmid"].lower()
            if pmid in decisions["pmid"]:
                decisions["pmid"][pmid].append(record["label_included"])
            else:
                decisions["pmid"][pmid] = [record["label_included"]]

        if "openalex_id" in record:
            oaid = record["openalex_id"].lower()
            if oaid in decisions["openalex_id"]:
                decisions["openalex_id"][oaid].append(record["label_included"])
            else:
                decisions["openalex_id"][oaid] = [record["label_included"]]

    def _check_quality(self, *, decisions: dict) -> None:
        decisions[Fields.DOI] = {
            d: v
            for d, v in decisions[Fields.DOI].items()
            if len(v) > 1 and len(set(v)) != 1
        }
        decisions["pmid"] = {
            d: v
            for d, v in decisions["pmid"].items()
            if len(v) > 1 and len(set(v)) != 1
        }
        decisions["openalex_id"] = {
            d: v
            for d, v in decisions["openalex_id"].items()
            if len(v) > 1 and len(set(v)) != 1
        }
        if decisions[Fields.DOI] or decisions["pmid"] or decisions["openalex_id"]:
            self.logger.error("Errors in dataset: ambiguous inclusion decisions:")
            msg = (
                f"{Colors.RED}"
                + f"- dois: {', '.join(decisions['doi'])}"
                + f"- pmid: {', '.join(decisions['pmid'])}"
                + f"- openalex_id: {', '.join(decisions['openalex_id'])}"
                + f"{Colors.END}"
            )
            print(msg)

    def _prep_record(self, *, record: dict, ind: int) -> None:
        record[Fields.ID] = ind
        record[Fields.ENTRYTYPE] = "article"
        for k in list(record.keys()):
            if str(record[k]) == "nan":
                del record[k]
        if Fields.DOI in record.keys():
            # pylint: disable=colrev-missed-constant-usage
            record[Fields.DOI] = (
                str(record["doi"]).replace("https://doi.org/", "").upper()
            )
        if "pmid" in record.keys():
            record["pmid"] = str(record["pmid"]).replace(
                "https://pubmed.ncbi.nlm.nih.gov/", ""
            )
        if "openalex_id" in record.keys():
            record["openalex_id"] = str(record["openalex_id"]).replace(
                "https://openalex.org/", ""
            )

    def _validate_source(self) -> None:
        source = self.search_source
        self.logger.debug(f"Validate SearchSource {source.search_results_path}")
        assert source.search_type == SearchType.API

    def search(self, rerun: bool) -> None:
        """Run a search of the SYNERGY datasets"""

        self._validate_source()

        dataset_df = self._load_dataset()

        synergy_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=False,
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )
        existing_keys = {
            Fields.DOI: [
                r[Fields.DOI]
                for r in synergy_feed.feed_records.values()
                if Fields.DOI in r
            ],
            "pmid": [
                r["pmid"] for r in synergy_feed.feed_records.values() if "pmid" in r
            ],
            "openalex_id": [
                r["openalex_id"]
                for r in synergy_feed.feed_records.values()
                if "openalex_id" in r
            ],
        }

        decisions: typing.Dict[str, typing.Dict[str, list]] = {
            Fields.DOI: {},
            "pmid": {},
            "openalex_id": {},
        }
        empty_records, duplicates = 0, 0
        for ind, record in enumerate(dataset_df.to_dict(orient="records")):
            self._prep_record(record=record, ind=ind)
            self._update_decisions(decisions=decisions, record=record)
            # Skip records without metadata
            if {Fields.ID, Fields.ENTRYTYPE, "label_included"} == set(record.keys()):
                empty_records += 1
                continue

            # Skip records that are already in the feed
            if any(
                value in existing_keys[key]
                for key, value in record.items()
                if key in [Fields.DOI, "pmid", "openalex_id"]
            ):
                duplicates += 1
                continue

            for key in list(record.keys()):
                if key not in [
                    Fields.ID,
                    Fields.DOI,
                    "pmid",
                    "openalex_id",
                    Fields.ENTRYTYPE,
                ]:
                    record[f"colrev.synergy_datasets.{key}"] = record.pop(key)

            if Fields.DOI in record:
                existing_keys[Fields.DOI].append(record[Fields.DOI])
            if "pmid" in record:
                existing_keys["pmid"].append(record["pmid"])
            if "openalex_id" in record:
                existing_keys["openalex_id"].append(record["openalex_id"])

            synergy_feed.add_update_record(
                retrieved_record=colrev.record.record.Record(record)
            )

            # The linking of doi/... should happen in the prep operation

        self._check_quality(decisions=decisions)
        self.logger.info("Dropped %s empty records", empty_records)
        self.logger.info("Dropped %s duplicate records", duplicates)
        synergy_feed.save()

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":
            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                logger=self.logger,
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
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for SYNERGY-datasets"""

        record.rename_field(
            key="colrev.synergy_datasets.pubmedid", new_key=Fields.PUBMED_ID
        )
        record.rename_field(
            key="colrev.synergy_datasets.openalex_id", new_key="colrev.open_alex.id"
        )
        if not any(
            x in record.data
            for x in [Fields.PUBMED_ID, Fields.DOI, "colrev.open_alex.id"]
        ):
            record.prescreen_exclude(reason="no-metadata-available")
        return record
