#! /usr/bin/env python
"""Indexing and retrieving records locally."""
from __future__ import annotations

import collections
import hashlib
import json
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
from rapidfuzz import fuzz
from tqdm import tqdm

import colrev.constants as c
import colrev.env.environment_manager
import colrev.env.resources
import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record
import colrev.review_manager
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import Filepaths
from colrev.constants import RecordState
from colrev.writer.write_utils import to_string

# import binascii

# pylint: disable=too-many-lines


class LocalIndex:
    """The LocalIndex implements indexing and retrieval of records across projects"""

    sqlite_connection: sqlite3.Connection
    request_timeout = 90
    _sqlite_available = True

    global_keys = [
        Fields.DOI,
        Fields.DBLP_KEY,
        "colrev_pdf_id",
        Fields.URL,
        "colrev_id",
    ]

    RECORDS_INDEX_KEYS = [
        "id",
        "colrev_id",
        "citation_key",
        Fields.TITLE,
        Fields.ABSTRACT,
        Fields.FILE,
        "tei",
        Fields.FULLTEXT,
        Fields.URL,
        Fields.DOI,
        "dblp_key",  # Note : no dots in key names
        "colrev_pdf_id",
        "bibtex",
        "layered_fields",
        # Fields.CURATION_ID
    ]

    # Note: we need the local_curated_metadata field for is_duplicate()

    # Note : records are indexed by id = hash(colrev_id)
    # to ensure that the indexing-ids do not exceed limits
    # such as the opensearch limit of 512 bytes.
    # This enables efficient retrieval based on id=hash(colrev_id)
    # but also search-based retrieval using only colrev_ids

    RECORD_INDEX = "record_index"
    TOC_INDEX = "toc_index"
    # AUTHOR_INDEX = "author_index"
    # AUTHOR_RECORD_INDEX = "author_record_index"
    # CITATIONS_INDEX = "citations_index"

    UPDATE_LAYERD_FIELDS_QUERY = """
            UPDATE record_index SET
            layered_fields=?
            WHERE id=?"""

    SELECT_LAYERD_FIELDS_QUERY = "SELECT layered_fields FROM record_index WHERE id=?"

    SELECT_ALL_QUERIES = {
        TOC_INDEX: "SELECT * FROM toc_index WHERE",
        RECORD_INDEX: "SELECT * FROM record_index WHERE",
    }

    SELECT_KEY_QUERIES = {
        (RECORD_INDEX, "id"): "SELECT * FROM record_index WHERE id=?",
        (TOC_INDEX, "toc_key"): "SELECT * FROM toc_index WHERE toc_key=?",
        (RECORD_INDEX, "colrev_id"): "SELECT * FROM record_index WHERE colrev_id=?",
        (RECORD_INDEX, Fields.DOI): "SELECT * FROM record_index where doi=?",
        (
            RECORD_INDEX,
            Fields.DBLP_KEY,
        ): "SELECT * FROM record_index WHERE dblp_key=?",
        (
            RECORD_INDEX,
            "colrev_pdf_id",
        ): "SELECT * FROM record_index WHERE colrev_pdf_id=?",
        (RECORD_INDEX, Fields.URL): "SELECT * FROM record_index WHERE url=?",
    }

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

    def _get_sqlite_cursor(self, *, init: bool = False) -> sqlite3.Cursor:
        if init:
            Filepaths.LOCAL_INDEX_SQLITE_FILE.unlink(missing_ok=True)

        self.sqlite_connection = sqlite3.connect(
            str(Filepaths.LOCAL_INDEX_SQLITE_FILE), timeout=90
        )
        self.sqlite_connection.row_factory = self._dict_factory
        return self.sqlite_connection.cursor()

    def load_journal_rankings(self) -> None:
        """Loads journal rankings into sqlite database"""

        print("Index rankings")

        rankings_csv_path = str(Path(__file__).parents[1]) / Path(
            "env/journal_rankings.csv"
        )
        conn = sqlite3.connect(str(Filepaths.LOCAL_INDEX_SQLITE_FILE))
        data_frame = pd.read_csv(rankings_csv_path, encoding="utf-8")
        data_frame.to_sql("rankings", conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()

    def search_in_database(self, journal: typing.Optional[typing.Any]) -> list:
        """Searches for journalranking in database"""
        cur = self._get_sqlite_cursor(init=False)
        cur.execute(
            "SELECT * FROM rankings WHERE journal_name = ?",
            (journal,),
        )
        rankings = cur.fetchall()
        return rankings

    def _dict_factory(self, cursor: sqlite3.Cursor, row: dict) -> dict:
        ret_dict = {}
        for idx, col in enumerate(cursor.description):
            ret_dict[col[0]] = row[idx]
        return ret_dict

    def _get_record_hash(self, *, record_dict: dict) -> str:
        # Note : may raise NotEnoughDataToIdentifyException
        string_to_hash = colrev.record.record.Record(record_dict).create_colrev_id()
        return hashlib.sha256(string_to_hash.encode("utf-8")).hexdigest()

    # def _increment_hash(self, *, paper_hash: str) -> str:
    #     plaintext = binascii.unhexlify(paper_hash)
    #     # also, we'll want to know our length later on
    #     plaintext_length = len(plaintext)
    #     plaintext_number = int.from_bytes(plaintext, "big")

    #     # recommendation: do not increment by 1
    #     plaintext_number += 10
    #     max_len_sha256 = 2**256
    #     plaintext_number = plaintext_number % max_len_sha256

    #     new_plaintext = plaintext_number.to_bytes(plaintext_length, "big")
    #     new_hex = binascii.hexlify(new_plaintext)
    #     # print(new_hex.decode("utf-8"))

    #     return new_hex.decode("utf-8")

    def _get_tei_index_file(self, *, paper_hash: str) -> Path:
        return Filepaths.TEI_INDEX_DIR / Path(
            f"{paper_hash[:2]}/{paper_hash[2:]}.tei.xml"
        )

    # def _index_author(
    #     self, tei: colrev.env.tei_parser.TEIParser, record_dict: dict
    # ) -> None:
    #     print("index_author currently not implemented")
    # author_details = tei.get_author_details()
    # # Iterate over curated metadata and enrich it based on TEI (may vary in quality)
    # for author in record_dict.get(Fields.AUTHOR, "").split(" and "):
    #     if "," not in author:
    #         continue
    #     author_dict = {}
    #     author_dict["surname"] = author.split(", ")[0]
    #     author_dict["forename"] = author.split(", ")[1]
    #     for author_detail in author_details:
    #         if author_dict["surname"] == author_detail["surname"]:
    #             # Add complementary details
    #             author_dict = {**author_dict, **author_detail}
    #     self.open_search.index(index=self.AUTHOR_INDEX, body=author_dict)

    def _index_tei_document(self, recs_to_index: list) -> None:
        if not self._index_tei:
            return
        for record_dict in recs_to_index:
            if not Path(record_dict.get(Fields.FILE, "NA")).is_file():
                continue

            try:
                paper_hash = record_dict["id"]
                tei_path = self._get_tei_index_file(paper_hash=paper_hash)
                tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                if not tei_path.is_file():
                    print(f"Create tei for {record_dict['file']}")
                tei = colrev.env.tei_parser.TEIParser(
                    environment_manager=self.environment_manager,
                    pdf_path=Path(record_dict[Fields.FILE]),
                    tei_path=tei_path,
                )

                record_dict["tei"] = str(tei_path)
                record_dict[Fields.FULLTEXT] = tei.get_tei_str()

                # self._index_author(tei=tei, record_dict=record_dict)

            except (
                colrev_exceptions.TEIException,
                AttributeError,
                FileNotFoundError,
                colrev_exceptions.ServiceNotAvailableException,
            ):  # pragma: no cover
                pass

    def _amend_record(
        self, *, cur: sqlite3.Cursor, item: dict, curated_fields: list
    ) -> None:
        """Adds layered fields to amend existing records"""

        record_dict = self._get_record_from_row(item)

        layered_fields = []
        cur.execute(self.SELECT_LAYERD_FIELDS_QUERY, (item["id"],))
        row = cur.fetchone()
        if row["layered_fields"]:
            layered_fields = json.loads(row["layered_fields"])
        for curated_field in curated_fields:
            if curated_field not in record_dict:
                continue
            source = record_dict[Fields.D_PROV][curated_field]["source"]
            layered_fields.append(
                {
                    "key": curated_field,
                    "value": record_dict[curated_field],
                    "source": source,
                }
            )

        cur.execute(
            self.UPDATE_LAYERD_FIELDS_QUERY,
            (json.dumps(layered_fields), item["id"]),
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
                    data=internal_record_dict
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

    def _add_index_toc(self, toc_to_index: dict) -> None:
        list_to_add = list((k, v) for k, v in toc_to_index.items() if v != "DROPPED")
        cur = self.sqlite_connection.cursor()
        try:
            cur.executemany(f"INSERT INTO {self.TOC_INDEX} VALUES(?, ?)", list_to_add)
        except sqlite3.IntegrityError as exc:  # pragma: no cover
            if self.verbose_mode:
                print(exc)
        finally:
            if self.sqlite_connection:
                self.sqlite_connection.commit()

    def _add_index_records(self, *, recs_to_index: list, curated_fields: list) -> None:
        list_to_add = [
            {k: v for k, v in el.items() if k in self.RECORDS_INDEX_KEYS}
            for el in recs_to_index
        ]

        cur = self.sqlite_connection.cursor()
        for item in list_to_add:
            while True:
                for records_index_required_key in self.RECORDS_INDEX_KEYS:
                    if records_index_required_key not in item:
                        item[records_index_required_key] = ""
                if item["id"] == "":
                    print("NO ID IN RECORD")
                    break
                try:
                    cur.execute(
                        f"INSERT INTO {self.RECORD_INDEX} "
                        f"VALUES(:{', :'.join(self.RECORDS_INDEX_KEYS)})",
                        item,
                    )
                    break
                except sqlite3.IntegrityError:
                    if not curated_fields:
                        break
                    try:
                        stored_record = self._get_item_from_index(
                            index_name=self.RECORD_INDEX,
                            key=Fields.COLREV_ID,
                            value=item["colrev_id"],
                            cursor=cur,
                        )
                        stored_colrev_id = colrev.record.record.Record(
                            data=stored_record
                        ).create_colrev_id()

                        if stored_colrev_id != item["colrev_id"]:  # pragma: no cover
                            print("Collisions (TODO):")
                            print(stored_colrev_id)
                            print(item["colrev_id"])

                            # print(
                            #     [
                            #         {k: v for k, v in x.items() if k != "bibtex"}
                            #         for x in stored_record
                            #     ]
                            # )
                            # print(item)
                            # to handle the collision:
                            # print(f"Collision: {paper_hash}")
                            # print(cid_to_index)
                            # print(saved_record_cid)
                            # print(saved_record)
                            # paper_hash = self._increment_hash(paper_hash=paper_hash)
                            # item["id"] = paper_hash
                            # continue in while-loop/try to insert...
                            # pylint: disable=raise-missing-from
                            raise NotImplementedError

                        self._amend_record(
                            cur=cur, item=item, curated_fields=curated_fields
                        )
                        break
                    except (
                        colrev_exceptions.RecordNotInIndexException
                    ):  # pragma: no cover
                        break

        if self.sqlite_connection:
            self.sqlite_connection.commit()

    def _get_record_from_row(self, row: dict) -> dict:

        records_dict = colrev.loader.load_utils.loads(
            load_string=row["bibtex"],
            implementation="bib",
            unique_id_field="ID",
        )

        retrieved_record = list(records_dict.values())[0]

        # append layered fields
        if row["layered_fields"]:
            layered_fields = json.loads(row["layered_fields"])
            for layered_field in layered_fields:
                retrieved_record[layered_field["key"]] = layered_field["value"]
                if Fields.D_PROV not in retrieved_record:
                    retrieved_record[Fields.D_PROV] = {}
                retrieved_record[Fields.D_PROV][layered_field["key"]] = {
                    "source": layered_field["source"],
                    "note": "",
                }
        return retrieved_record

    def _retrieve_based_on_colrev_id(
        self, *, cids_to_retrieve: list
    ) -> colrev.record.record.Record:
        for cid_to_retrieve in cids_to_retrieve:
            try:
                retrieved_record = self._get_item_from_index(
                    index_name=self.RECORD_INDEX,
                    key=Fields.COLREV_ID,
                    value=cid_to_retrieve,
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
                filename=target_path / Path("data/records.bib"),
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

        if not self._sqlite_available:  # pragma: no cover
            if record_dict.get(Fields.CURATION_ID, "NA").startswith(
                "https://github.com/"
            ):
                return self._retrieve_from_github_curation(record_dict=record_dict)
            raise colrev_exceptions.RecordNotInIndexException

        if Fields.COLREV_ID in record.data:
            cid_to_retrieve = record.get_colrev_id()
        else:
            cid_to_retrieve = [record.create_colrev_id(assume_complete=True)]

        retrieved_record = self._retrieve_based_on_colrev_id(
            cids_to_retrieve=cid_to_retrieve
        )
        if retrieved_record.data[Fields.ENTRYTYPE] != record.data[Fields.ENTRYTYPE]:
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

        # pylint: disable=too-many-branches

        # Note : remove fulltext before parsing because it raises errors
        fulltext_backup = record_dict.get(Fields.FULLTEXT, "NA")

        keys_to_remove = (
            Fields.ORIGIN,
            Fields.FULLTEXT,
            "tei_file",
            Fields.GROBID_VERSION,
            Fields.SCREENING_CRITERIA,
            "local_curated_metadata",
            "metadata_source_repository_paths",
        )

        for key in keys_to_remove:
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
            record_dict.pop(Fields.FILE, None)
            if Fields.FILE in record_dict.get(Fields.D_PROV, {}):
                del record_dict[Fields.D_PROV][Fields.FILE]
            record_dict.pop("colrev_pdf_id", None)
            if "colrev_pdf_id" in record_dict.get(Fields.D_PROV, {}):
                del record_dict[Fields.D_PROV]["colrev_pdf_id"]

        record = colrev.record.record.Record(record_dict)
        record.set_status(RecordState.md_prepared)

        if record.masterdata_is_curated():
            identifier_string = (
                record.get_masterdata_provenance_source(FieldValues.CURATED)
                + "#"
                + record_dict[Fields.ID]
            )
            record_dict[Fields.CURATION_ID] = identifier_string

        return record

    def search(self, query: str) -> list[colrev.record.record.Record]:
        """Run a search for records"""

        records_to_return = []
        try:
            self.thread_lock.acquire(timeout=60)
            cur = self._get_sqlite_cursor()
            selected_row = None
            print(f"{self.SELECT_ALL_QUERIES[self.RECORD_INDEX] } {query}")
            cur.execute(f"{self.SELECT_ALL_QUERIES[self.RECORD_INDEX] } {query}")
            for row in cur.fetchall():
                selected_row = row
                retrieved_record_dict = self._get_record_from_row(selected_row)
                retrieved_record = self._prepare_record_for_return(
                    retrieved_record_dict, include_file=False
                )
                retrieved_record.align_provenance()
                records_to_return.append(retrieved_record)
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

    def _apply_status_requirements(self, record_dict: dict) -> None:
        if Fields.STATUS not in record_dict:
            raise colrev_exceptions.RecordNotIndexableException()

        # It is important to exclude md_prepared if the LocalIndex
        # is used to dissociate duplicates
        if record_dict[Fields.STATUS] in RecordState.get_non_processed_states():
            raise colrev_exceptions.RecordNotIndexableException()

        # Some prescreen_excluded records are not prepared
        if record_dict[Fields.STATUS] == RecordState.rev_prescreen_excluded:
            raise colrev_exceptions.RecordNotIndexableException()

    def _remove_fields(self, record_dict: dict) -> None:
        # Do not cover deprecated fields
        for deprecated_field in ["pdf_hash"]:
            if deprecated_field in record_dict:
                print(f"Removing deprecated field: {deprecated_field}")
                del record_dict[deprecated_field]

        for field in ["note", "link"]:
            record_dict.pop(field, None)

        if Fields.SCREENING_CRITERIA in record_dict:
            del record_dict[Fields.SCREENING_CRITERIA]
        # Note: if the colrev_pdf_id has not been checked,
        # we cannot use it for retrieval or preparation.
        post_pdf_prepared_states = RecordState.get_post_x_states(
            state=RecordState.pdf_prepared
        )
        if record_dict[Fields.STATUS] not in post_pdf_prepared_states:
            record_dict.pop("colrev_pdf_id", None)

        # Note : numbers of citations change regularly.
        # They should be retrieved from sources like crossref/doi.org
        record_dict.pop(Fields.CITED_BY, None)
        if record_dict.get(Fields.YEAR, "NA").isdigit():
            record_dict[Fields.YEAR] = int(record_dict[Fields.YEAR])
        else:
            raise colrev_exceptions.RecordNotIndexableException()

        if Fields.LANGUAGE in record_dict and len(record_dict[Fields.LANGUAGE]) != 3:
            print(f"Language not in ISO 639-3 format: {record_dict[Fields.LANGUAGE]}")
            del record_dict[Fields.LANGUAGE]

    def _adjust_provenance_for_indexing(self, record_dict: dict) -> None:
        # Provenance should point to the original repository path.
        # If the provenance/source was example.bib (and the record is amended during indexing)
        # we wouldn't know where the example.bib belongs to.
        record = colrev.record.record.Record(record_dict)
        # Make sure that we don't add provenance information without corresponding fields
        record.align_provenance()
        for key in list(record.data.keys()):
            if not record.masterdata_is_curated():
                record.add_masterdata_provenance(
                    key=key, source=record_dict["metadata_source_repository_paths"]
                )
            elif (
                key
                not in c.FieldSet.IDENTIFYING_FIELD_KEYS
                + c.FieldSet.PROVENANCE_KEYS
                + [
                    Fields.ID,
                    Fields.ENTRYTYPE,
                    "local_curated_metadata",
                    "metadata_source_repository_paths",
                ]
            ):
                if key not in record.data.get(Fields.D_PROV, {}):
                    record.add_data_provenance(
                        key=key,
                        source=record_dict["metadata_source_repository_paths"],
                    )
                elif (
                    FieldValues.CURATED not in record.data[Fields.D_PROV][key]["source"]
                ):
                    record.add_data_provenance(
                        key=key,
                        source=record_dict["metadata_source_repository_paths"],
                    )

        record_dict = record.get_data()

    def _prep_fields_for_indexing(self, record_dict: dict) -> None:
        # Note : this is the first run, no need to split/list
        if "colrev/curated_metadata" in record_dict["metadata_source_repository_paths"]:
            # Note : local_curated_metadata is important to identify non-duplicates
            # between curated_metadata_repositories
            record_dict[Fields.LOCAL_CURATED_METADATA] = "yes"

        # Note : file paths should be absolute when added to the LocalIndex
        if Fields.FILE in record_dict:
            pdf_path = Path(record_dict[Fields.FILE])
            if pdf_path.is_file():
                record_dict[Fields.FILE] = str(pdf_path)
            else:
                del record_dict[Fields.FILE]

        record_dict.pop(Fields.ORIGIN, None)

    def _prepare_record_for_indexing(self, record_dict: dict) -> dict:
        self._apply_status_requirements(record_dict)
        self._remove_fields(record_dict)
        self._prep_fields_for_indexing(record_dict)
        self._adjust_provenance_for_indexing(record_dict)

        return record_dict

    def _get_index_record(self, record_dict: dict) -> dict:
        try:
            record_dict = self._prepare_record_for_indexing(record_dict)
            cid_to_index = colrev.record.record.Record(record_dict).create_colrev_id()
            record_dict[Fields.COLREV_ID] = cid_to_index
            record_dict["citation_key"] = record_dict[Fields.ID]
            record_dict["id"] = self._get_record_hash(record_dict=record_dict)
        except colrev_exceptions.NotEnoughDataToIdentifyException as exc:
            missing_key = ""
            if exc.missing_fields is not None:
                missing_key = ",".join(exc.missing_fields)
            raise colrev_exceptions.RecordNotIndexableException(
                missing_key=missing_key
            ) from exc

        return record_dict

    def _update_toc_index(
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
            colrev_id = colrev.record.record.Record(
                copy_for_toc_index
            ).create_colrev_id(assume_complete=True)
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
                # Add metadata_source_repository_paths : list of repositories from which
                # the record was integrated. Important for is_duplicate(...)
                record_dict.update(
                    metadata_source_repository_paths=str(repo_source_path)
                )

                if curated_fields:
                    for curated_field in curated_fields:
                        colrev.record.record.Record(record_dict).add_data_provenance(
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
                record_dict["bibtex"] = to_string(
                    records_dict={record_dict[Fields.ID]: record_dict},
                    implementation="bib",
                )
                record_dict = self._get_index_record(record_dict)
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
                self._update_toc_index(
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
            self._add_index_toc(toc_to_index)

    def _load_masterdata_curations(self) -> dict:  # pragma: no cover
        # Note : the following should be replaced by heuristics
        # based on the data (between colrev load and prep)
        masterdata_curations = {}
        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("env/masterdata_curations.csv")
        )

        if filedata:
            for masterdata_curation in filedata.decode("utf-8").splitlines():
                masterdata_curations[masterdata_curation.lower()] = (
                    masterdata_curation.lower()
                )

        return masterdata_curations

    def reinitialize_sqlite_db(self) -> None:
        """Reinitialize the SQLITE database ()"""
        print(f"Reinitialize {self.RECORD_INDEX} and {self.TOC_INDEX}")
        # Note : the tei-directory should be removed manually.

        cur = self._get_sqlite_cursor(init=True)
        cur.execute(f"drop table if exists {self.RECORD_INDEX}")
        cur.execute(
            f"CREATE TABLE {self.RECORD_INDEX}(id TEXT PRIMARY KEY, "
            + ",".join(self.RECORDS_INDEX_KEYS[1:])
            + ")"
        )
        cur.execute(f"drop table if exists {self.TOC_INDEX}")
        cur.execute(
            f"CREATE TABLE {self.TOC_INDEX}(toc_key TEXT PRIMARY KEY, colrev_ids)"
        )
        if self.sqlite_connection:
            self.sqlite_connection.commit()

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

            check_operation = colrev.process.operation.CheckOperation(review_manager)

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
                    # Curated fields/layered_fields only for non-masterdata-curated repos
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

        except colrev_exceptions.CoLRevException as exc:
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

    def get_year_from_toc(self, record_dict: dict) -> str:
        """Determine the year of a paper based on its table-of-content (journal-volume-number)"""

        try:
            toc_key = colrev.record.record.Record(record_dict).get_toc_key()
            toc_items = []
            if self._toc_exists(toc_key):
                res = self._get_item_from_index(
                    index_name=self.TOC_INDEX, key="toc_key", value=toc_key
                )
                toc_items = res.get("colrev_ids", "").split(";")  # type: ignore

            if not toc_items:
                raise colrev_exceptions.TOCNotAvailableException()

            toc_records_colrev_id = toc_items[0]

            record_dict = self._get_item_from_index(
                index_name=self.RECORD_INDEX,
                key="colrev_id",
                value=toc_records_colrev_id,
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
            cur = self._get_sqlite_cursor()
            cur.execute(
                self.SELECT_KEY_QUERIES[(self.TOC_INDEX, "toc_key")], (toc_item,)
            )
            selected_row = cur.fetchone()
            self.thread_lock.release()
            if not selected_row:
                return False
            return True
        except sqlite3.OperationalError:  # pragma: no cover
            self.thread_lock.release()
        except AttributeError:  # pragma: no cover
            # ie. no sqlite database available
            return False
        return False

    def _get_toc_items_for_toc_retrieval(
        self, toc_key: str, *, search_across_tocs: bool
    ) -> list:
        toc_items = []

        if self._toc_exists(toc_key):
            res = self._get_item_from_index(
                index_name=self.TOC_INDEX, key="toc_key", value=toc_key
            )
            toc_items = res.get("colrev_ids", "").split(";")  # type: ignore
        else:
            if not search_across_tocs:
                raise colrev_exceptions.RecordNotInIndexException()

        if not toc_items and search_across_tocs:
            try:
                partial_toc_key = toc_key.replace("|-", "")
                retrieved_tocs = self._get_items_from_index(
                    ("toc_key LIKE ?", [f"{partial_toc_key}%"]),
                    index_name=self.TOC_INDEX,
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
        similarity_threshold: float,
        include_file: bool = False,
        search_across_tocs: bool = False,
    ) -> colrev.record.record.Record:
        """Retrieve a record from the toc (table-of-contents)"""

        try:
            # Note: in NotTOCIdentifiableException cases, we still need a toc_key.
            # to accomplish this, the get_toc_key() may acced an "accept_incomplete" flag
            # try:
            toc_key = record.get_toc_key()
            # except colrev_exceptions.NotTOCIdentifiableException as exc:
            #     if not search_across_tocs:
            #         raise colrev_exceptions.RecordNotInIndexException() from exc

            toc_items = self._get_toc_items_for_toc_retrieval(
                toc_key, search_across_tocs=search_across_tocs
            )

            if search_across_tocs:
                record_colrev_id = record.create_colrev_id(assume_complete=True)
            else:
                record_colrev_id = record.create_colrev_id()

            sim_list = []
            for toc_records_colrev_id in toc_items:
                # Note : using a simpler similarity measure
                # because the publication outlet parameters are already identical
                sim_value = fuzz.ratio(record_colrev_id, toc_records_colrev_id) / 100
                sim_list.append(sim_value)

            if not sim_list or max(sim_list) < similarity_threshold:
                raise colrev_exceptions.RecordNotInTOCException(
                    record_id=record.data[Fields.ID], toc_key=toc_key
                )

            if search_across_tocs:
                if len(list(set(sim_list))) < 2:
                    raise colrev_exceptions.RecordNotInIndexException()
                second_highest = list(set(sim_list))[-2]
                # Require a minimum difference to the next most similar record
                if (max(sim_list) - second_highest) < 0.2:
                    raise colrev_exceptions.RecordNotInIndexException()

            toc_records_colrev_id = toc_items[sim_list.index(max(sim_list))]

            record_dict = self._get_item_from_index(
                index_name=self.RECORD_INDEX,
                key=Fields.COLREV_ID,
                value=toc_records_colrev_id,
            )

            return self._prepare_record_for_return(
                record_dict, include_file=include_file
            )

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            colrev_exceptions.NotTOCIdentifiableException,
        ):
            pass

        raise colrev_exceptions.RecordNotInIndexException()

    def _get_items_from_index(
        self, query: typing.Tuple[str, list[str]], *, index_name: str
    ) -> list:
        try:
            self.thread_lock.acquire(timeout=60)
            cur = self._get_sqlite_cursor()
            select_all_query = f"{self.SELECT_ALL_QUERIES[index_name]} {query[0]}"
            cur.execute(select_all_query, query[1])
            results = cur.fetchall()
            self.thread_lock.release()
            return results

        except sqlite3.OperationalError as exc:  # pragma: no cover
            self.thread_lock.release()
            raise colrev_exceptions.RecordNotInIndexException() from exc
        except AttributeError as exc:
            raise colrev_exceptions.RecordNotInIndexException() from exc

    def _get_item_from_index(
        self,
        *,
        index_name: str,
        key: str,
        value: str,
        cursor: typing.Optional[sqlite3.Cursor] = None,
    ) -> dict:
        try:
            if cursor is None:
                self.thread_lock.acquire(timeout=60)
                cur = self._get_sqlite_cursor()
            else:
                cur = cursor

            # in the following, collisions should be handled.
            # paper_hash = hashlib.sha256(cid_to_retrieve.encode("utf-8")).hexdigest()
            # Collision
            # paper_hash = self._increment_hash(paper_hash=paper_hash)

            cur.execute(self.SELECT_KEY_QUERIES[(index_name, key)], (value,))

            selected_row = cur.fetchone()
            if cursor is None:
                self.thread_lock.release()

            if not selected_row:
                raise colrev_exceptions.RecordNotInIndexException()

            retrieved_record = {}
            if self.RECORD_INDEX == index_name:
                retrieved_record = self._get_record_from_row(selected_row)
            else:
                retrieved_record = selected_row

            if (
                key != Fields.COLREV_ID
                and (key not in retrieved_record or value != retrieved_record[key])
            ) or (
                key == Fields.COLREV_ID
                and (
                    value
                    != colrev.record.record.Record(retrieved_record).create_colrev_id()
                )
            ):
                raise colrev_exceptions.RecordNotInIndexException()

            return retrieved_record

        except sqlite3.OperationalError as exc:  # pragma: no cover
            if cursor is None:
                self.thread_lock.release()
            raise colrev_exceptions.RecordNotInIndexException() from exc

    def retrieve_based_on_colrev_pdf_id(
        self, *, colrev_pdf_id: str
    ) -> colrev.record.record.Record:
        """
        Convenience function to retrieve the indexed record_dict metadata
        based on a colrev_pdf_id
        """

        record_dict = self._get_item_from_index(
            index_name=self.RECORD_INDEX,
            key="colrev_pdf_id",
            value=colrev_pdf_id,
        )

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
                print(f"{record_dict['ID']} - no exact match")

            retrieved_record_dict = {}
            # 2. Try using global-ids
            if self._sqlite_available:
                remove_colrev_id = False
                if Fields.COLREV_ID not in record_dict:
                    try:
                        record_dict[Fields.COLREV_ID] = colrev.record.record.Record(
                            data=record_dict
                        ).create_colrev_id()
                        remove_colrev_id = True
                    except colrev_exceptions.NotEnoughDataToIdentifyException:
                        pass
                for key, value in record_dict.items():
                    if key not in self.global_keys or Fields.ID == key:
                        continue

                    retrieved_record_dict = self._get_item_from_index(
                        index_name=self.RECORD_INDEX, key=key, value=value
                    )
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

    # def is_duplicate(self, *, record1_colrev_id: list, record2_colrev_id: list) -> str:
    #     """Convenience function to check whether two records are a duplicate"""

    #     try:
    #         # Ensure that we receive actual lists
    #         # otherwise, __retrieve_based_on_colrev_id iterates over a string and
    #         # open_search_thread_instance.search returns random results
    #         assert isinstance(record1_colrev_id, list)
    #         assert isinstance(record2_colrev_id, list)

    #         # Prevent errors caused by short colrev_ids/empty lists
    #         if (
    #             any(len(cid) < 20 for cid in record1_colrev_id)
    #             or any(len(cid) < 20 for cid in record2_colrev_id)
    #             or 0 == len(record1_colrev_id)
    #             or 0 == len(record2_colrev_id)
    #         ):
    #             return "unknown"

    #         # Easy case: the initial colrev_ids overlap => duplicate
    #         initial_colrev_ids_overlap = not set(record1_colrev_id).isdisjoint(
    #             list(record2_colrev_id)
    #         )
    #         if initial_colrev_ids_overlap:
    #             return "yes"

    #         # Retrieve records from LocalIndex and use that information
    #         # to decide whether the records are duplicates

    #         r1_index = self._retrieve_based_on_colrev_id(
    #             cids_to_retrieve=record1_colrev_id
    #         )
    #         r2_index = self._retrieve_based_on_colrev_id(
    #             cids_to_retrieve=record2_colrev_id
    #         )
    #         # Each record may originate from multiple repositories simultaneously
    #         # see integration of records in __amend_record(...)
    #         # This information is stored in metadata_source_repository_paths (list)

    #         r1_metadata_source_repository_paths = r1_index.data[
    #             "metadata_source_repository_paths"
    #         ].split("\n")
    #         r2_metadata_source_repository_paths = r2_index.data[
    #             "metadata_source_repository_paths"
    #         ].split("\n")

    #         # There are no duplicates within repositories
    #         # because we only index records that are md_processed or beyond
    #         # see conditions of index_record(...)

    #         # The condition that two records are in the same repository is True if
    #         # their metadata_source_repository_paths overlap.
    #         # This does not change if records are also in non-overlapping repositories

    #         same_repository = not set(r1_metadata_source_repository_paths).isdisjoint(
    #             set(r2_metadata_source_repository_paths)
    #         )

    #         # colrev_ids must be used instead of IDs
    #         # because IDs of original repositories
    #         # are not available in the integrated record

    #         colrev_ids_overlap = not set(r1_index.get_colrev_id()).isdisjoint(
    #             list(list(r2_index.get_colrev_id()))
    #         )

    #         if same_repository:
    #             if colrev_ids_overlap:
    #                 return "yes"
    #             return "no"

    #         # Curated metadata repositories do not curate outlets redundantly,
    #         # i.e., there are no duplicates between curated repositories.
    #         # see __outlets_duplicated(...)

    #         different_curated_repositories = (
    #             r1_index.masterdata_is_curated()
    #             and r2_index.masterdata_is_curated()
    #             and (
    #                 r1_index.data.get(Fields.MD_PROV, "a")
    #                 != r2_index.data.get(Fields.MD_PROV, "b")
    #             )
    #         )

    #         if different_curated_repositories:
    #             return "no"

    #     except (
    #         colrev_exceptions.RecordNotInIndexException,
    #         colrev_exceptions.NotEnoughDataToIdentifyException,
    #     ):
    #         pass

    #     return "unknown"
