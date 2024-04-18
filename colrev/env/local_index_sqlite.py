#! /usr/bin/env python
"""LocalIndex: sqlite."""
from __future__ import annotations

import sqlite3
import typing

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.constants import LocalIndexFields

# Note: we need the local_curated_metadata field for is_duplicate()

# Note : records are indexed by id = hash(colrev_id)
# to ensure that the indexing-ids do not exceed limits
# such as the opensearch limit of 512 bytes.
# This enables efficient retrieval based on id=hash(colrev_id)
# but also search-based retrieval using only colrev_ids

# AUTHOR_INDEX = "author_index"
# AUTHOR_RECORD_INDEX = "author_record_index"
# CITATIONS_INDEX = "citations_index"


# pylint: disable=too-few-public-methods
class SQLiteIndex:
    """The SQLiteIndex class implements indexing and retrieval of records locally"""

    connection: sqlite3.Connection
    CREATE_TABLE_QUERY: str

    def __init__(
        self, *, index_name: str, index_keys: list, reinitialize: bool
    ) -> None:
        self.index_name = index_name
        self.index_keys = index_keys
        self.connection = sqlite3.connect(
            str(Filepaths.LOCAL_INDEX_SQLITE_FILE), timeout=90
        )
        self.connection.row_factory = self._dict_factory
        if reinitialize:
            self._reinitialize_db()

    def _dict_factory(self, cursor: sqlite3.Cursor, row: dict) -> dict:
        ret_dict = {}
        for idx, col in enumerate(cursor.description):
            ret_dict[col[0]] = row[idx]
        return ret_dict

    def _get_cursor(self) -> sqlite3.Cursor:
        return self.connection.cursor()

    def commit(self) -> None:
        """Commit changes to the SQLITE database"""
        if self.connection:
            self.connection.commit()

    def _reinitialize_db(self) -> None:
        """Reinitialize the SQLITE database"""

        cur = self._get_cursor()
        cur.execute(f"drop table if exists {self.index_name}")
        cur.execute(self.CREATE_TABLE_QUERY)
        if self.connection:
            self.connection.commit()

    def _get_record_from_row(self, row: dict) -> dict:

        records_dict = colrev.loader.load_utils.loads(
            load_string=row[LocalIndexFields.BIBTEX],
            implementation="bib",
            unique_id_field="ID",
        )

        retrieved_record = list(records_dict.values())[0]
        return retrieved_record


