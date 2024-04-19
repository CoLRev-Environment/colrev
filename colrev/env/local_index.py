#! /usr/bin/env python
"""Indexing and retrieving records locally."""
from __future__ import annotations

import collections
import os
import sqlite3
import typing
from copy import deepcopy
from datetime import timedelta
from multiprocessing import Lock
from pathlib import Path
from threading import Timer

import git
import pandas as pd
import requests_cache
from git.exc import GitCommandError
from tqdm import tqdm

import colrev.env.environment_manager
import colrev.env.local_index_sqlite
import colrev.env.resources
import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.check
import colrev.record.record
import colrev.review_manager
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import Filepaths
from colrev.constants import LocalIndexFields
from colrev.constants import RecordState
from colrev.env.local_index_prep import prepare_record_for_indexing
from colrev.writer.write_utils import to_string


class LocalIndex:
    """The LocalIndex implements indexing and retrieval of records across projects"""

    keys_to_remove = (
        Fields.ORIGIN,
        Fields.FULLTEXT,
        Fields.GROBID_VERSION,
        Fields.SCREENING_CRITERIA,
        Fields.METADATA_SOURCE_REPOSITORY_PATHS,
        "tei_file",
    )

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

    def load_journal_rankings(self) -> None:
        """Loads journal rankings into sqlite database"""

        print("Index rankings")
        rankings_csv_path = str(Path(__file__).parents[1]) / Path(
            "env/journal_rankings.csv"
        )
        data_frame = pd.read_csv(rankings_csv_path, encoding="utf-8")
        sqlite_index_ranking = colrev.env.local_index_sqlite.SQLiteIndexRankings()
        sqlite_index_ranking.insert(data_frame)

    def search_in_database(self, journal: str) -> list:
        """Searches for journal ranking in database"""
        sqlite_index_ranking = colrev.env.local_index_sqlite.SQLiteIndexRankings()
        return sqlite_index_ranking.select(journal=journal)

    def _get_tei_index_file(self, *, paper_hash: str) -> Path:
        return Filepaths.TEI_INDEX_DIR / Path(
            f"{paper_hash[:2]}/{paper_hash[2:]}.tei.xml"
        )

    def _index_tei_document(self, recs_to_index: list) -> None:
        if not self._index_tei:
            return
        for record_dict in recs_to_index:
            if not Path(record_dict.get(Fields.FILE, "NA")).is_file():
                continue

            try:
                paper_hash = record_dict[LocalIndexFields.ID]
                tei_path = self._get_tei_index_file(paper_hash=paper_hash)
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

    def get_fields_to_remove(self, record_dict: dict) -> list:
        """Compares the record to available toc items and
        returns fields to remove (if any)"""
        # pylint: disable=too-many-return-statements

        fields_to_remove: typing.List[str] = []
        if (
            Fields.JOURNAL not in record_dict
            and record_dict[Fields.ENTRYTYPE] != ENTRYTYPES.ARTICLE
        ):
            return fields_to_remove

        internal_record_dict = deepcopy(record_dict)

        if all(
            x in internal_record_dict.keys() for x in [Fields.VOLUME, Fields.NUMBER]
        ):
            try:
                toc_key_full = colrev.record.record.Record(
                    internal_record_dict
                ).get_toc_key()

                if self._toc_exists(toc_key_full):
                    return fields_to_remove
            except colrev_exceptions.NotTOCIdentifiableException:
                return fields_to_remove
            wo_nr = deepcopy(internal_record_dict)
            del wo_nr[Fields.NUMBER]
            toc_key_wo_nr = colrev.record.record.Record(wo_nr).get_toc_key()

            if toc_key_wo_nr != "NA":
                if self._toc_exists(toc_key_wo_nr):
                    fields_to_remove.append(Fields.NUMBER)
                    return fields_to_remove

            wo_vol = deepcopy(internal_record_dict)
            del wo_vol[Fields.VOLUME]
            toc_key_wo_vol = colrev.record.record.Record(wo_vol).get_toc_key()
            if toc_key_wo_vol != "NA":
                if self._toc_exists(toc_key_wo_vol):
                    fields_to_remove.append(Fields.VOLUME)
                    return fields_to_remove

            wo_vol_nr = deepcopy(internal_record_dict)
            del wo_vol_nr[Fields.VOLUME]
            del wo_vol_nr[Fields.NUMBER]
            toc_key_wo_vol_nr = colrev.record.record.Record(wo_vol_nr).get_toc_key()
            if toc_key_wo_vol_nr != "NA":
                if self._toc_exists(toc_key_wo_vol_nr):
                    fields_to_remove.append(Fields.NUMBER)
                    fields_to_remove.append(Fields.VOLUME)
                    return fields_to_remove

        return fields_to_remove

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

    def _get_record_from_row(self, row: dict) -> dict:
        records_dict = colrev.loader.load_utils.loads(
            load_string=row[LocalIndexFields.BIBTEX],
            implementation="bib",
            unique_id_field="ID",
        )
        retrieved_record = list(records_dict.values())[0]
        return retrieved_record

    def _retrieve_based_on_colrev_id(
        self, cids_to_retrieve: list
    ) -> colrev.record.record.Record:

        sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
        for cid_to_retrieve in cids_to_retrieve:
            try:
                retrieved_record = sqlite_index_record.get(
                    key=Fields.COLREV_ID, value=cid_to_retrieve
                )
                return colrev.record.record.Record(retrieved_record)

            except colrev_exceptions.RecordNotInIndexException:
                continue  # continue with the next cid_to_retrieve

        raise colrev_exceptions.RecordNotInIndexException()

    def _retrieve_from_github_curation(
        self, record_dict: dict
    ) -> colrev.record.record.Record:  # pragma: no cover
        ret = {}
        try:
            gh_url, record_id = record_dict[Fields.CURATION_ID].split("#")
            temp_path = Path.home().joinpath("colrev").joinpath("test")
            temp_path.mkdir(exist_ok=True, parents=True)
            target_path = Path(temp_path) / Path(gh_url.split("/")[-1])
            if not target_path.is_dir():
                git.Repo.clone_from(
                    gh_url,  # .replace("https://github.com/", "git@github.com:") + ".git",
                    str(target_path),
                    depth=1,
                )
            ret = colrev.loader.load_utils.load(
                filename=target_path / Filepaths.RECORDS_FILE,
            )

        except GitCommandError:
            pass

        if record_id not in ret:
            raise colrev_exceptions.RecordNotInIndexException

        ret[record_id][Fields.CURATION_ID] = record_dict[Fields.CURATION_ID]
        return colrev.record.record.Record(ret[record_id])

    def _retrieve_from_record_index(
        self, record_dict: dict
    ) -> colrev.record.record.Record:

        record = colrev.record.record.Record(record_dict)
        cids_to_retrieve = [record.get_colrev_id()]
        retrieved_record = self._retrieve_based_on_colrev_id(cids_to_retrieve)
        if retrieved_record.data[Fields.ENTRYTYPE] != record.data[Fields.ENTRYTYPE]:
            if record_dict.get(Fields.CURATION_ID, "NA").startswith(
                "https://github.com/"
            ):
                return self._retrieve_from_github_curation(record_dict=record_dict)
            raise colrev_exceptions.RecordNotInIndexException
        return retrieved_record

    def _prepare_record_for_return(
        self,
        record_dict: dict,
        *,
        include_file: bool = False,
        include_colrev_ids: bool = False,
    ) -> colrev.record.record.Record:
        """Prepare a record for return (from local index)"""

        # Note : remove fulltext before parsing because it raises errors
        fulltext_backup = record_dict.get(Fields.FULLTEXT, "NA")

        for key in self.keys_to_remove:
            record_dict.pop(key, None)

        # Note: record['file'] should be an absolute path by definition
        # when stored in the LocalIndex
        if Fields.FILE in record_dict and not Path(record_dict[Fields.FILE]).is_file():
            del record_dict[Fields.FILE]

        if not include_colrev_ids and Fields.COLREV_ID in record_dict:
            del record_dict[Fields.COLREV_ID]

        if include_file:
            if fulltext_backup != "NA":
                record_dict[Fields.FULLTEXT] = fulltext_backup
        else:
            colrev.record.record.Record(record_dict).remove_field(key=Fields.FILE)
            colrev.record.record.Record(record_dict).remove_field(key=Fields.PDF_ID)

        record = colrev.record.record.Record(record_dict)
        record.set_status(RecordState.md_prepared)

        if record.masterdata_is_curated():
            identifier_string = (
                record.get_field_provenance_source(FieldValues.CURATED)
                + f"#{record_dict[Fields.ID]}"
            )
            record_dict[Fields.CURATION_ID] = identifier_string

        return record

    def search(self, query: str) -> list[colrev.record.record.Record]:
        """Run a search for records"""

        try:
            self.thread_lock.acquire(timeout=60)
            sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
            records_to_return = []
            for record_dict in sqlite_index_record.search(query=query):
                record = self._prepare_record_for_return(
                    record_dict, include_file=False
                )
                records_to_return.append(record)

        except sqlite3.OperationalError as exc:  # pragma: no cover
            print(exc)
        finally:
            self.thread_lock.release()

        return records_to_return

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

            records_file = check_operation.review_manager.get_path(
                Filepaths.RECORDS_FILE
            )
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

    def reinitialize_sqlite_db(self) -> None:
        """Reinitialize the SQLITE database ()"""

        Filepaths.LOCAL_INDEX_SQLITE_FILE.unlink(missing_ok=True)
        colrev.env.local_index_sqlite.SQLiteIndexRecord(reinitialize=True)
        colrev.env.local_index_sqlite.SQLiteIndexTOC(reinitialize=True)

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

    def get_year_from_toc(self, record_dict: dict) -> str:
        """Determine the year of a paper based on its table-of-content (journal-volume-number)"""

        try:
            sqlite_index_toc = colrev.env.local_index_sqlite.SQLiteIndexTOC()
            toc_key = colrev.record.record.Record(record_dict).get_toc_key()
            toc_items = []
            if self._toc_exists(toc_key):
                res = sqlite_index_toc.get(key=LocalIndexFields.TOC_KEY, value=toc_key)
                toc_items = res.get("colrev_ids", "").split(";")  # type: ignore

            if not toc_items:
                raise colrev_exceptions.TOCNotAvailableException()

            toc_records_colrev_id = toc_items[0]
            sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
            record_dict = sqlite_index_record.get(
                key=Fields.COLREV_ID, value=toc_records_colrev_id
            )

            year = record_dict.get(Fields.YEAR, "NA")
            return year

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            colrev_exceptions.NotTOCIdentifiableException,
            colrev_exceptions.RecordNotInIndexException,
        ) as exc:
            raise colrev_exceptions.TOCNotAvailableException() from exc

    def _toc_exists(self, toc_item: str) -> bool:
        try:
            self.thread_lock.acquire(timeout=60)
            sqlite_index_toc = colrev.env.local_index_sqlite.SQLiteIndexTOC()
            return sqlite_index_toc.exists(toc_item)
        except sqlite3.OperationalError:  # pragma: no cover
            pass  # return False
        except AttributeError:  # pragma: no cover
            # ie. no sqlite database available
            pass  # return False
        finally:
            self.thread_lock.release()
        return False

    def _get_toc_items(self, toc_key: str, *, search_across_tocs: bool) -> list:
        sqlite_index_toc = colrev.env.local_index_sqlite.SQLiteIndexTOC()
        toc_items = []
        if self._toc_exists(toc_key):
            res = sqlite_index_toc.get(key=LocalIndexFields.TOC_KEY, value=toc_key)
            toc_items = res.get("colrev_ids", "").split(";")  # type: ignore
        else:
            if not search_across_tocs:
                raise colrev_exceptions.RecordNotInIndexException()

        if not toc_items and search_across_tocs:
            try:
                partial_toc_key = toc_key.replace("|-", "")
                retrieved_tocs = sqlite_index_toc.get_toc_items(
                    (f"{LocalIndexFields.TOC_KEY} LIKE ?", [f"{partial_toc_key}%"])
                )
                toc_items = [x["colrev_ids"].split(";") for x in retrieved_tocs]
                toc_items = [item for sublist in toc_items for item in sublist]

            except (
                colrev_exceptions.NotTOCIdentifiableException,
                KeyError,
            ) as exc:
                raise colrev_exceptions.RecordNotInIndexException() from exc

        if not toc_items:
            raise colrev_exceptions.RecordNotInIndexException()
        return toc_items

    def retrieve_from_toc(
        self,
        record: colrev.record.record.Record,
        *,
        include_file: bool = False,
        search_across_tocs: bool = False,
    ) -> colrev.record.record.Record:
        """Retrieve a record from the toc (table-of-contents)"""

        sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
        try:
            # Note: in NotTOCIdentifiableException cases, we still need a toc_key.
            # to accomplish this, the get_toc_key() may acced an "accept_incomplete" flag
            toc_key = record.get_toc_key()
            toc_items = self._get_toc_items(
                toc_key, search_across_tocs=search_across_tocs
            )
            for toc_records_colrev_id in toc_items:
                record_dict = sqlite_index_record.get(
                    key=Fields.COLREV_ID, value=toc_records_colrev_id
                )

                if not colrev.record.record_similarity.matches(
                    record, colrev.record.record.Record(record_dict)
                ):
                    continue

                return self._prepare_record_for_return(
                    record_dict, include_file=include_file
                )
            raise colrev_exceptions.RecordNotInTOCException(
                record_id=record.data[Fields.ID], toc_key=toc_key
            )

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            colrev_exceptions.NotTOCIdentifiableException,
        ):
            pass

        raise colrev_exceptions.RecordNotInIndexException()

    def retrieve_based_on_colrev_pdf_id(
        self, *, colrev_pdf_id: str
    ) -> colrev.record.record.Record:
        """
        Convenience function to retrieve the indexed record_dict metadata
        based on a colrev_pdf_id
        """

        sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
        record_dict = sqlite_index_record.get(key=Fields.PDF_ID, value=colrev_pdf_id)
        record_to_import = self._prepare_record_for_return(
            record_dict, include_file=True
        )
        record_to_import.data.pop(Fields.FILE, None)
        return record_to_import

    def retrieve(
        self,
        record_dict: dict,
        *,
        include_file: bool = False,
        include_colrev_ids: bool = False,
    ) -> colrev.record.record.Record:
        """
        Convenience function to retrieve the indexed record_dict metadata
        based on another record_dict
        """

        # To avoid modifications to the original record
        record_dict = deepcopy(record_dict)

        # 1. Try the record index
        try:
            retrieved_record = self._retrieve_from_record_index(record_dict)
            retrieved_record_dict = retrieved_record.data
        except (
            colrev_exceptions.RecordNotInIndexException,
            colrev_exceptions.NotEnoughDataToIdentifyException,
        ) as exc:
            if self.verbose_mode:
                print(exc)
                print(f"{record_dict[Fields.ID]} - no exact match")

            # 2. Try using global-ids
            retrieved_record_dict = {}
            sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
            remove_colrev_id = False
            if Fields.COLREV_ID not in record_dict:
                try:
                    record_dict[Fields.COLREV_ID] = colrev.record.record.Record(
                        record_dict
                    ).get_colrev_id()
                    remove_colrev_id = True
                except colrev_exceptions.NotEnoughDataToIdentifyException:
                    pass
            for key, value in record_dict.items():
                if (
                    key
                    not in colrev.env.local_index_sqlite.SQLiteIndexRecord.GLOBAL_KEYS
                    or Fields.ID == key
                ):
                    continue

                retrieved_record_dict = sqlite_index_record.get(key=key, value=value)

                if key in retrieved_record_dict:
                    if retrieved_record_dict[key] == value:
                        break
                retrieved_record_dict = {}
            if remove_colrev_id:
                del record_dict[Fields.COLREV_ID]

            if not retrieved_record_dict:
                raise colrev_exceptions.RecordNotInIndexException(
                    record_dict.get(Fields.ID, "no-key")
                )

        return self._prepare_record_for_return(
            retrieved_record_dict,
            include_file=include_file,
            include_colrev_ids=include_colrev_ids,
        )
