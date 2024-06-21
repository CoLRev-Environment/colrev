#! /usr/bin/env python
"""Indexing and retrieving records locally."""
from __future__ import annotations

import collections
import io
import os
import typing
from copy import deepcopy
from datetime import timedelta
from multiprocessing import Lock
from pathlib import Path
from threading import Timer

import pandas as pd
import requests_cache
from tqdm import tqdm

import colrev.env.environment_manager
import colrev.env.local_index_sqlite
import colrev.env.resources
import colrev.env.tei_parser
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.check
import colrev.record.record
import colrev.review_manager
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.constants import LocalIndexFields
from colrev.constants import RecordState
from colrev.env.local_index_prep import prepare_record_for_indexing
from colrev.writer.write_utils import to_string


class LocalIndexBuilder:
    """The LocalIndexBuilder implements indexing functionality"""

    def __init__(
        self,
        *,
        index_tei: bool = False,
        verbose_mode: bool = False,
    ) -> None:
        self.verbose_mode = verbose_mode
        self.environment_manager = colrev.env.environment_manager.EnvironmentManager()
        self._index_tei = index_tei
        self.thread_lock = Lock()

    def reinitialize_sqlite_db(self) -> None:
        """Reinitialize the SQLITE database ()"""

        Filepaths.LOCAL_INDEX_SQLITE_FILE.unlink(missing_ok=True)
        colrev.env.local_index_sqlite.SQLiteIndexRecord(reinitialize=True)
        colrev.env.local_index_sqlite.SQLiteIndexTOC(reinitialize=True)

    def _outlets_duplicated(self) -> bool:
        print("Validate curated metadata")

        try:
            curated_outlets = self.environment_manager.get_curated_outlets()
            if len(curated_outlets) != len(set(curated_outlets)):
                duplicated = [
                    item
                    for item, count in collections.Counter(curated_outlets).items()
                    if count > 1
                ]
                print(
                    f"Error: Duplicate outlets in curated_metadata : {','.join(duplicated)}"
                )
                return True

        except colrev_exceptions.CuratedOutletNotUnique as exc:
            print(exc)
            return True
        return False

    def _drop_toc_item(
        self, *, toc_to_index: dict, copy_for_toc_index: dict, curated_masterdata: bool
    ) -> None:
        if not curated_masterdata or copy_for_toc_index.get(
            Fields.ENTRYTYPE, ""
        ) not in [
            ENTRYTYPES.ARTICLE,
            ENTRYTYPES.INPROCEEDINGS,
        ]:
            return

        toc_item = colrev.record.record.Record(copy_for_toc_index).get_toc_key()
        # Note : drop (do not index) tocs where records are missing
        # otherwise, record-not-in-toc will be triggered erroneously.
        drop_toc = copy_for_toc_index[
            Fields.STATUS
        ] not in RecordState.get_post_x_states(state=RecordState.md_processed)
        try:
            colrev_id = colrev.record.record.Record(copy_for_toc_index).get_colrev_id(
                assume_complete=True
            )
        except colrev_exceptions.NotEnoughDataToIdentifyException:
            drop_toc = True
        if drop_toc:
            toc_to_index[toc_item] = "DROPPED"
        elif toc_to_index.get("toc_item", "") != "DROPPED":
            if toc_item in toc_to_index:
                toc_to_index[toc_item] += f";{colrev_id}"
            else:
                toc_to_index[toc_item] = colrev_id

    def _add_index_records(self, *, recs_to_index: list, curated_fields: list) -> None:
        list_to_add = [
            {
                k: v
                for k, v in el.items()
                if k in colrev.env.local_index_sqlite.SQLiteIndexRecord.KEYS
            }
            for el in recs_to_index
        ]
        sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
        for item in list_to_add:
            for (
                records_index_required_key
            ) in colrev.env.local_index_sqlite.SQLiteIndexRecord.KEYS:
                if records_index_required_key not in item:
                    item[records_index_required_key] = ""
            if item[LocalIndexFields.ID] == "":
                print("NO ID IN RECORD")
                continue

            if not sqlite_index_record.exists(local_index_id=item[LocalIndexFields.ID]):
                sqlite_index_record.insert(item)
            else:
                if not curated_fields:
                    continue
                try:
                    stored_record = sqlite_index_record.get(
                        key=Fields.COLREV_ID,
                        value=item[Fields.COLREV_ID],
                    )

                    self._amend_record(
                        sqlite_index_record=sqlite_index_record,
                        stored_record_dict=stored_record,
                        item_to_add=item,
                        curated_fields=curated_fields,
                    )
                except colrev_exceptions.RecordNotInIndexException:  # pragma: no cover
                    pass

        sqlite_index_record.commit()

    def _amend_record(
        self,
        *,
        sqlite_index_record: colrev.env.local_index_sqlite.SQLiteIndexRecord,
        stored_record_dict: dict,
        item_to_add: dict,
        curated_fields: list,
    ) -> None:
        """Adds layered fields to amend existing records"""

        item_record_dict = colrev.loader.load_utils.loads(
            load_string=item_to_add[LocalIndexFields.BIBTEX],
            implementation="bib",
            unique_id_field="ID",
        )
        item_record = colrev.record.record.Record(list(item_record_dict.values())[0])
        stored_record = colrev.record.record.Record(stored_record_dict)

        for curated_field in curated_fields:
            if curated_field in stored_record.data:
                print(f"{curated_field} already in record")
                continue

            if curated_field not in item_record.data:
                continue
            stored_record.update_field(
                key=curated_field,
                value=item_record.data[curated_field],
                source=item_record.get_field_provenance_source(curated_field),
            )

        bibtex = to_string(
            records_dict={stored_record.data[Fields.ID]: stored_record.data},
            implementation="bib",
        )

        sqlite_index_record.update(
            local_index_id=item_to_add[LocalIndexFields.ID], bibtex=bibtex
        )

    # pylint: disable=too-many-arguments
    def index_records(
        self,
        *,
        records: dict,
        repo_source_path: Path,
        curation_url: str,
        curated_masterdata: bool,
        curated_fields: list,
    ) -> None:
        """Index a CoLRev project"""

        recs_to_index = []
        toc_to_index: typing.Dict[str, str] = {}
        for record_dict in tqdm(records.values()):
            copy_for_toc_index = deepcopy(record_dict)
            try:
                record_dict[Fields.METADATA_SOURCE_REPOSITORY_PATHS] = str(
                    repo_source_path
                )
                if curated_fields:
                    for curated_field in curated_fields:
                        colrev.record.record.Record(record_dict).add_field_provenance(
                            key=curated_field, source=f"CURATED:{curation_url}"
                        )
                if curated_masterdata:
                    colrev.record.record.Record(record_dict).set_masterdata_curated(
                        curation_url
                    )

                # Set absolute file paths and set bibtex field (for simpler retrieval)
                if Fields.FILE in record_dict:
                    record_dict.update(
                        file=repo_source_path / Path(record_dict[Fields.FILE])
                    )
                record_dict[LocalIndexFields.BIBTEX] = to_string(
                    records_dict={record_dict[Fields.ID]: record_dict},
                    implementation="bib",
                )
                record_dict = prepare_record_for_indexing(record_dict)
                recs_to_index.append(record_dict)

            except (
                colrev_exceptions.RecordNotIndexableException,
                colrev_exceptions.NotTOCIdentifiableException,
                colrev_exceptions.NotEnoughDataToIdentifyException,
            ) as exc:
                if self.verbose_mode:
                    print(exc)
                    print(record_dict)
            finally:
                self._drop_toc_item(
                    toc_to_index=toc_to_index,
                    copy_for_toc_index=copy_for_toc_index,
                    curated_masterdata=curated_masterdata,
                )
        # Select fields and insert into index (sqlite)

        self._index_tei_document(recs_to_index)

        self._add_index_records(
            recs_to_index=recs_to_index, curated_fields=curated_fields
        )

        if curated_masterdata:
            sqlite_index_toc = colrev.env.local_index_sqlite.SQLiteIndexTOC()
            sqlite_index_toc.add(toc_to_index)

    def _load_masterdata_curations(self) -> dict:  # pragma: no cover
        # Note : the following should be replaced by heuristics
        # based on the data (between colrev load and prep)
        masterdata_curations = {}
        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.env", filename=Path("masterdata_curations.csv")
        )

        if filedata:
            for masterdata_curation in filedata.decode("utf-8").splitlines():
                masterdata_curations[masterdata_curation.lower()] = (
                    masterdata_curation.lower()
                )

        return masterdata_curations

    def index_colrev_project(self, repo_source_path: Path) -> None:  # pragma: no cover
        """Index a CoLRev project"""
        try:
            if not Path(repo_source_path).is_dir():
                print(f"Warning {repo_source_path} not a directory")
                return

            print(f"Index records from {repo_source_path}")
            os.chdir(repo_source_path)
            review_manager = colrev.review_manager.ReviewManager(
                path_str=str(repo_source_path)
            )

            check_operation = colrev.ops.check.CheckOperation(review_manager)

            if review_manager.dataset.get_repo().active_branch.name != "main":
                print(
                    f"{Colors.ORANGE}Warning: {repo_source_path} not on main branch{Colors.END}"
                )

            records_file = check_operation.review_manager.paths.records
            if not records_file.is_file():
                return
            records = check_operation.review_manager.dataset.load_records_dict()

            curation_endpoints = [
                x
                for x in check_operation.review_manager.settings.data.data_package_endpoints
                if x["endpoint"] == "colrev.colrev_curation"
            ]

            curated_fields = []
            curation_url = ""
            if curation_endpoints:
                curation_endpoint = curation_endpoints[0]
                # Set masterdata_provenace to CURATED:{url}
                curation_url = curation_endpoint["curation_url"]
                if (
                    not check_operation.review_manager.settings.is_curated_masterdata_repo()
                ):
                    # Add curation_url to curated fields (provenance)
                    curated_fields = curation_endpoint["curated_fields"]

            curated_masterdata = (
                check_operation.review_manager.settings.is_curated_masterdata_repo()
            )

            self.index_records(
                records=records,
                repo_source_path=repo_source_path,
                curated_fields=curated_fields,
                curation_url=curation_url,
                curated_masterdata=curated_masterdata,
            )

        # TypeErrors are thrown when a repo is in interactive rebase mode
        except (colrev_exceptions.CoLRevException, TypeError) as exc:
            print(exc)

    def index(self) -> None:  # pragma: no cover
        """Index all registered CoLRev projects"""

        # Note : this task takes long and does not need to run often
        session = requests_cache.CachedSession(
            str(Filepaths.PREP_REQUESTS_CACHE_FILE),
            backend="sqlite",
            expire_after=timedelta(days=30),
        )
        # Note : lambda is necessary to prevent immediate function call
        # pylint: disable=unnecessary-lambda
        Timer(0.1, lambda: session.remove_expired_responses()).start()

        if self._outlets_duplicated():
            return

        self.reinitialize_sqlite_db()

        repo_source_paths = [
            x["repo_source_path"] for x in self.environment_manager.local_repos()
        ]
        if not repo_source_paths:
            env_resources = colrev.env.resources.Resources()
            curated_resources = list(self._load_masterdata_curations().values())
            for curated_resource in curated_resources:
                print(f"Install {curated_resource}")
                env_resources.install_curated_resource(
                    curated_resource=curated_resource
                )

            repo_source_paths = [
                x["repo_source_path"] for x in self.environment_manager.local_repos()
            ]

        for repo_source_path in repo_source_paths:
            self.index_colrev_project(repo_source_path)

    def _index_tei_document(self, recs_to_index: list) -> None:
        if not self._index_tei:
            return
        for record_dict in recs_to_index:
            if not Path(record_dict.get(Fields.FILE, "NA")).is_file():
                continue

            try:
                tei_path = self._get_tei_index_file(
                    local_index_id=record_dict[LocalIndexFields.ID]
                )
                tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                if not tei_path.is_file():
                    print(f"Create tei for {record_dict[Fields.FILE]}")
                tei = colrev.env.tei_parser.TEIParser(
                    environment_manager=self.environment_manager,
                    pdf_path=Path(record_dict[Fields.FILE]),
                    tei_path=tei_path,
                )
                record_dict[LocalIndexFields.TEI] = str(tei_path)
                record_dict[Fields.FULLTEXT] = tei.get_tei_str()

            except (
                colrev_exceptions.TEIException,
                AttributeError,
                FileNotFoundError,
                colrev_exceptions.ServiceNotAvailableException,
            ):  # pragma: no cover
                pass

    def _get_tei_index_file(self, *, local_index_id: str) -> Path:
        return Filepaths.TEI_INDEX_DIR / Path(
            f"{local_index_id[:2]}/{local_index_id[2:]}.tei.xml"
        )

    def index_journal_rankings(self) -> None:
        """Indexes journal rankings in sqlite database"""

        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.env", filename=Path("journal_rankings.csv")
        )
        if filedata is not None:
            data_frame = pd.read_csv(
                io.StringIO(filedata.decode("utf-8")), encoding="utf-8"
            )
            sqlite_index_ranking = colrev.env.local_index_sqlite.SQLiteIndexRankings()
            sqlite_index_ranking.insert_df(data_frame)