class SQLiteIndexRecord(SQLiteIndex):
    """The SQLiteIndexRecord class implements indexing and retrieval of records locally"""

    INDEX_NAME = "record_index"
    KEYS = [
        LocalIndexFields.ID,
        Fields.COLREV_ID,
        LocalIndexFields.CITATION_KEY,
        Fields.TITLE,
        Fields.ABSTRACT,
        Fields.FILE,
        LocalIndexFields.TEI,
        Fields.FULLTEXT,
        Fields.URL,
        Fields.DOI,
        LocalIndexFields.DBLP_KEY,  # Note : no dots in key names
        Fields.PDF_ID,
        LocalIndexFields.BIBTEX,
    ]

    GLOBAL_KEYS = [
        Fields.DOI,
        Fields.DBLP_KEY,
        Fields.PDF_ID,
        Fields.URL,
        Fields.COLREV_ID,
    ]

    CREATE_TABLE_QUERY = (
        f"CREATE TABLE {INDEX_NAME} (id TEXT PRIMARY KEY," + ",".join(KEYS[1:]) + ")"
    )

    SELECT_ALL_QUERY = f"SELECT * FROM {INDEX_NAME} WHERE"

    SELECT_KEY_QUERIES = {
        LocalIndexFields.ID: f"SELECT * FROM {INDEX_NAME} WHERE {LocalIndexFields.ID}=?",
        Fields.COLREV_ID: f"SELECT * FROM {INDEX_NAME} WHERE {Fields.COLREV_ID}=?",
        Fields.DOI: f"SELECT * FROM {INDEX_NAME} where {Fields.DOI}=?",
        Fields.DBLP_KEY: f"SELECT * FROM {INDEX_NAME} WHERE {Fields.DBLP_KEY}=?",
        Fields.PDF_ID: f"SELECT * FROM {INDEX_NAME} WHERE {Fields.PDF_ID}=?",
        Fields.URL: f"SELECT * FROM {INDEX_NAME} WHERE {Fields.URL}=?",
    }

    UPDATE_RECORD_QUERY = f"""
            UPDATE {INDEX_NAME} SET
            {LocalIndexFields.BIBTEX}=?
            WHERE {LocalIndexFields.ID}=?"""

    def __init__(self, *, reinitialize: bool = False) -> None:
        super().__init__(
            index_name=self.INDEX_NAME,
            index_keys=self.KEYS,
            reinitialize=reinitialize,
        )

    def insert(self, item: dict) -> None:
        """Insert a record into the index"""
        cur = self._get_cursor()
        cur.execute(
            f"INSERT INTO {self.INDEX_NAME} " f"VALUES(:{', :'.join(self.KEYS)})",
            item,
        )
        self.commit()

    def get(
        self,
        *,
        key: str,
        value: str,
    ) -> dict:
        """Get a record from the index"""
        try:
            cur = self._get_cursor()

            # in the following, collisions should be handled.
            # paper_hash = hashlib.sha256(cid_to_retrieve.encode("utf-8")).hexdigest()
            # Collision
            # paper_hash = self._increment_hash(paper_hash=paper_hash)

            cur.execute(self.SELECT_KEY_QUERIES[key], (value,))

            selected_row = cur.fetchone()

            if not selected_row:
                raise colrev_exceptions.RecordNotInIndexException()

            retrieved_record = {}
            retrieved_record = self._get_record_from_row(selected_row)

            if (
                key != Fields.COLREV_ID
                and (key not in retrieved_record or value != retrieved_record[key])
            ) or (
                key == Fields.COLREV_ID
                and (
                    value
                    != colrev.record.record.Record(retrieved_record).get_colrev_id()
                )
            ):
                raise colrev_exceptions.RecordNotInIndexException()

            return retrieved_record

        except sqlite3.OperationalError as exc:  # pragma: no cover
            raise colrev_exceptions.RecordNotInIndexException() from exc

    def update(self, local_index_id: str, bibtex: str) -> None:
        """Update a record in the index"""
        cur = self._get_cursor()
        cur.execute(
            self.UPDATE_RECORD_QUERY,
            (bibtex, local_index_id),
        )

    def search(self, query: str) -> list:
        """Search for records in the index"""
        cur = self._get_cursor()
        records_to_return = []

        selected_row = None
        print(f"{self.SELECT_ALL_QUERY} {query}")
        cur.execute(f"{self.SELECT_ALL_QUERY} {query}")
        for row in cur.fetchall():
            selected_row = row
            retrieved_record_dict = self._get_record_from_row(selected_row)
            records_to_return.append(retrieved_record_dict)
        return records_to_return


class SQLiteIndexRankings(SQLiteIndex):
    """The SQLiteIndexRankings class implements indexing and retrieval
    of journal rankings locally"""

    INDEX_NAME = "rankings"
    KEYS: typing.List[str] = []

    CREATE_TABLE_QUERY = f"CREATE TABLE {INDEX_NAME} (id TEXT PRIMARY KEY)"

    def __init__(self, *, reinitialize: bool = False) -> None:
        super().__init__(
            index_name=self.INDEX_NAME,
            index_keys=self.KEYS,
            reinitialize=reinitialize,
        )

    def insert(self, data_frame: pd.DataFrame) -> None:
        """Insert journal rankings into the index"""
        conn = sqlite3.connect(str(Filepaths.LOCAL_INDEX_SQLITE_FILE))
        data_frame.to_sql(self.INDEX_NAME, conn, if_exists="replace", index=False)
        conn.commit()
        conn.close()

    def select(self, journal: str) -> list:
        """Select journal rankings from the index"""

        cur = self._get_cursor()
        cur.execute(
            "SELECT * FROM rankings WHERE journal_name = ?",
            (journal,),
        )
        rankings = cur.fetchall()
        return rankings


