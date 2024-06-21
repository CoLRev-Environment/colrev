#! /usr/bin/env python
"""Indexing and retrieving records locally."""
from __future__ import annotations

import sqlite3
import typing
from copy import deepcopy
from multiprocessing import Lock
from pathlib import Path

import git
from git.exc import GitCommandError

import colrev.env.environment_manager
import colrev.env.local_index_sqlite
import colrev.env.resources
import colrev.env.tei_parser
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.ops.check
import colrev.record.record
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.env.local_index_prep import prepare_record_for_return


class LocalIndex:
    """The LocalIndex implements indexing and retrieval of records across projects"""

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

    def get_journal_rankings(self, journal: str) -> list:
        """Get the journal rankings from the sqlite database"""
        sqlite_index_ranking = colrev.env.local_index_sqlite.SQLiteIndexRankings()
        return sqlite_index_ranking.select(journal=journal)

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
            finally:
                sqlite_index_record.connection.close()

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
        cids_to_retrieve = [record.get_colrev_id()]
        retrieved_record = self._retrieve_based_on_colrev_id(cids_to_retrieve)
        if retrieved_record.data[Fields.ENTRYTYPE] != record.data[Fields.ENTRYTYPE]:
            if record_dict.get(Fields.CURATION_ID, "NA").startswith(
                "https://github.com/"
            ):
                return self._retrieve_from_github_curation(record_dict=record_dict)
            raise colrev_exceptions.RecordNotInIndexException
        return retrieved_record

    def search(self, query: str) -> list[colrev.record.record.Record]:
        """Run a search for records"""

        try:
            self.thread_lock.acquire(timeout=60)
            sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
            records_to_return = []
            for record_dict in sqlite_index_record.search(query=query):
                record = prepare_record_for_return(record_dict, include_file=False)
                records_to_return.append(record)

        except sqlite3.OperationalError as exc:  # pragma: no cover
            print(exc)
        finally:
            sqlite_index_record.connection.close()
            self.thread_lock.release()

        return records_to_return

    def get_year_from_toc(self, record_dict: dict) -> str:
        """Determine the year of a paper based on its table-of-content (journal-volume-number)"""

        try:
            sqlite_index_toc = colrev.env.local_index_sqlite.SQLiteIndexTOC()
            toc_key = colrev.record.record.Record(record_dict).get_toc_key()
            toc_items = []
            if self._toc_exists(toc_key):
                toc_items = sqlite_index_toc.get_toc_items(toc_key=toc_key)

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
        finally:
            sqlite_index_toc.connection.close()

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
            sqlite_index_toc.connection.close()
            self.thread_lock.release()
        return False

    def _get_toc_items(self, toc_key: str, *, search_across_tocs: bool) -> list:
        sqlite_index_toc = colrev.env.local_index_sqlite.SQLiteIndexTOC()
        toc_items = []
        if self._toc_exists(toc_key):
            toc_items = sqlite_index_toc.get_toc_items(toc_key=toc_key)
        else:
            if not search_across_tocs:
                sqlite_index_toc.connection.close()
                raise colrev_exceptions.RecordNotInIndexException()

        if not toc_items and search_across_tocs:
            try:

                partial_toc_key = toc_key.rsplit("|", 1)[0]

                toc_items = sqlite_index_toc.get_toc_items(
                    partial_toc_key=partial_toc_key
                )
                sqlite_index_toc.connection.close()
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

        # Note: in NotTOCIdentifiableException cases, we still need a toc_key.
        # to accomplish this, the get_toc_key() may acced an "accept_incomplete" flag
        try:
            toc_key = record.get_toc_key()
        except colrev_exceptions.NotTOCIdentifiableException as exc:
            raise colrev_exceptions.RecordNotInIndexException() from exc

        toc_items = self._get_toc_items(toc_key, search_across_tocs=search_across_tocs)
        # SQLiteIndexRecord() must be after _get_toc_items(), which also uses the sqlite file
        sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
        try:
            for toc_records_colrev_id in toc_items:
                record_dict = sqlite_index_record.get(
                    key=Fields.COLREV_ID, value=toc_records_colrev_id
                )

                if not colrev.record.record_similarity.matches(
                    record, colrev.record.record.Record(record_dict)
                ):
                    continue

                return prepare_record_for_return(record_dict, include_file=include_file)
            raise colrev_exceptions.RecordNotInTOCException(
                record_id=record.data[Fields.ID], toc_key=toc_key
            )

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            colrev_exceptions.NotTOCIdentifiableException,
        ):
            pass

        sqlite_index_record.connection.close()

        raise colrev_exceptions.RecordNotInIndexException()

    def retrieve_based_on_colrev_pdf_id(
        self, *, colrev_pdf_id: str
    ) -> colrev.record.record.Record:
        """
        Convenience function to retrieve the indexed record_dict metadata
        based on a colrev_pdf_id
        """
        try:
            sqlite_index_record = colrev.env.local_index_sqlite.SQLiteIndexRecord()
            record_dict = sqlite_index_record.get(
                key=Fields.PDF_ID, value=colrev_pdf_id
            )
            record_to_import = prepare_record_for_return(record_dict, include_file=True)
            record_to_import.data.pop(Fields.FILE, None)
        finally:
            sqlite_index_record.connection.close()
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
                try:
                    sqlite_index_record = (
                        colrev.env.local_index_sqlite.SQLiteIndexRecord()
                    )
                    retrieved_record_dict = sqlite_index_record.get(
                        key=key, value=value
                    )
                finally:
                    sqlite_index_record.connection.close()

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

        return prepare_record_for_return(
            retrieved_record_dict,
            include_file=include_file,
            include_colrev_ids=include_colrev_ids,
        )

    def get_fields_to_remove(self, record_dict: dict) -> list:
        """Compares the record to available toc items and
        returns fields to remove (if any), such as the volume or number."""
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
