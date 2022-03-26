#! /usr/bin/env python
import binascii
import hashlib
import os
import re
import time
import typing
import unicodedata
from pathlib import Path

import docker
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import convert_to_unicode
from elastic_transport import ConnectionError
from elasticsearch import Elasticsearch
from elasticsearch import NotFoundError
from git.exc import InvalidGitRepositoryError
from nameparser import HumanName
from thefuzz import fuzz
from tqdm import tqdm

from colrev_core.process import CheckProcess
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.process import RecordState
from colrev_core.review_manager import ReviewManager
from colrev_core.tei import TEI
from colrev_core.tei import TEI_Exception


class LocalIndex(Process):

    global_keys = ["doi", "dblp_key", "pdf_hash", "url"]
    max_len_sha256 = 2 ** 256

    local_index_path = Path.home().joinpath("colrev")
    toc_overview = local_index_path / Path(".toc_index/readme.md")
    teiind_path = local_index_path / Path(".tei_index/")
    annotators_path = local_index_path / Path("annotators")
    elastic_index = local_index_path / Path("index")

    def __init__(self, REVIEW_MANAGER, notify_state_transition_process=False):

        super().__init__(
            REVIEW_MANAGER,
            ProcessType.explore,
            notify_state_transition_process=False,
        )
        self.local_registry = self.REVIEW_MANAGER.load_local_registry()
        self.local_repos = self.__load_local_repos()
        es_image = self.REVIEW_MANAGER.docker_images[
            "docker.elastic.co/elasticsearch/elasticsearch"
        ]

        client = docker.from_env()
        try:
            client.containers.run(
                es_image,
                name="elasticsearch",
                ports={"9200/tcp": ("127.0.0.1", 9200)},
                auto_remove=True,
                detach=True,
                environment={
                    "bootstrap.memory_lock": "true",
                    "ES_JAVA_OPTS": "-Xms512m -Xmx512m",
                    "discovery.type": "single-node",
                    "ingest.geoip.downloader.enabled": "false",
                    "xpack.security.enabled": "false",
                    "xpack.security.http.ssl.enabled": "false",
                    "xpack.security.transport.ssl.enabled": "false",
                },
                volumes={
                    str(self.elastic_index): {
                        "bind": "/usr/share/elasticsearch/data",
                        "mode": "rw",
                    }
                },
            )
        except docker.errors.APIError:
            pass

        self.es = Elasticsearch("http://localhost:9200")
        i = 0
        while i < 20:
            try:
                self.es.get(index="record_index", id="test")
                break
            except ConnectionError:
                if i == 0:
                    print("Start LocalIndex")
                time.sleep(3)
                print("Waiting until LocalIndex is available")
                pass
            except NotFoundError:
                pass
                break
        # If not available after 120s: raise error
        self.es.info()
        # self.REVIEW_MANAGER.pp.pprint(self.es.info())

    def __load_local_repos(self) -> typing.List:
        from git.exc import NoSuchPathError
        from git.exc import InvalidGitRepositoryError

        local_repo_list = []
        sources = [x for x in self.local_registry]
        for source in sources:
            try:
                if not Path(source["source_url"]).is_dir():
                    continue
                cp_REVIEW_MANAGER = ReviewManager(path_str=source["source_url"])
                CheckProcess(cp_REVIEW_MANAGER)  # to notify
                repo = {
                    "source_url": str(cp_REVIEW_MANAGER.path),
                }
                remote_url = cp_REVIEW_MANAGER.get_remote_url()
                if remote_url is not None:
                    repo["source_link"] = remote_url
                local_repo_list.append(repo)
            except (NoSuchPathError, InvalidGitRepositoryError):
                pass
                continue
        return local_repo_list

    def __robust_append(self, string_to_hash: str, to_append: str) -> str:
        to_append = to_append.replace("\n", " ").rstrip().lstrip().replace("–", " ")
        to_append = re.sub(r"[\.\:“”’]", "", to_append)
        to_append = re.sub(r"\s+", " ", to_append)
        to_append = to_append.lower()
        string_to_hash = string_to_hash + "|" + to_append
        return string_to_hash

    def __rmdiacritics(self, char):
        """
        Return the base character of char, by "removing" any
        diacritics like accents or curls and strokes and the like.
        """
        try:
            desc = unicodedata.name(char)
            cutoff = desc.find(" WITH ")
            if cutoff != -1:
                desc = desc[:cutoff]
                char = unicodedata.lookup(desc)
        except (KeyError, ValueError):
            pass  # removing "WITH ..." produced an invalid name
        return char

    def __remove_accents(self, input_str: str) -> str:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac = [
            self.__rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac_str = "".join(wo_ac)
        return wo_ac_str

    def __get_container_title(self, record: dict) -> str:

        # if multiple container titles are available, they are concatenated
        container_title = ""

        # school as the container title for theses
        if "school" in record:
            container_title += record["school"]
        # for technical reports
        if "institution" in record:
            container_title += record["institution"]
        if "series" in record:
            container_title += record["series"]
        if "booktitle" in record:
            container_title += record["booktitle"]
        if "journal" in record:
            container_title += record["journal"]

        if "url" in record and not any(
            x in record for x in ["journal", "series", "booktitle"]
        ):
            container_title += record["url"]

        return container_title

    def __format_author_field(self, input_string: str) -> str:
        input_string = input_string.replace("\n", " ")
        names = (
            self.__remove_accents(input_string).replace("; ", " and ").split(" and ")
        )
        author_list = []
        for name in names:
            parsed_name = HumanName(name)
            # Note: do not set this as a global constant to preserve consistent
            # creation of hash_ids
            parsed_name.string_format = "{last}, {first} {middle}"
            if len(parsed_name.middle) > 0:
                parsed_name.middle = parsed_name.middle[:1]
            if len(parsed_name.first) > 0:
                parsed_name.first = parsed_name.first[:1]
            if len(parsed_name.nickname) > 0:
                parsed_name.nickname = ""

            if "," not in str(parsed_name):
                author_list.append(str(parsed_name))
                continue
            author_list.append(str(parsed_name))
        return " and ".join(author_list)

    def get_string_representation(self, record: dict) -> str:

        # Including the version of the hash_function prevents cases
        # in which almost all hash_ids are identical (and very few hash_ids change)
        # when updatingthe hash function
        # (this may look like an anomaly and be hard to identify)
        srep = "v0.1"
        author = record.get("author", "")
        srep = self.__robust_append(srep, record.get("ENTRYTYPE", "NA").lower())
        srep = self.__robust_append(srep, self.__format_author_field(author))
        srep = self.__robust_append(srep, record.get("year", ""))
        title_str = re.sub("[^0-9a-zA-Z]+", " ", record.get("title", ""))
        srep = self.__robust_append(srep, title_str)
        srep = self.__robust_append(srep, self.__get_container_title(record))
        srep = self.__robust_append(srep, record.get("volume", ""))
        srep = self.__robust_append(srep, record.get("number", ""))
        pages = record.get("pages", "")
        srep = self.__robust_append(srep, pages)

        return srep

    def __get_record_hash(self, record: dict) -> str:
        string_to_hash = self.get_string_representation(record)
        return hashlib.sha256(string_to_hash.encode("utf-8")).hexdigest()

    def __increment_hash(self, hash: str) -> str:

        plaintext = binascii.unhexlify(hash)
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

    def __get_tei_index_file(self, hash: str) -> Path:
        return self.local_index_path / Path(f".tei_index/{hash[:2]}/{hash[2:]}.tei.xml")

    def __store_record(self, hash: str, record: dict) -> None:

        # Casting to string (in particular the RecordState Enum)
        record = {k: str(v) for k, v in record.items()}

        if "file" in record:
            try:
                tei_path = self.__get_tei_index_file(hash)
                tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                if Path(record["file"]).is_file():
                    TEI_INSTANCE = TEI(
                        self.REVIEW_MANAGER,
                        pdf_path=Path(record["file"]),
                        tei_path=tei_path,
                        notify_state_transition_process=False,
                    )
                    record["fulltext"] = TEI_INSTANCE.get_tei_str()
            except (TEI_Exception, AttributeError):
                pass

        self.es.index(index="record_index", id=hash, document=record)

        return

    def __retrieve_from_toc_index_based_on_hash(self, hash: str) -> list:

        toc_item_response = self.es.get(index="toc_index", id=hash)
        toc_item = toc_item_response["_source"]

        return toc_item

    def __amend_record(self, hash: str, record: dict) -> None:

        saved_record_response = self.es.get(index="record_index", id=hash)
        saved_record = saved_record_response["_source"]

        # amend saved record
        for k, v in record.items():
            if k in saved_record:
                continue
            saved_record[k] = v

        if "file" in record and "fulltext" not in saved_record:
            try:
                tei_path = self.__get_tei_index_file(hash)
                tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                if Path(record["file"]).is_file():
                    TEI_INSTANCE = TEI(
                        self.REVIEW_MANAGER,
                        pdf_path=Path(record["file"]),
                        tei_path=tei_path,
                        notify_state_transition_process=False,
                    )
                    saved_record["fulltext"] = TEI_INSTANCE.get_tei_str()
            except (TEI_Exception, AttributeError):
                pass

        self.es.update(index="record_index", id=hash, doc=saved_record)
        return

    def __record_index(self, record: dict) -> None:
        record = {k: str(v) for k, v in record.items()}
        hash = self.__get_record_hash(record)

        string_representation = self.get_string_representation(record)
        record["hash_string_representation"] = string_representation

        try:
            # check if the record is already indexed (based on d)
            retrieved_record = self.retrieve_record_from_index(record)

            # if the string_representations are not identical: add to d_index
            if not self.get_string_representation(
                retrieved_record
            ) == self.get_string_representation(record):
                # Note: we need the hash of the retrieved_record (different from record)
                self.__amend_record(self.__get_record_hash(retrieved_record), record)
                return
        except RecordNotInIndexException:
            pass

        while True:
            if not self.es.exists(index="record_index", id=hash):
                self.__store_record(hash, record)
                break
            else:
                saved_record_response = self.es.get(index="record_index", id=hash)
                saved_record = saved_record_response["_source"]
                if string_representation == self.get_string_representation(
                    saved_record
                ):
                    # ok - no collision, update the record
                    # Note : do not update (the record from the first repository
                    # should take precedence - reset the index to update)
                    self.__amend_record(hash, record)
                    break
                else:
                    # to handle the collision:
                    print(f"Collision: {hash}")
                    print(string_representation)
                    print(self.get_string_representation(saved_record))
                    print(saved_record)
                    hash = self.__increment_hash(hash)

        return

    def __get_toc_key(self, record: dict) -> str:
        toc_key = "NA"
        if "article" == record["ENTRYTYPE"]:
            toc_key = f"{record.get('journal', '').lower()}"
            if "volume" in record:
                toc_key = toc_key + f"|{record['volume']}"
            if "number" in record:
                toc_key = toc_key + f"|{record['number']}"
            else:
                toc_key = toc_key + "|"
        elif "inproceedings" == record["ENTRYTYPE"]:
            toc_key = (
                f"{record.get('booktitle', '').lower()}" + f"|{record.get('year', '')}"
            )

        return toc_key

    def __toc_index(self, record) -> None:

        if record.get("ENTRYTYPE", "") in ["article", "inproceedings"]:
            # Note : records are md_prepared, i.e., complete

            toc_key = self.__get_toc_key(record)
            if "NA" == toc_key:
                return

            # print(toc_key)
            hash = hashlib.sha256(toc_key.encode("utf-8")).hexdigest()
            record_string_repr = self.get_string_representation(record)
            while True:
                if not self.es.exists(index="toc_index", id=hash):
                    toc_item = {
                        "toc_key": toc_key,
                        "string_representations": [record_string_repr],
                    }
                    self.es.index(index="toc_index", id=hash, document=toc_item)
                    break
                else:
                    toc_item_response = self.es.get(index="toc_index", id=hash)
                    toc_item = toc_item_response["_source"]
                    if toc_item["toc_key"] == toc_key:
                        # ok - no collision, update the record
                        # Note : do not update (the record from the first repository
                        #  should take precedence - reset the index to update)
                        if record_string_repr not in toc_item["string_representations"]:
                            toc_item["string_representations"].append(  # type: ignore
                                record_string_repr
                            )
                            self.es.update(index="toc_index", id=hash, doc=toc_item)
                        break
                    else:
                        # to handle the collision:
                        print(f"Collision: {hash}")
                        hash = self.__increment_hash(hash)

        return

    def __append_j_variation(
        self, j_variations: list, origin_record: dict, record: dict
    ) -> list:

        if "journal" not in origin_record or "journal" not in record:
            return j_variations
        else:
            if origin_record["journal"] != record["journal"]:
                j_variations.append([origin_record["journal"], record["journal"]])

        return j_variations

    def __append_if_duplicate_repr(
        self, non_identical_representations: list, origin_record: dict, record: dict
    ) -> list:

        required_fields = [
            k
            for k, v in record.items()
            if k
            in [
                "author",
                "title",
                "year",
                "journal",
                "volume",
                "number",
                "pages",
                "booktitle",
            ]
        ]

        if all(required_field in origin_record for required_field in required_fields):
            orig_repr = self.get_string_representation(origin_record)
            main_repr = self.get_string_representation(record)
            if orig_repr != main_repr:
                non_identical_representations.append([orig_repr, main_repr])

        return non_identical_representations

    def __add_to_d_index(self, non_identical_representations: list) -> None:
        non_identical_representations = [
            list(x) for x in {tuple(x) for x in non_identical_representations}
        ]
        if len(non_identical_representations) > 0:

            for (
                non_identical_representation,
                orig_record_string,
            ) in non_identical_representations:

                hash = hashlib.sha256(orig_record_string.encode("utf-8")).hexdigest()
                while True:
                    if not self.es.exists(index="record_index", id=hash):
                        # Note : this should happen rarely/never
                        break
                    else:
                        response = self.es.get(index="record_index", id=hash)
                        saved_record = response["_source"]
                        saved_original_string_repr = saved_record[
                            "hash_string_representation"
                        ]

                        if saved_original_string_repr == orig_record_string:
                            # ok - no collision
                            if non_identical_representation not in saved_record.get(
                                "duplicate_reprs", []
                            ):
                                if "duplicate_reprs" in saved_record:
                                    saved_record["duplicate_reprs"].append(
                                        non_identical_representation
                                    )
                                else:
                                    saved_record["duplicate_reprs"] = [
                                        non_identical_representation
                                    ]
                                self.es.update(
                                    index="record_index", id=hash, doc=saved_record
                                )
                            break
                        else:
                            # to handle the collision:
                            print(f"Collision: {hash}")
                            hash = self.__increment_hash(hash)
        return

    def __d_index(self, records: typing.List[dict]) -> None:

        try:
            search_path = Path(records[0]["source_url"] + "/search/")
        except IndexError:
            pass
            return

        self.REVIEW_MANAGER.logger.info(f"Update d_index for {search_path.parent}")

        # Note : records are at least md_processed.
        duplicate_repr_list = []
        for record in records:
            for orig in record["origin"].split(";"):
                duplicate_repr_list.append(
                    {
                        "origin_source": orig.split("/")[0],
                        "origin_id": orig.split("/")[1],
                        "record": record,
                    }
                )

        if len(duplicate_repr_list) == 0:
            return

        origin_sources = list({x["origin_source"] for x in duplicate_repr_list})
        non_identical_representations: typing.List[list] = []
        j_variations: typing.List[list] = []
        for origin_source in origin_sources:
            os_fp = search_path / Path(origin_source)
            if not os_fp.is_file():
                print(f"source not found {os_fp}")
            else:
                with open(os_fp) as target_db:
                    bib_db = BibTexParser(
                        customization=convert_to_unicode,
                        ignore_nonstandard_types=False,
                        common_strings=True,
                    ).parse_file(target_db, partial=True)

                    origin_source_records = bib_db.entries
                for duplicate_repr in duplicate_repr_list:
                    if duplicate_repr["origin_source"] != origin_source:
                        continue

                    record = duplicate_repr["record"]
                    origin_record_list = [
                        x
                        for x in origin_source_records
                        if x["ID"] == duplicate_repr["origin_id"]
                    ]
                    if len(origin_record_list) != 1:
                        continue
                    origin_record = origin_record_list[0]
                    non_identical_representations = self.__append_if_duplicate_repr(
                        non_identical_representations, origin_record, record
                    )
                    j_variations = self.__append_j_variation(
                        j_variations, origin_record, record
                    )

        # 2. add representations to index
        self.__add_to_d_index(non_identical_representations)

        return

    def __retrieve_record_from_d_index(self, record: dict) -> dict:

        string_representation_record = self.get_string_representation(record)

        try:
            # match_phrase := exact match
            resp = self.es.search(
                index="record_index",
                query={
                    "match_phrase": {"duplicate_reprs": string_representation_record}
                },
            )
            retrieved_record = resp["hits"]["hits"][0]["_source"]

        except (IndexError, NotFoundError):
            pass
            raise RecordNotInIndexException

        if retrieved_record["ENTRYTYPE"] != record["ENTRYTYPE"]:
            raise RecordNotInIndexException

        return self.prep_record_for_return(retrieved_record)

    def __retrieve_from_record_index(self, record: dict) -> dict:
        string_representation = self.get_string_representation(record)
        retrieved_record = self.__retrieve_from_record_index_string_repr(
            string_representation
        )
        if retrieved_record["ENTRYTYPE"] != record["ENTRYTYPE"]:
            raise RecordNotInIndexException
        return retrieved_record

    def __retrieve_from_record_index_string_repr(
        self, string_representation: str
    ) -> dict:

        hash = hashlib.sha256(string_representation.encode("utf-8")).hexdigest()

        while True:  # Note : while breaks with NotFoundError
            res = self.es.get(index="record_index", id=hash)
            retrieved_record = res["_source"]
            if (
                self.get_string_representation(retrieved_record)
                == string_representation
            ):
                break
            hash = self.__increment_hash(hash)

        return retrieved_record

    def prep_record_for_return(self, record: dict) -> dict:
        from colrev_core.process import RecordState

        if "hash_string_representation" in record:
            del record["hash_string_representation"]
        # del retrieved_record['source_url']
        if "file" in record:
            if not Path(record["file"]).is_file():
                dir_path = Path(record["source_url"]) / Path(record["file"])
                if dir_path.is_file():
                    record["file"] = str(dir_path)
                pdf_dir_path = (
                    Path(record["source_url"])
                    / self.REVIEW_MANAGER.paths["PDF_DIRECTORY_RELATIVE"]
                    / Path(record["file"])
                )
                if pdf_dir_path.is_file():
                    record["file"] = str(pdf_dir_path)

        if "manual_non_duplicate" in record:
            del record["manual_non_duplicate"]
        if "duplicate_reprs" in record:
            del record["duplicate_reprs"]
        record["status"] = RecordState.md_prepared
        return record

    def duplicate_outlets(self) -> bool:
        import collections

        self.REVIEW_MANAGER.logger.info("Validate curated metadata")

        curated_outlets = []
        for source_url in [
            x["source_url"]
            for x in self.local_registry
            if "colrev/curated_metadata/" in x["source_url"]
        ]:
            with open(f"{source_url}/readme.md") as f:
                first_line = f.readline()
            curated_outlets.append(first_line.lstrip("# ").replace("\n", ""))

            with open(f"{source_url}/references.bib") as r:
                outlets = []
                for line in r.readlines():

                    if "journal" == line.lstrip()[:7]:
                        journal = line[line.find("{") + 1 : line.rfind("}")]
                        outlets.append(journal)
                    if "booktitle" == line.lstrip()[:9]:
                        booktitle = line[line.find("{") + 1 : line.rfind("}")]
                        outlets.append(booktitle)

                if len(set(outlets)) != 1:
                    self.REVIEW_MANAGER.logger.error(
                        "Duplicate outlets in curated_metadata of "
                        f"{source_url} : {','.join(list(set(outlets)))}"
                    )
                    return True

        if len(curated_outlets) != len(set(curated_outlets)):
            duplicated = [
                item
                for item, count in collections.Counter(curated_outlets).items()
                if count > 1
            ]
            self.REVIEW_MANAGER.logger.error(
                f"Duplicate outlets in curated_metadata : {','.join(duplicated)}"
            )
            return True

        return False

    def index_records(self) -> None:
        # import shutil

        self.REVIEW_MANAGER.logger.info("Start LocalIndex")

        if self.duplicate_outlets():
            return

        self.REVIEW_MANAGER.logger.info("Reset record_index and toc_index")
        # if self.teiind_path.is_dir():
        #     shutil.rmtree(self.teiind_path)

        self.elastic_index.mkdir(exist_ok=True, parents=True)
        if "record_index" in self.es.indices.get_alias().keys():
            self.es.indices.delete(index="record_index", ignore=[400, 404])
        if "toc_index" in self.es.indices.get_alias().keys():
            self.es.indices.delete(index="toc_index", ignore=[400, 404])
        self.es.indices.create(index="record_index")
        self.es.indices.create(index="toc_index")

        for source_url in [x["source_url"] for x in self.local_registry]:

            try:
                if not Path(source_url).is_dir():
                    print(f"Warning {source_url} not a directory")
                    continue
                os.chdir(source_url)
                self.REVIEW_MANAGER.logger.info(f"Index records from {source_url}")

                # get ReviewManager for project (after chdir)
                REVIEW_MANAGER = ReviewManager(path_str=str(source_url))
                CHECK_PROCESS = CheckProcess(REVIEW_MANAGER)

                if not CHECK_PROCESS.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                    continue

                records = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.load_records()
                records = [
                    r
                    for r in records
                    if r["status"]
                    not in [
                        RecordState.md_retrieved,
                        RecordState.md_imported,
                        RecordState.md_prepared,
                        RecordState.md_needs_manual_preparation,
                    ]
                ]

                for record in tqdm(records):
                    record["source_url"] = source_url
                    if "excl_criteria" in record:
                        del record["excl_criteria"]
                    # Note: if the pdf_hash has not been checked,
                    # we cannot use it for retrieval or preparation.
                    if record["status"] not in [
                        RecordState.pdf_prepared,
                        RecordState.rev_excluded,
                        RecordState.rev_included,
                        RecordState.rev_synthesized,
                    ]:
                        if "pdf_hash" in record:
                            del record["pdf_hash"]

                    del record["status"]

                    self.__record_index(record)

                    # Note : only use curated journal metadata for TOC indices
                    # otherwise, TOCs will be incomplete and affect retrieval
                    if "colrev/curated_metadata" in source_url:
                        self.__toc_index(record)

                self.__d_index(records)
            except InvalidGitRepositoryError:
                print(f"InvalidGitRepositoryError: {source_url}")
                pass

        # for annotator in self.annotators_path.glob("*/annotate.py"):
        #     print(f"Load {annotator}")
        #     import imp

        #     annotator_module = imp.load_source("annotator_module", str(annotator))
        #     annotate = getattr(annotator_module, "annotate")
        #     annotate(self)
        # TODO : es.update can use functions applied to each record (for the update)

        return

    def retrieve_record_from_toc_index(
        self, record: dict, similarity_threshold: float
    ) -> dict:
        toc_key = self.__get_toc_key(record)

        # 1. get TOC
        hash = hashlib.sha256(toc_key.encode("utf-8")).hexdigest()
        toc_items = []
        while True:
            if not self.es.exists(index="toc_index", id=hash):
                break
            else:
                res = self.__retrieve_from_toc_index_based_on_hash(hash)
                if toc_key == res["toc_key"]:  # type: ignore
                    toc_items = res["string_representations"]  # type: ignore
                    break
                else:
                    # to handle the collision:
                    print(f"Collision: {hash}")
                    hash = self.__increment_hash(hash)

        # 2. get most similar record
        record_string_repr = self.get_string_representation(record)
        if len(toc_items) > 0:
            sim_list = []
            for saved_toc_record_str_repr in toc_items:
                # Note : using a simpler similarity measure
                # because the publication outlet parameters are already identical
                sv = fuzz.ratio(record_string_repr, saved_toc_record_str_repr) / 100
                sim_list.append(sv)

            if max(sim_list) > similarity_threshold:
                saved_toc_record_str_repr = toc_items[sim_list.index(max(sim_list))]

                hash = hashlib.sha256(
                    saved_toc_record_str_repr.encode("utf-8")
                ).hexdigest()
                res = self.es.get(index="record_index", id=str(hash))
                record = res["_source"]  # type: ignore
                return self.prep_record_for_return(record)

        raise RecordNotInIndexException()
        return record

    def get_from_index_exact_match(self, index_name, key, value) -> dict:
        resp = self.es.search(index=index_name, query={"match_phrase": {key: value}})
        res = resp["hits"]["hits"][0]["_source"]
        return res

    def retrieve_record_from_index(self, record: dict) -> dict:
        """
        Convenience function to retrieve the indexed record metadata
        based on another record
        """

        retrieved_record: typing.Dict = dict()

        # 1. Try using global-ids
        if not retrieved_record:
            for k, v in record.items():
                if k not in self.global_keys or "ID" == k:
                    continue
                try:
                    retrieved_record = self.get_from_index_exact_match(
                        "record_index", k, v
                    )
                    break
                except (IndexError, NotFoundError):
                    pass

        if retrieved_record:
            self.REVIEW_MANAGER.logger.debug("Retrieved from g_id index")
            return self.prep_record_for_return(retrieved_record)

        # 2. Try the record index

        if not retrieved_record:
            try:
                retrieved_record = self.__retrieve_from_record_index(record)
            except (NotFoundError, RecordNotInIndexException):
                pass

        if retrieved_record:
            self.REVIEW_MANAGER.logger.debug("Retrieved from record index")
            return self.prep_record_for_return(retrieved_record)

        # 3. Try the duplicate representation index
        if not retrieved_record:
            try:
                retrieved_record = self.__retrieve_record_from_d_index(record)
            except FileNotFoundError:
                pass

        if not retrieved_record:
            raise RecordNotInIndexException(record.get("ID", "no-key"))

        self.REVIEW_MANAGER.logger.debug("Retrieved from d index")
        return self.prep_record_for_return(retrieved_record)

    def set_source_url_link(self, record: dict) -> dict:
        if "source_url" in record:
            for local_repo in self.local_repos:
                if local_repo["source_url"] == record["source_url"]:
                    if "source_link" in local_repo:
                        record["source_url"] = local_repo["source_link"]

        return record

    def set_source_path(self, record: dict) -> dict:
        if "source_url" in record:
            for local_repo in self.local_repos:
                if local_repo["source_link"] == record["source_url"]:
                    record["source_url"] = local_repo["source_url"]

        return record

    def is_duplicate(self, record1_string_repr: str, record2_string_repr: str) -> str:
        """Convenience function to check whether two records are a duplicate"""

        # Note : the retrieve_record_from_index also checks the d_index, i.e.,
        # if the IDs and source_urls are identical,
        # record1 and record2 have been mapped to the same record
        # if record1 and record2 in index (and same source_url): return 'no'
        try:
            r1_index = self.__retrieve_from_record_index_string_repr(
                record1_string_repr
            )
            r2_index = self.__retrieve_from_record_index_string_repr(
                record2_string_repr
            )
            if r1_index["source_url"] == r2_index["source_url"]:
                if r1_index["ID"] == r2_index["ID"]:
                    return "yes"
                else:
                    return "no"

            # Note : We know that records are not duplicates when they are
            # part of curated_metadata repositories and their IDs are not identical
            # For the same journal, only deduplicated records are indexed
            # We make sure that journals are only indexed once
            if (
                "colrev/curated_metadata" in r1_index["source_url"]
                and "colrev/curated_metadata" in r2_index["source_url"]
            ):
                if r1_index["ID"] != r2_index["ID"]:
                    return "no"

        except (RecordNotInIndexException, NotFoundError):
            pass
            return "unknown"

        return "unknown"

    def analyze(self, threshold: float = 0.95) -> None:

        # TODO : update based on es index
        # import pandas as pd

        # changes = []
        # for d_file in self.dind_path.rglob("*.txt"):
        #     str1, str2 = d_file.read_text().split("\n")
        #     similarity = fuzz.ratio(str1, str2) / 100
        #     if similarity < threshold:
        #         changes.append(
        #             {"similarity": similarity, "str": str1, "fname": str(d_file)}
        #         )
        #         changes.append(
        #             {"similarity": similarity, "str": str2, "fname": str(d_file)}
        #         )

        # df = pd.DataFrame(changes)
        # df = df.sort_values(by=["similarity", "fname"])
        # df.to_csv("changes.csv", index=False)
        # print("Exported changes.csv")

        # pdf_hashes = []
        # https://bit.ly/3tbypkd
        # for r_file in self.rind_path.rglob("*.bib"):

        #     with open(r_file) as f:
        #         while True:
        #             line = f.readline()
        #             if not line:
        #                 break
        #             if "pdf_hash" in line[:9]:
        #                 pdf_hashes.append(line[line.find("{") + 1 : line.rfind("}")])

        # import collections

        # pdf_hashes_dupes = [
        #     item for item, count in
        #       collections.Counter(pdf_hashes).items() if count > 1
        # ]

        # with open("non-unique-pdf-hashes.txt", "w") as o:
        #     o.write("\n".join(pdf_hashes_dupes))
        # print("Export non-unique-pdf-hashes.txt")
        return


class Resources:

    curations_path = Path.home().joinpath("colrev/curated_metadata")
    annotators_path = Path.home().joinpath("colrev/annotators")

    def __init__(self):
        pass

    def install_curated_resource(self, curated_resource: str) -> bool:
        import git
        import shutil

        # check if url else return False
        # validators.url(curated_resource)
        if "http" not in curated_resource:
            curated_resource = "https://github.com/" + curated_resource
        self.curations_path.mkdir(exist_ok=True, parents=True)
        repo_dir = self.curations_path / Path(curated_resource.split("/")[-1])
        annotator_dir = self.annotators_path / Path(curated_resource.split("/")[-1])
        if repo_dir.is_dir():
            print(f"Repo already exists ({repo_dir})")
            return False
        print(f"Download curated resource from {curated_resource}")
        git.Repo.clone_from(curated_resource, repo_dir, depth=1)

        if (repo_dir / Path("references.bib")).is_file():
            REVIEW_MANAGER = ReviewManager(path_str=str(repo_dir))
            REVIEW_MANAGER.register_repo()
        elif (repo_dir / Path("annotate.py")).is_file():
            shutil.move(str(repo_dir), str(annotator_dir))
        elif (repo_dir / Path("readme.md")).is_file():
            text = Path(repo_dir / "readme.md").read_text()
            for line in [x for x in text.splitlines() if "colrev env --install" in x]:
                if line == curated_resource:
                    continue
                self.install_curated_resource(line.replace("colrev env --install ", ""))
        else:
            print(
                f"Error: repo does not contain a references.bib/linked repos {repo_dir}"
            )
        return True


class RecordNotInIndexException(Exception):
    def __init__(self, id: str = None):
        if id is not None:
            self.message = f"Record not in index ({id})"
        else:
            self.message = "Record not in index"
        super().__init__(self.message)


if __name__ == "__main__":
    pass