class SQLiteIndexTOC(SQLiteIndex):
    """The SQLiteIndexTOC class implements indexing and retrieval of TOC items locally"""

    INDEX_NAME = "toc_index"
    KEYS: typing.List[str] = []

    CREATE_TABLE_QUERY = (
        f"CREATE TABLE {INDEX_NAME} (toc_key TEXT PRIMARY KEY, colrev_ids)"
    )

    SELECT_ALL_QUERY = {INDEX_NAME: f"SELECT * FROM {INDEX_NAME} WHERE"}

    SELECT_KEY_QUERY = {
        LocalIndexFields.TOC_KEY: f"SELECT * FROM {INDEX_NAME} WHERE {LocalIndexFields.TOC_KEY}=?",
    }

    def __init__(self, *, reinitialize: bool = False) -> None:
        super().__init__(
            index_name=self.INDEX_NAME,
            index_keys=self.KEYS,
            reinitialize=reinitialize,
        )

    def exists(self, toc_item: str) -> bool:
        """Check if TOC item exists in the index"""
        cur = self._get_cursor()
        cur.execute(
            self.SELECT_KEY_QUERY[LocalIndexFields.TOC_KEY],
            (toc_item,),
        )
        selected_row = cur.fetchone()
        if not selected_row:
            return False
        return True

    def get(
        self,
        *,
        key: str,
        value: str,
    ) -> dict:
        """Get TOC items from the index"""
        try:
            cur = self._get_cursor()

            # in the following, collisions should be handled.
            # paper_hash = hashlib.sha256(cid_to_retrieve.encode("utf-8")).hexdigest()
            # Collision
            # paper_hash = self._increment_hash(paper_hash=paper_hash)

            cur.execute(self.SELECT_KEY_QUERY[key], (value,))
            selected_row = cur.fetchone()

            if not selected_row:
                raise colrev_exceptions.RecordNotInIndexException()

            retrieved_record = {}
            retrieved_record = selected_row

            if (
                key != Fields.COLREV_ID
                and (key not in retrieved_record or value != retrieved_record[key])
            ) or (
                key == Fields.COLREV_ID
                and (
                    value
                    != colrev.record.record.Record(retrieved_record).get_colrev_id()
                )
            ):
                raise colrev_exceptions.RecordNotInIndexException()

            return retrieved_record

        except sqlite3.OperationalError as exc:  # pragma: no cover
            raise colrev_exceptions.RecordNotInIndexException() from exc

    def get_toc_items(self, query: typing.Tuple[str, list[str]]) -> list:
        """Get TOC items from the index"""
        try:
            cur = self._get_cursor()
            select_all_query = f"{self.SELECT_ALL_QUERY} {query[0]}"
            cur.execute(select_all_query, query[1])
            results = cur.fetchall()
            return results

        except sqlite3.OperationalError as exc:  # pragma: no cover
            raise colrev_exceptions.RecordNotInIndexException() from exc
        except AttributeError as exc:
            raise colrev_exceptions.RecordNotInIndexException() from exc

    def add(self, toc_to_index: dict) -> None:
        """Add TOC items to the index"""
        list_to_add = list((k, v) for k, v in toc_to_index.items() if v != "DROPPED")
        cur = self._get_cursor()
        try:
            cur.executemany(f"INSERT INTO {self.INDEX_NAME} VALUES(?, ?)", list_to_add)
        except sqlite3.IntegrityError as exc:  # pragma: no cover
            print(exc)
        finally:
            self.commit()
