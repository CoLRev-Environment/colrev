#! /usr/bin/env python
"""Indexing and retrieving records locally."""
from __future__ import annotations

import binascii
import collections
import hashlib
import logging
import os
import time
import typing
from copy import deepcopy
from datetime import timedelta
from json import JSONDecodeError
from pathlib import Path
from threading import Timer

import docker
import requests
import requests_cache
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError
from opensearchpy.exceptions import SerializationError
from opensearchpy.exceptions import TransportError
from pybtex.database.input import bibtex
from pybtex.scanner import PrematureEOF
from pybtex.scanner import TokenRequired
from thefuzz import fuzz
from tqdm import tqdm

import colrev.env.environment_manager
import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


# pylint: disable=too-many-lines


class LocalIndex:
    """The LocalIndex implements indexing and retrieval of records across projects"""

    global_keys = ["doi", "dblp_key", "colrev_pdf_id", "url"]
    max_len_sha256 = 2**256
    request_timeout = 90

    local_environment_path = Path.home().joinpath("colrev")

    opensearch_index = local_environment_path / Path("index")
    teiind_path = local_environment_path / Path(".tei_index/")
    annotators_path = local_environment_path / Path("annotators")

    # Note : records are indexed by id = hash(colrev_id)
    # to ensure that the indexing-ids do not exceed limits
    # such as the opensearch limit of 512 bytes.
    # This enables efficient retrieval based on id=hash(colrev_id)
    # but also search-based retrieval using only colrev_ids

    RECORD_INDEX = "record_index"
    TOC_INDEX = "toc_index"
    AUTHOR_INDEX = "author_index"
    AUTHOR_RECORD_INDEX = "author_record_index"
    CITATIONS_INDEX = "citations_index"

    OPENSEARCH_URL = "http://localhost:9200"

    # Note: we need the local_curated_metadata field for is_duplicate()

    def __init__(
        self,
        *,
        startup_without_waiting: bool = False,
        verbose_mode: bool = False,
    ) -> None:

        self.verbose_mode = verbose_mode
        self.environment_manager = colrev.env.environment_manager.EnvironmentManager()
        self.os_dashboard_image = "opensearchproject/opensearch-dashboards:2.3.0"
        self.environment_manager.build_docker_image(imagename=self.os_dashboard_image)
        self.environment_manager.register_ports(ports=["5601"])

        self.os_image = "opensearchproject/opensearch:2.3.0"
        self.environment_manager.build_docker_image(imagename=self.os_image)
        self.environment_manager.register_ports(ports=["9200"])

        self.open_search = OpenSearch(self.OPENSEARCH_URL)
        self.opensearch_index.mkdir(exist_ok=True, parents=True)
        try:
            self.check_opensearch_docker_available()
        except TransportError:
            self.start_opensearch_docker(
                startup_without_waiting=startup_without_waiting
            )

        if not startup_without_waiting:
            self.check_opensearch_docker_available()

        logging.getLogger("opensearch").setLevel(logging.ERROR)

        self.__index_tei = False

    def start_opensearch_docker_dashboards(self) -> None:
        """Start the local_index dashboard (opensearch dashboard Docker container)"""

        self.start_opensearch_docker()
        client = docker.from_env()
        if not any(
            "opensearch-dashboards" in container.name
            for container in client.containers.list()
        ):
            try:
                print("Start OpenSearch Dashboards")

                if not client.networks.list(names=["opensearch-net"]):
                    client.networks.create("opensearch-net")

                client.containers.run(
                    self.os_dashboard_image,
                    name="opensearch-dashboards",
                    ports={"5601/tcp": 5601},
                    auto_remove=True,
                    detach=True,
                    environment={
                        "OPENSEARCH_HOSTS": '["http://opensearch-node:9200"]',
                        "DISABLE_SECURITY_DASHBOARDS_PLUGIN": "true",
                    },
                    network="opensearch-net",
                )
            except docker.errors.APIError as exc:
                print(exc)

    def start_opensearch_docker(self, *, startup_without_waiting: bool = False) -> None:
        """Start the local_index (opensearch Docker container)"""

        client = docker.from_env()
        if not any(
            "opensearch" in container.name for container in client.containers.list()
        ):
            try:
                if not startup_without_waiting:
                    print("Start LocalIndex")

                if not client.networks.list(names=["opensearch-net"]):
                    client.networks.create("opensearch-net")
                client.containers.run(
                    self.os_image,
                    name="opensearch-node",
                    ports={"9200/tcp": 9200, "9600/tcp": 9600},
                    auto_remove=True,
                    detach=True,
                    environment={
                        "cluster.name": "opensearch-cluster",
                        "node.name": "opensearch-node",
                        "bootstrap.memory_lock": "true",
                        "OPENSEARCH_JAVA_OPTS": "-Xms512m -Xmx512m",
                        "DISABLE_INSTALL_DEMO_CONFIG": "true",
                        "DISABLE_SECURITY_PLUGIN": "true",
                        "discovery.type": "single-node",
                    },
                    volumes={
                        str(self.opensearch_index): {
                            "bind": "/usr/share/opensearch/data",
                            "mode": "rw",
                        }
                    },
                    ulimits=[
                        docker.types.Ulimit(name="memlock", soft=-1, hard=-1),
                        docker.types.Ulimit(name="nofile", soft=65536, hard=65536),
                    ],
                    network="opensearch-net",
                )
            except docker.errors.APIError as exc:
                print(exc)

        logging.getLogger("opensearch").setLevel(logging.ERROR)

        available = False
        try:
            self.open_search.get(index=self.RECORD_INDEX, id="test")
        except NotFoundError:
            available = True
        except (
            requests.exceptions.RequestException,
            TransportError,
            SerializationError,
        ):
            pass

        if not available and not startup_without_waiting:
            print("Waiting until LocalIndex is available")
            for _ in tqdm(range(0, 20)):
                try:
                    self.open_search.get(
                        index=self.RECORD_INDEX,
                        id="test",
                    )
                    break
                except NotFoundError:
                    break
                except (
                    requests.exceptions.RequestException,
                    TransportError,
                    SerializationError,
                ):
                    time.sleep(3)
        logging.getLogger("opensearch").setLevel(logging.WARNING)

    def check_opensearch_docker_available(self) -> None:
        """Check whether the local_index (opensearch Docker container) is available"""
        # If not available after 120s: raise error
        logging.getLogger("opensearch").setLevel(logging.ERROR)
        self.open_search.info()
        logging.getLogger("opensearch").setLevel(logging.WARNING)

    def __get_record_hash(self, *, record_dict: dict) -> str:
        # Note : may raise NotEnoughDataToIdentifyException
        string_to_hash = colrev.record.Record(data=record_dict).create_colrev_id()
        return hashlib.sha256(string_to_hash.encode("utf-8")).hexdigest()

    def __increment_hash(self, *, paper_hash: str) -> str:

        plaintext = binascii.unhexlify(paper_hash)
        # also, we'll want to know our length later on
        plaintext_length = len(plaintext)
        plaintext_number = int.from_bytes(plaintext, "big")

        # recommendation: do not increment by 1
        plaintext_number += 10
        plaintext_number = plaintext_number % self.max_len_sha256

        new_plaintext = plaintext_number.to_bytes(plaintext_length, "big")
        new_hex = binascii.hexlify(new_plaintext)
        # print(new_hex.decode("utf-8"))

        return new_hex.decode("utf-8")

    def __get_tei_index_file(self, *, paper_hash: str) -> Path:
        return self.teiind_path / Path(f"{paper_hash[:2]}/{paper_hash[2:]}.tei.xml")

    def __index_author(
        self, tei: colrev.env.tei_parser.TEIParser, record_dict: dict
    ) -> None:
        author_details = tei.get_author_details()
        # Iterate over curated metadata and enrich it based on TEI (may vary in quality)
        for author in record_dict.get("author", "").split(" and "):
            if "," not in author:
                continue
            author_dict = {}
            author_dict["surname"] = author.split(", ")[0]
            author_dict["forename"] = author.split(", ")[1]
            for author_detail in author_details:
                if author_dict["surname"] == author_detail["surname"]:
                    # Add complementary details
                    author_dict = {**author_dict, **author_detail}
            self.open_search.index(index=self.AUTHOR_INDEX, body=author_dict)

    def __store_record(self, *, paper_hash: str, record_dict: dict) -> None:

        if self.__index_tei:
            if "file" in record_dict:
                try:
                    tei_path = self.__get_tei_index_file(paper_hash=paper_hash)
                    tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                    if Path(record_dict["file"]).is_file():
                        tei = colrev.env.tei_parser.TEIParser(
                            environment_manager=self.environment_manager,
                            pdf_path=Path(record_dict["file"]),
                            tei_path=tei_path,
                        )

                        record_dict["fulltext"] = tei.get_tei_str()

                        self.__index_author(tei=tei, record_dict=record_dict)

                except (
                    colrev_exceptions.TEIException,
                    AttributeError,
                    SerializationError,
                    TransportError,
                ):
                    pass

        record = colrev.record.Record(data=record_dict)

        if "colrev_status" in record.data:
            del record.data["colrev_status"]

        self.open_search.index(
            index=self.RECORD_INDEX, id=paper_hash, body=record.get_data(stringify=True)
        )

    def __retrieve_toc_index(self, *, toc_key: str) -> dict:

        toc_item = {}
        try:
            toc_item_response = self.open_search.get(index=self.TOC_INDEX, id=toc_key)
            toc_item = toc_item_response["_source"]
        except (SerializationError, KeyError):
            pass
        return toc_item

    def __amend_record(self, *, paper_hash: str, record_dict: dict) -> None:

        try:
            saved_record_response = self.open_search.get(
                index=self.RECORD_INDEX,
                id=paper_hash,
            )
            saved_record_dict = saved_record_response["_source"]

            # Create fulltext backup to prevent bibtext parsing issues
            fulltext_backup = saved_record_dict.get("fulltext", "NA")
            if "fulltext" in saved_record_dict:
                del saved_record_dict["fulltext"]

            parsed_record_dict = self.__parse_record(record_dict=saved_record_dict)
            saved_record = colrev.record.Record(data=parsed_record_dict)
            record = colrev.record.Record(data=record_dict)

            # combine metadata_source_repository_paths in a semicolon-separated list
            metadata_source_repository_paths = record.data[
                "metadata_source_repository_paths"
            ]
            saved_record.data["metadata_source_repository_paths"] += (
                "\n" + metadata_source_repository_paths
            )

            record_dict = record.get_data()

            # amend saved record
            for key, value in record_dict.items():
                # Note : the record from the first repository should take precedence)
                if key in saved_record.data or key in ["colrev_status"]:
                    continue

                field_provenance = colrev.record.Record(
                    data=record_dict
                ).get_field_provenance(
                    key=key,
                    default_source=record.data.get(
                        "metadata_source_repository_paths", "None"
                    ),
                )

                saved_record.update_field(
                    key=key, value=value, source=field_provenance["source_info"]
                )

            saved_record_dict = saved_record.get_data(stringify=True)

            # Important: full-texts should be added after get_data (parsing records)
            # to avoid error-printouts by pybtex
            if "NA" != fulltext_backup:
                saved_record.data["fulltext"] = fulltext_backup
            elif "file" in record_dict:
                try:
                    tei_path = self.__get_tei_index_file(paper_hash=paper_hash)
                    tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                    if Path(record_dict["file"]).is_file():
                        tei = colrev.env.tei_parser.TEIParser(
                            environment_manager=self.environment_manager,
                            pdf_path=Path(record_dict["file"]),
                            tei_path=tei_path,
                        )
                        saved_record.data["fulltext"] = tei.get_tei_str()
                except (
                    colrev_exceptions.TEIException,
                    AttributeError,
                    SerializationError,
                    TransportError,
                ):
                    pass

            # Note : update(...) accepts the timeout keyword
            # https://opensearch-project.github.io/opensearch-py/
            # api-ref/client.html#opensearchpy.OpenSearch.update
            # pylint: disable=unexpected-keyword-arg
            self.open_search.update(
                index=self.RECORD_INDEX,
                id=paper_hash,
                body={"doc": saved_record_dict},
                timeout=self.request_timeout,
            )
        except (NotFoundError, KeyError):
            pass

    def get_fields_to_remove(self, *, record_dict: dict) -> list:
        """Compares the record to available toc items and
        returns fields to remove (if any)"""
        # pylint: disable=too-many-return-statements

        fields_to_remove: typing.List[str] = []
        if "journal" not in record_dict and "article" != record_dict["ENTRYTYPE"]:
            return fields_to_remove

        internal_record_dict = deepcopy(record_dict)
        if all(x in internal_record_dict.keys() for x in ["volume", "number"]):

            try:
                toc_key_full = colrev.record.Record(
                    data=internal_record_dict
                ).get_toc_key()
            except colrev_exceptions.NotTOCIdentifiableException:
                return fields_to_remove

            open_search_thread_instance = OpenSearch(self.OPENSEARCH_URL)

            if open_search_thread_instance.exists(
                index=self.TOC_INDEX, id=toc_key_full
            ):
                return fields_to_remove

            wo_nr = deepcopy(internal_record_dict)
            del wo_nr["number"]
            toc_key_wo_nr = colrev.record.Record(data=wo_nr).get_toc_key()
            if "NA" != toc_key_wo_nr:
                toc_key_wo_nr_exists = open_search_thread_instance.exists(
                    index=self.TOC_INDEX, id=toc_key_wo_nr
                )
                if toc_key_wo_nr_exists:
                    fields_to_remove.append("number")
                    return fields_to_remove

            wo_vol = deepcopy(internal_record_dict)
            del wo_vol["volume"]
            toc_key_wo_vol = colrev.record.Record(data=wo_vol).get_toc_key()
            if "NA" != toc_key_wo_vol:
                toc_key_wo_vol_exists = open_search_thread_instance.exists(
                    index=self.TOC_INDEX, id=toc_key_wo_vol
                )
                if toc_key_wo_vol_exists:
                    fields_to_remove.append("volume")
                    return fields_to_remove

            wo_vol_nr = deepcopy(internal_record_dict)
            del wo_vol_nr["volume"]
            del wo_vol_nr["number"]
            toc_key_wo_vol_nr = colrev.record.Record(data=wo_vol_nr).get_toc_key()
            if "NA" != toc_key_wo_vol_nr:
                toc_key_wo_vol_nr_exists = open_search_thread_instance.exists(
                    index=self.TOC_INDEX, id=toc_key_wo_vol_nr
                )
                if toc_key_wo_vol_nr_exists:
                    fields_to_remove.append("number")
                    fields_to_remove.append("volume")
                    return fields_to_remove

        return fields_to_remove

    def __toc_index(self, *, record_dict: dict) -> None:
        if not colrev.record.Record(data=record_dict).masterdata_is_curated():
            return

        if record_dict.get("ENTRYTYPE", "") in ["article", "inproceedings"]:
            # Note : records are md_prepared, i.e., complete

            toc_key = colrev.record.Record(data=record_dict).get_toc_key()
            if "NA" == toc_key:
                return

            # print(toc_key)
            try:
                record_colrev_id = colrev.record.Record(
                    data=record_dict
                ).create_colrev_id()

                if not self.open_search.exists(index=self.TOC_INDEX, id=toc_key):
                    toc_item = {
                        "toc_key": toc_key,
                        "colrev_ids": [record_colrev_id],
                    }
                    self.open_search.index(
                        index=self.TOC_INDEX, id=toc_key, body=toc_item
                    )
                else:
                    toc_item_response = self.open_search.get(
                        index=self.TOC_INDEX,
                        id=toc_key,
                    )
                    toc_item = toc_item_response["_source"]
                    if toc_item["toc_key"] == toc_key:
                        # ok - no collision, update the record
                        # Note : do not update (the record from the first repository
                        #  should take precedence - reset the index to update)
                        if record_colrev_id not in toc_item["colrev_ids"]:
                            toc_item["colrev_ids"].append(  # type: ignore
                                record_colrev_id
                            )
                            self.open_search.update(
                                index=self.TOC_INDEX, id=toc_key, body={"doc": toc_item}
                            )
            except (
                colrev_exceptions.NotEnoughDataToIdentifyException,
                TransportError,
                SerializationError,
                KeyError,
            ):
                pass

        return

    def __retrieve_based_on_colrev_id(self, *, cids_to_retrieve: list) -> dict:
        # Note : may raise NotEnoughDataToIdentifyException

        for cid_to_retrieve in cids_to_retrieve:
            paper_hash = hashlib.sha256(cid_to_retrieve.encode("utf-8")).hexdigest()
            while True:  # Note : while breaks with NotFoundError
                try:
                    res = self.open_search.get(
                        index=self.RECORD_INDEX,
                        id=paper_hash,
                    )
                    retrieved_record = res["_source"]
                    if (
                        cid_to_retrieve
                        in colrev.record.Record(data=retrieved_record).get_colrev_id()
                    ):
                        return retrieved_record
                    # Collision
                    paper_hash = self.__increment_hash(paper_hash=paper_hash)
                except (NotFoundError, TransportError, SerializationError, KeyError):
                    break

        # search colrev_id field
        for cid_to_retrieve in cids_to_retrieve:
            try:

                resp = self.open_search.search(
                    index=self.RECORD_INDEX,
                    body={"query": {"match_phrase": {"colrev_id": cid_to_retrieve}}},
                )
                retrieved_record = resp["hits"]["hits"][0]["_source"]
                if cid_to_retrieve in retrieved_record.get("colrev_id", "NA"):
                    return retrieved_record
            except (
                IndexError,
                KeyError,
                NotFoundError,
                TransportError,
                SerializationError,
            ) as exc:
                raise colrev_exceptions.RecordNotInIndexException from exc

        raise colrev_exceptions.RecordNotInIndexException

    def __retrieve_from_record_index(self, *, record_dict: dict) -> dict:
        # Note : may raise NotEnoughDataToIdentifyException

        record = colrev.record.Record(data=record_dict)
        if "colrev_id" in record.data:
            cid_to_retrieve = record.get_colrev_id()
        else:
            cid_to_retrieve = [record.create_colrev_id()]

        retrieved_record = self.__retrieve_based_on_colrev_id(
            cids_to_retrieve=cid_to_retrieve
        )
        if retrieved_record["ENTRYTYPE"] != record_dict["ENTRYTYPE"]:
            raise colrev_exceptions.RecordNotInIndexException
        return retrieved_record

    def __parse_record(self, *, record_dict: dict) -> dict:
        # pylint: disable=redefined-outer-name
        # pylint: disable=import-outside-toplevel
        import colrev.dataset

        # Note : we need to parse it through parse_records_dict (pybtex / parse_string)
        # To make sure all fields are formatted /parsed consistently
        parser = bibtex.Parser()
        load_str = (
            "@"
            + record_dict["ENTRYTYPE"]
            + "{"
            + record_dict["ID"]
            + "\n"
            + ",\n".join(
                [
                    f"{k} = {{{v}}}"
                    for k, v in record_dict.items()
                    if k not in ["ID", "ENTRYTYPE"]
                ]
            )
            + "}"
        )
        bib_data = parser.parse_string(load_str)
        records_dict = colrev.dataset.Dataset.parse_records_dict(
            records_dict=bib_data.entries
        )
        record = list(records_dict.values())[0]

        return record

    def __prepare_record_for_return(
        self,
        *,
        record_dict: dict,
        include_file: bool = False,
        include_colrev_ids: bool = False,
    ) -> dict:
        """Prepare a record for return (from local index)"""

        # pylint: disable=too-many-branches

        # Note : remove fulltext before parsing because it raises errors
        fulltext_backup = record_dict.get("fulltext", "NA")
        if "fulltext" in record_dict:
            del record_dict["fulltext"]

        record_dict = self.__parse_record(record_dict=record_dict)

        keys_to_remove = (
            "fulltext",
            "tei_file",
            "grobid-version",
            "excl_criteria",
            "exclusion_criteria",
            "local_curated_metadata",
            "metadata_source_repository_paths",
        )

        for key in keys_to_remove:
            record_dict.pop(key, None)

        # Note: record['file'] should be an absolute path by definition
        # when stored in the LocalIndex
        if "file" in record_dict:
            if not Path(record_dict["file"]).is_file():
                del record_dict["file"]

        if include_colrev_ids:
            if "colrev_id" in record_dict:
                pass
        else:
            if "colrev_id" in record_dict:
                del record_dict["colrev_id"]

        if include_file:
            if "NA" != fulltext_backup:
                record_dict["fulltext"] = fulltext_backup
        else:
            if "file" in record_dict:
                del record_dict["file"]
            if "file" in record_dict.get("colrev_data_provenance", {}):
                del record_dict["colrev_data_provenance"]["file"]
            if "colrev_pdf_id" in record_dict:
                del record_dict["colrev_pdf_id"]
            if "colrev_pdf_id" in record_dict.get("colrev_data_provenance", {}):
                del record_dict["colrev_data_provenance"]["colrev_pdf_id"]

        record_dict["colrev_status"] = colrev.record.RecordState.md_prepared

        if "CURATED" in record_dict["colrev_masterdata_provenance"]:
            identifier_string = (
                record_dict["colrev_masterdata_provenance"]["CURATED"]["source"]
                + "#"
                + record_dict["ID"]
            )
            record_dict["curation_ID"] = identifier_string

        return record_dict

    def search(self, *, query: dict) -> list[colrev.record.Record]:
        """Run a search for records"""

        # Resource for other query types:
        # https://github.com/aiven/demo-opensearch-python/blob/main/search.py

        # pylint: disable=unexpected-keyword-arg

        # https://opensearch.org/docs/latest/opensearch/ux/#scroll-search
        # Code based on: https://t1p.de/vbyc3
        res = self.open_search.search(
            index=self.RECORD_INDEX, body=query, size=100, scroll="10m"
        )

        old_scroll_id = res.get("_scroll_id", "NA")
        records_to_return = []
        try:
            while len(res["hits"]["hits"]):

                for item in res["hits"]["hits"]:
                    record_to_import = item["_source"]  # type: ignore
                    if "fulltext" in record_to_import:
                        del record_to_import["fulltext"]

                    record_to_import = {k: str(v) for k, v in record_to_import.items()}
                    record_to_import = {
                        k: v for k, v in record_to_import.items() if "None" != v
                    }
                    try:
                        record_to_import = self.__prepare_record_for_return(
                            record_dict=record_to_import, include_file=False
                        )
                        records_to_return.append(
                            colrev.record.Record(data=record_to_import)
                        )
                    except (PrematureEOF, TokenRequired):
                        pass

                res = self.open_search.scroll(scroll_id=old_scroll_id, scroll="2s")

                # Note : the scroll_id typically does not change (but it can)
                old_scroll_id = res["_scroll_id"]
        except KeyError:
            pass

        return records_to_return

    def __outlets_duplicated(self) -> bool:

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

    def _prepare_record_for_indexing(self, *, record_dict: dict) -> dict:

        # pylint: disable=too-many-branches
        if "colrev_status" not in record_dict:
            raise colrev_exceptions.RecordNotIndexableException()

        # It is important to exclude md_prepared if the LocalIndex
        # is used to dissociate duplicates
        if (
            record_dict["colrev_status"]
            in colrev.record.RecordState.get_non_processed_states()
        ):
            raise colrev_exceptions.RecordNotIndexableException()

        # Some prescreen_excluded records are not prepared
        if (
            record_dict["colrev_status"]
            == colrev.record.RecordState.rev_prescreen_excluded
        ):
            raise colrev_exceptions.RecordNotIndexableException()

        if "screening_criteria" in record_dict:
            del record_dict["screening_criteria"]
        # Note: if the colrev_pdf_id has not been checked,
        # we cannot use it for retrieval or preparation.
        post_pdf_prepared_states = colrev.record.RecordState.get_post_x_states(
            state=colrev.record.RecordState.pdf_prepared
        )
        if record_dict["colrev_status"] not in post_pdf_prepared_states:
            if "colrev_pdf_id" in record_dict:
                del record_dict["colrev_pdf_id"]

        # Note : this is the first run, no need to split/list
        if "colrev/curated_metadata" in record_dict["metadata_source_repository_paths"]:
            # Note : local_curated_metadata is important to identify non-duplicates
            # between curated_metadata_repositories
            record_dict["local_curated_metadata"] = "yes"

        # To fix pdf_hash fields that should have been renamed
        if "pdf_hash" in record_dict:
            record_dict["colrev_pdf_id"] = "cpid1:" + record_dict["pdf_hash"]
            del record_dict["pdf_hash"]

        if "colrev_origin" in record_dict:
            del record_dict["colrev_origin"]

        # Note : numbers of citations change regularly.
        # They should be retrieved from sources like crossref/doi.org
        if "cited_by" in record_dict:
            del record_dict["cited_by"]

        # Note : file paths should be absolute when added to the LocalIndex
        if "file" in record_dict:
            pdf_path = Path(record_dict["file"])
            if pdf_path.is_file():
                record_dict["file"] = str(pdf_path)
            else:
                del record_dict["file"]

        if record_dict.get("year", "NA").isdigit():
            record_dict["year"] = int(record_dict["year"])
        elif "year" in record_dict:
            del record_dict["year"]

        # Provenance should point to the original repository path.
        # If the provenance/source was example.bib (and the record is amended during indexing)
        # we wouldn't know where the example.bib belongs to.
        record = colrev.record.Record(data=record_dict)
        for key in list(record.data.keys()):
            if key not in colrev.record.Record.identifying_field_keys:
                if key not in colrev.record.Record.provenance_keys + [
                    "ID",
                    "ENTRYTYPE",
                    "local_curated_metadata",
                    "metadata_source_repository_paths",
                ]:
                    if key not in record.data.get("colrev_data_provenance", {}):
                        record.add_data_provenance(
                            key=key,
                            source=record_dict["metadata_source_repository_paths"],
                        )
                    else:
                        if (
                            "CURATED"
                            not in record.data["colrev_data_provenance"][key]["source"]
                        ):
                            record.add_data_provenance(
                                key=key,
                                source=record_dict["metadata_source_repository_paths"],
                            )
            else:
                if not record.masterdata_is_curated():
                    record.add_masterdata_provenance(
                        key=key, source=record_dict["metadata_source_repository_paths"]
                    )

        # Make sure that we don't add provenance information without corresponding fields
        if "colrev_data_provenance" in record.data:
            provenance_keys = list(record.data.get("colrev_data_provenance", {}).keys())
            for provenance_key in provenance_keys:
                if provenance_key not in record.data:
                    del record.data["colrev_data_provenance"][provenance_key]
        if not record.masterdata_is_curated():
            if "colrev_masterdata_provenance" in record.data:
                provenance_keys = list(
                    record.data.get("colrev_masterdata_provenance", {}).keys()
                )
                for provenance_key in provenance_keys:
                    if provenance_key not in record.data:
                        del record.data["colrev_masterdata_provenance"][provenance_key]

        return record.get_data()

    def _add_record_to_index(self, *, record_dict: dict) -> None:
        cid_to_index = colrev.record.Record(data=record_dict).create_colrev_id()
        record_dict["colrev_id"] = cid_to_index
        paper_hash = self.__get_record_hash(record_dict=record_dict)

        try:
            # check if the record is already indexed (based on d)
            retrieved_record = self.retrieve(
                record_dict=record_dict, include_colrev_ids=True
            )
            retrieved_record_cid = colrev.record.Record(
                data=retrieved_record
            ).get_colrev_id()

            # if colrev_ids not identical (but overlapping): amend
            if not set(retrieved_record_cid).isdisjoint([cid_to_index]):
                # Note: we need the colrev_id of the retrieved_record
                # (may be different from record)
                self.__amend_record(
                    paper_hash=self.__get_record_hash(record_dict=retrieved_record),
                    record_dict=record_dict,
                )
                return
        except (
            colrev_exceptions.RecordNotInIndexException,
            TransportError,
            SerializationError,
        ):
            pass

        while True:
            if not self.open_search.exists(index=self.RECORD_INDEX, id=hash):
                self.__store_record(paper_hash=paper_hash, record_dict=record_dict)
                break
            saved_record_response = self.open_search.get(
                index=self.RECORD_INDEX,
                id=paper_hash,
            )
            saved_record = saved_record_response["_source"]
            saved_record_cid = colrev.record.Record(data=saved_record).create_colrev_id(
                assume_complete=True
            )
            if saved_record_cid == cid_to_index:
                # ok - no collision, update the record
                # Note : do not update (the record from the first repository
                # should take precedence - reset the index to update)
                self.__amend_record(paper_hash=paper_hash, record_dict=record_dict)
                break
            # to handle the collision:
            print(f"Collision: {paper_hash}")
            print(cid_to_index)
            print(saved_record_cid)
            print(saved_record)
            paper_hash = self.__increment_hash(paper_hash=paper_hash)

    def index_record(self, *, record_dict: dict) -> None:
        """Index a record"""
        # Note : may raise NotEnoughDataToIdentifyException

        def is_curated_metadata(*, copy_for_toc_index: dict) -> bool:
            return (
                "colrev/curated_metadata"
                in copy_for_toc_index["metadata_source_repository_paths"]
            )

        copy_for_toc_index = deepcopy(record_dict)
        record_dict = self._prepare_record_for_indexing(record_dict=record_dict)
        try:
            self._add_record_to_index(record_dict=record_dict)
        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            TransportError,
            SerializationError,
            KeyError,
        ) as exc:
            if self.verbose_mode:
                print(exc)
                print(record_dict)
            return

        # Note : only use curated journal metadata for TOC indices
        # otherwise, TOCs will be incomplete and affect retrieval
        if is_curated_metadata(copy_for_toc_index=copy_for_toc_index):
            self.__toc_index(record_dict=copy_for_toc_index)

    def index_colrev_project(self, *, repo_source_path: Path) -> None:
        """Index a CoLRev project"""

        # pylint: disable=import-outside-toplevel
        # pylint: disable=redefined-outer-name
        # pylint: disable=cyclic-import
        # pylint: disable=too-many-branches
        import colrev.review_manager

        try:
            if not Path(repo_source_path).is_dir():
                print(f"Warning {repo_source_path} not a directory")
                return

            print(f"Index records from {repo_source_path}")
            os.chdir(repo_source_path)
            review_manager = colrev.review_manager.ReviewManager(
                path_str=str(repo_source_path)
            )
            check_operation = colrev.operation.CheckOperation(
                review_manager=review_manager
            )
            if not check_operation.review_manager.dataset.records_file.is_file():
                return
            records = check_operation.review_manager.dataset.load_records_dict()

            # Add metadata_source_repository_paths : list of repositories from which
            # the record was integrated. Important for is_duplicate(...)
            for record in records.values():
                record.update(metadata_source_repository_paths=repo_source_path)

            curation_endpoints = [
                x
                for x in check_operation.review_manager.settings.data.data_package_endpoints
                if x["endpoint"] == "colrev_built_in.colrev_curation"
            ]
            if curation_endpoints:
                curation_endpoint = curation_endpoints[0]
                # Set masterdata_provenace to CURATED:{url}
                curation_url = curation_endpoint["curation_url"]
                if check_operation.review_manager.settings.is_curated_masterdata_repo():
                    for record in records.values():
                        record.update(
                            colrev_masterdata_provenance=f"CURATED:{curation_url};;"
                        )

                # Add curation_url to curated fields (provenance)
                curated_fields = curation_endpoint["curated_fields"]
                for curated_field in curated_fields:

                    for record_dict in records.values():
                        colrev.record.Record(data=record_dict).add_data_provenance(
                            key=curated_field, source=f"CURATED:{curation_url}"
                        )

            # Set absolute file paths (for simpler retrieval)
            for record in records.values():
                if "file" in record:
                    record.update(file=repo_source_path / Path(record["file"]))

            for record_dict in tqdm(records.values()):
                try:
                    self.index_record(record_dict=record_dict)
                except colrev_exceptions.RecordNotIndexableException:
                    pass

        except (colrev_exceptions.InvalidSettingsError) as exc:
            print(exc)

    def index(self, *, index_tei: bool = False) -> None:
        """Index all registered CoLRev projects"""
        # import shutil

        self.__index_tei = index_tei

        # Note : this task takes long and does not need to run often
        session = requests_cache.CachedSession(
            str(colrev.env.environment_manager.EnvironmentManager.cache_path),
            backend="sqlite",
            expire_after=timedelta(days=30),
        )
        # Note : lambda is necessary to prevent immediate function call
        # pylint: disable=unnecessary-lambda
        Timer(0.1, lambda: session.remove_expired_responses()).start()

        print("Start LocalIndex")

        if self.__outlets_duplicated():
            return

        print(f"Reset {self.RECORD_INDEX} and {self.TOC_INDEX}")
        # if self.teiind_path.is_dir():
        #     shutil.rmtree(self.teiind_path)

        available_indices = self.open_search.indices.get_alias().keys()
        self.opensearch_index.mkdir(exist_ok=True, parents=True)
        if self.RECORD_INDEX in available_indices:
            self.open_search.indices.delete(index=self.RECORD_INDEX)
        if self.TOC_INDEX in available_indices:
            self.open_search.indices.delete(index=self.TOC_INDEX)
        if self.AUTHOR_INDEX in available_indices:
            self.open_search.indices.delete(index=self.AUTHOR_INDEX)
        if self.AUTHOR_RECORD_INDEX in available_indices:
            self.open_search.indices.delete(index=self.AUTHOR_RECORD_INDEX)
        if self.CITATIONS_INDEX in available_indices:
            self.open_search.indices.delete(index=self.CITATIONS_INDEX)
        self.open_search.indices.create(index=self.RECORD_INDEX)
        self.open_search.indices.create(index=self.TOC_INDEX)
        self.open_search.indices.create(index=self.AUTHOR_INDEX)
        self.open_search.indices.create(index=self.AUTHOR_RECORD_INDEX)
        self.open_search.indices.create(index=self.CITATIONS_INDEX)

        repo_source_paths = [
            x["repo_source_path"]
            for x in self.environment_manager.load_environment_registry()
        ]
        for repo_source_path in repo_source_paths:
            self.index_colrev_project(repo_source_path=repo_source_path)

        # for annotator in self.annotators_path.glob("*/annotate.py"):
        #     print(f"Load {annotator}")

        #     annotator_module = ....load_source("annotator_module", str(annotator))
        #     annotate = getattr(annotator_module, "annotate")
        #     annotate(self)
        # Note : es.update can use functions applied to each record (for the update)

    def get_year_from_toc(self, *, record_dict: dict) -> str:
        """Determine the year of a paper based on its table-of-content (journal-volume-number)"""
        open_search_thread_instance = OpenSearch(self.OPENSEARCH_URL)

        try:
            toc_key = colrev.record.Record(data=record_dict).get_toc_key()
            toc_items = []
            if open_search_thread_instance.exists(index=self.TOC_INDEX, id=toc_key):
                res = self.__retrieve_toc_index(toc_key=toc_key)
                toc_items = res.get("colrev_ids", [])  # type: ignore

            if not toc_items:
                raise colrev_exceptions.TOCNotAvailableException()

            toc_records_colrev_id = toc_items[0]
            paper_hash = hashlib.sha256(
                toc_records_colrev_id.encode("utf-8")
            ).hexdigest()
            res = open_search_thread_instance.get(
                index=self.RECORD_INDEX,
                id=str(paper_hash),
            )
            record_dict = res["_source"]  # type: ignore
            year = record_dict.get("year", "NA")

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            TransportError,
            SerializationError,
            colrev_exceptions.NotTOCIdentifiableException,
        ) as exc:
            raise colrev_exceptions.TOCNotAvailableException() from exc

        return year

    def retrieve_from_toc(
        self,
        *,
        record_dict: dict,
        similarity_threshold: float,
        include_file: bool = False,
        search_across_tocs: bool = False,
    ) -> dict:
        """Retrieve a record from the toc (table-of-contents)"""

        # pylint: disable=too-many-locals
        # pylint: disable=too-many-branches

        try:
            toc_key = colrev.record.Record(data=record_dict).get_toc_key()
        except colrev_exceptions.NotTOCIdentifiableException as exc:
            if not search_across_tocs:
                raise colrev_exceptions.RecordNotInIndexException() from exc

        open_search_thread_instance = OpenSearch(self.OPENSEARCH_URL)
        # 1. get TOC
        if search_across_tocs:
            try:
                toc_items: typing.List[str] = []
                partial_toc_key = colrev.record.Record(data=record_dict).get_toc_key()
                # pylint: disable=unexpected-keyword-arg
                resp = self.open_search.search(
                    index=self.TOC_INDEX,
                    body={
                        "query": {
                            "match_phrase": {
                                "toc_key": partial_toc_key.replace("|UNKNOWN", "") + "|"
                            }
                        }
                    },
                    size=2000,
                )

                retrieved_tocs = resp["hits"]["hits"]
                if "hits" not in resp["hits"]:
                    raise colrev_exceptions.RecordNotInIndexException()

                toc_items = [
                    z
                    for x in retrieved_tocs
                    for y, z in x["_source"].items()
                    if y == "colrev_ids"
                ]
                toc_items = [item for sublist in toc_items for item in sublist]

            except (
                colrev_exceptions.NotTOCIdentifiableException,
                TransportError,
                KeyError,
            ) as exc:
                raise colrev_exceptions.RecordNotInIndexException() from exc

        else:
            toc_items = []
            if open_search_thread_instance.exists(index=self.TOC_INDEX, id=toc_key):
                try:
                    res = self.__retrieve_toc_index(toc_key=toc_key)
                    toc_items = res.get("colrev_ids", [])  # type: ignore
                except (TransportError, SerializationError, NotFoundError):
                    toc_items = []

        if not toc_items:
            raise colrev_exceptions.RecordNotInIndexException()

        # 2. get most similar record_dict
        try:
            if search_across_tocs:
                record_colrev_id = colrev.record.Record(
                    data=record_dict
                ).create_colrev_id(assume_complete=True)

            else:
                record_colrev_id = colrev.record.Record(
                    data=record_dict
                ).create_colrev_id()
            sim_list = []

            for toc_records_colrev_id in toc_items:
                # Note : using a simpler similarity measure
                # because the publication outlet parameters are already identical
                sim_value = fuzz.ratio(record_colrev_id, toc_records_colrev_id) / 100
                sim_list.append(sim_value)

            if max(sim_list) > similarity_threshold:
                if search_across_tocs:
                    second_highest = list(set(sim_list))[-2]
                    # Require a minimum difference to the next most similar record
                    if (max(sim_list) - second_highest) < 0.2:
                        raise colrev_exceptions.RecordNotInIndexException()

                toc_records_colrev_id = toc_items[sim_list.index(max(sim_list))]
                paper_hash = hashlib.sha256(
                    toc_records_colrev_id.encode("utf-8")
                ).hexdigest()
                res = open_search_thread_instance.get(
                    index=self.RECORD_INDEX,
                    id=str(paper_hash),
                )
                record_dict = res["_source"]  # type: ignore
                return self.__prepare_record_for_return(
                    record_dict=record_dict, include_file=include_file
                )

            raise colrev_exceptions.RecordNotInTOCException(
                record_id=record_dict["ID"], toc_key=toc_key
            )

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            KeyError,
            NotFoundError,
            TransportError,
        ):
            pass

        raise colrev_exceptions.RecordNotInIndexException()

    def __get_from_index_exact_match(
        self, *, index_name: str, key: str, value: str
    ) -> dict:

        res = {}
        try:
            open_search_thread_instance = OpenSearch(self.OPENSEARCH_URL)
            resp = open_search_thread_instance.search(
                index=index_name,
                body={"query": {"match_phrase": {key: value}}},
            )
            res = resp["hits"]["hits"][0]["_source"]
        except (
            JSONDecodeError,
            NotFoundError,
            TransportError,
            SerializationError,
            KeyError,
        ):
            pass
        return res

    def retrieve_based_on_colrev_pdf_id(self, *, colrev_pdf_id: str) -> dict:
        """
        Convenience function to retrieve the indexed record_dict metadata
        based on a colrev_pdf_id
        """

        query = {
            "query": {
                "simple_query_string": {
                    "query": colrev_pdf_id,
                    "fields": ["colrev_pdf_id"],
                },
            }
        }

        # pylint: disable=unexpected-keyword-arg
        res = self.open_search.search(
            index=self.RECORD_INDEX,
            body=query,
            size=1,
        )
        try:
            record_dict = res["hits"]["hits"][0]["_source"]

            if colrev_pdf_id != record_dict["colrev_pdf_id"]:
                raise colrev_exceptions.RecordNotInIndexException()
        except KeyError as exc:
            raise colrev_exceptions.RecordNotInIndexException() from exc

        record_to_import = self.__prepare_record_for_return(
            record_dict=record_dict, include_file=True
        )
        if "file" in record_to_import:
            del record_to_import["file"]
        return record_to_import

    def retrieve(
        self,
        *,
        record_dict: dict,
        include_file: bool = False,
        include_colrev_ids: bool = False,
    ) -> dict:
        """
        Convenience function to retrieve the indexed record_dict metadata
        based on another record_dict
        """

        retrieved_record_dict: typing.Dict = {}

        # 1. Try the record index
        try:
            retrieved_record_dict = self.__retrieve_from_record_index(
                record_dict=record_dict
            )
        except (
            NotFoundError,
            colrev_exceptions.RecordNotInIndexException,
            colrev_exceptions.NotEnoughDataToIdentifyException,
            TransportError,
            SerializationError,
        ):
            pass
        if retrieved_record_dict:
            return self.__prepare_record_for_return(
                record_dict=retrieved_record_dict,
                include_file=include_file,
                include_colrev_ids=include_colrev_ids,
            )

        # 2. Try using global-ids
        if not retrieved_record_dict:
            for key, value in record_dict.items():
                if key not in self.global_keys or "ID" == key:
                    continue
                try:
                    retrieved_record_dict = self.__get_from_index_exact_match(
                        index_name=self.RECORD_INDEX, key=key, value=value
                    )
                    break
                except (
                    IndexError,
                    NotFoundError,
                    JSONDecodeError,
                    KeyError,
                    TransportError,
                    SerializationError,
                ):
                    pass
        if not retrieved_record_dict:
            raise colrev_exceptions.RecordNotInIndexException(
                record_dict.get("ID", "no-key")
            )

        return self.__prepare_record_for_return(
            record_dict=retrieved_record_dict,
            include_file=include_file,
            include_colrev_ids=include_colrev_ids,
        )

    def is_duplicate(self, *, record1_colrev_id: list, record2_colrev_id: list) -> str:
        """Convenience function to check whether two records are a duplicate"""

        try:

            # Ensure that we receive actual lists
            # otherwise, __retrieve_based_on_colrev_id iterates over a string and
            # open_search_thread_instance.search returns random results
            assert isinstance(record1_colrev_id, list)
            assert isinstance(record2_colrev_id, list)

            # Prevent errors caused by short colrev_ids/empty lists
            if (
                any(len(cid) < 20 for cid in record1_colrev_id)
                or any(len(cid) < 20 for cid in record2_colrev_id)
                or 0 == len(record1_colrev_id)
                or 0 == len(record2_colrev_id)
            ):
                return "unknown"

            # Easy case: the initial colrev_ids overlap => duplicate
            initial_colrev_ids_overlap = not set(record1_colrev_id).isdisjoint(
                list(record2_colrev_id)
            )
            if initial_colrev_ids_overlap:
                return "yes"

            # Retrieve records from LocalIndex and use that information
            # to decide whether the records are duplicates

            r1_index = self.__retrieve_based_on_colrev_id(
                cids_to_retrieve=record1_colrev_id
            )
            r2_index = self.__retrieve_based_on_colrev_id(
                cids_to_retrieve=record2_colrev_id
            )
            # Each record may originate from multiple repositories simultaneously
            # see integration of records in __amend_record(...)
            # This information is stored in metadata_source_repository_paths (list)

            r1_metadata_source_repository_paths = r1_index[
                "metadata_source_repository_paths"
            ].split("\n")
            r2_metadata_source_repository_paths = r2_index[
                "metadata_source_repository_paths"
            ].split("\n")

            # There are no duplicates within repositories
            # because we only index records that are md_processed or beyond
            # see conditions of index_record(...)

            # The condition that two records are in the same repository is True if
            # their metadata_source_repository_paths overlap.
            # This does not change if records are also in non-overlapping repositories

            same_repository = not set(r1_metadata_source_repository_paths).isdisjoint(
                set(r2_metadata_source_repository_paths)
            )

            # colrev_ids must be used instead of IDs
            # because IDs of original repositories
            # are not available in the integrated record

            colrev_ids_overlap = not set(
                colrev.record.Record(data=r1_index).get_colrev_id()
            ).isdisjoint(
                list(list(colrev.record.Record(data=r2_index).get_colrev_id()))
            )

            if same_repository:
                if colrev_ids_overlap:
                    return "yes"
                return "no"

            # Curated metadata repositories do not curate outlets redundantly,
            # i.e., there are no duplicates between curated repositories.
            # see __outlets_duplicated(...)

            different_curated_repositories = (
                "CURATED:" in r1_index.get("colrev_masterdata_provenance", "")
                and "CURATED:" in r2_index.get("colrev_masterdata_provenance", "")
                and (
                    r1_index.get("colrev_masterdata_provenance", "a")
                    != r2_index.get("colrev_masterdata_provenance", "b")
                )
            )

            if different_curated_repositories:
                return "no"

        except (
            colrev_exceptions.RecordNotInIndexException,
            NotFoundError,
            colrev_exceptions.NotEnoughDataToIdentifyException,
        ):
            pass

        return "unknown"


if __name__ == "__main__":
    pass
