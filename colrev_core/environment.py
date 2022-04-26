#! /usr/bin/env python
import binascii
import hashlib
import logging
import os
import time
import typing
from pathlib import Path

import docker
from git.exc import InvalidGitRepositoryError
from lxml.etree import SerialisationError
from opensearchpy import NotFoundError
from opensearchpy import OpenSearch
from opensearchpy.exceptions import ConnectionError
from opensearchpy.exceptions import TransportError
from thefuzz import fuzz
from tqdm import tqdm

from colrev_core.process import CheckProcess
from colrev_core.record import NotEnoughDataToIdentifyException
from colrev_core.record import Record
from colrev_core.record import RecordState
from colrev_core.tei import TEI
from colrev_core.tei import TEI_Exception


class EnvironmentManager:

    colrev_path = Path.home().joinpath("colrev")
    registry = "registry.yaml"

    paths = {"REGISTRY": colrev_path.joinpath(registry)}

    os_db = "opensearchproject/opensearch-dashboards:1.3.0"

    docker_images = {
        "lfoppiano/grobid": "lfoppiano/grobid:0.7.0",
        "pandoc/ubuntu-latex": "pandoc/ubuntu-latex:2.14",
        "jbarlow83/ocrmypdf": "jbarlow83/ocrmypdf:v13.3.0",
        "zotero/translation-server": "zotero/translation-server:2.0.4",
        "opensearchproject/opensearch": "opensearchproject/opensearch:1.3.0",
        "opensearchproject/opensearch-dashboards": os_db,
    }

    def __init__(self):
        self.local_registry = self.load_local_registry()

    @classmethod
    def load_local_registry(cls) -> list:
        from yaml import safe_load
        import pandas as pd

        local_registry_path = EnvironmentManager.paths["REGISTRY"]
        local_registry = []
        if local_registry_path.is_file():
            with open(local_registry_path) as f:
                local_registry_df = pd.json_normalize(safe_load(f))
                local_registry = local_registry_df.to_dict("records")

        return local_registry

    @classmethod
    def save_local_registry(cls, updated_registry: list) -> None:
        import pandas as pd
        import json
        import yaml

        local_registry_path = cls.paths["REGISTRY"]

        updated_registry_df = pd.DataFrame(updated_registry)
        orderedCols = [
            "filename",
            "source_name",
            "source_url",
        ]
        for x in [x for x in updated_registry_df.columns if x not in orderedCols]:
            orderedCols.append(x)
        updated_registry_df = updated_registry_df.reindex(columns=orderedCols)

        local_registry_path.parents[0].mkdir(parents=True, exist_ok=True)
        with open(local_registry_path, "w") as f:
            yaml.dump(
                json.loads(
                    updated_registry_df.to_json(orient="records", default_handler=str)
                ),
                f,
                default_flow_style=False,
                sort_keys=False,
            )
        return

    @classmethod
    def register_repo(cls, path_to_register: Path) -> None:
        import git

        local_registry = cls.load_local_registry()
        registered_paths = [x["source_url"] for x in local_registry]

        if registered_paths != []:
            if str(path_to_register) in registered_paths:
                print(f"Warning: Path already registered: {path_to_register}")
                return
        else:
            print(f"Creating {cls.paths['REGISTRY']}")

        new_record = {
            "filename": path_to_register.stem,
            "source_name": path_to_register.stem,
            "source_url": path_to_register,
        }
        git_repo = git.Repo(path_to_register)
        for remote in git_repo.remotes:
            if remote.url:
                new_record["source_link"] = remote.url
        local_registry.append(new_record)
        cls.save_local_registry(local_registry)
        print(f"Registered path ({path_to_register})")
        return

    @classmethod
    def get_name_mail_from_global_git_config(cls) -> list:
        import git

        ggit_conf_path = Path.home() / Path(".gitconfig")
        global_conf_details = []
        if ggit_conf_path.is_file():
            glob_git_conf = git.GitConfigParser([str(ggit_conf_path)], read_only=True)
            global_conf_details = [
                glob_git_conf.get("user", "name"),
                glob_git_conf.get("user", "email"),
            ]
        return global_conf_details

    @classmethod
    def build_docker_images(cls) -> None:

        client = docker.from_env()

        repo_tags = [image.tags for image in client.images.list()]
        repo_tags = [tag[0][: tag[0].find(":")] for tag in repo_tags if tag]

        if "lfoppiano/grobid" not in repo_tags:
            print("Pulling grobid Docker image...")
            client.images.pull(cls.docker_images["lfoppiano/grobid"])
        if "pandoc/ubuntu-latex" not in repo_tags:
            print("Pulling pandoc/ubuntu-latex image...")
            client.images.pull(cls.docker_images["pandoc/ubuntu-latex"])
        if "jbarlow83/ocrmypdf" not in repo_tags:
            print("Pulling jbarlow83/ocrmypdf image...")
            client.images.pull(cls.docker_images["jbarlow83/ocrmypdf"])
        if "zotero/translation-server" not in repo_tags:
            print("Pulling zotero/translation-server image...")
            client.images.pull(cls.docker_images["zotero/translation-server"])

        return

    @classmethod
    def check_git_installed(cls) -> None:
        import subprocess
        from colrev_core.review_manager import MissingDependencyError

        try:
            null = open("/dev/null", "w")
            subprocess.Popen("git", stdout=null, stderr=null)
            null.close()
        except OSError:
            pass
            raise MissingDependencyError("git")
        return

    @classmethod
    def check_docker_installed(cls) -> None:
        import subprocess
        from colrev_core.review_manager import MissingDependencyError

        try:
            null = open("/dev/null", "w")
            subprocess.Popen("docker", stdout=null, stderr=null)
            null.close()
        except OSError:
            pass
            raise MissingDependencyError("docker")
        return

    def get_environment_details(self) -> dict:
        from colrev_core.environment import LocalIndex
        from colrev_core.review_manager import ReviewManager

        from git.exc import NoSuchPathError
        from git.exc import InvalidGitRepositoryError
        from opensearchpy import NotFoundError

        LOCAL_INDEX = LocalIndex()

        environment_details = {}

        size = 0
        last_modified = "NOT_INITIATED"
        status = ""

        def get_last_modified() -> str:
            import os
            import datetime

            list_of_files = LOCAL_INDEX.opensearch_index.glob(
                "**/*"
            )  # * means all if need specific format then *.csv
            latest_file = max(list_of_files, key=os.path.getmtime)
            last_mod = datetime.datetime.fromtimestamp(latest_file.lstat().st_mtime)
            return last_mod.strftime("%Y-%m-%d %H:%M")

        try:
            size = LOCAL_INDEX.os.cat.count(
                index=LOCAL_INDEX.RECORD_INDEX, params={"format": "json"}
            )[0]["count"]
            last_modified = get_last_modified()
            status = "up"
        except (NotFoundError, IndexError):
            status = "down"
            pass

        environment_details["index"] = {
            "size": size,
            "last_modified": last_modified,
            "path": str(LocalIndex.local_environment_path),
            "status": status,
        }

        local_repos = self.load_local_registry()

        repos = []
        broken_links = []
        for repo in local_repos:
            try:
                cp_REVIEW_MANAGER = ReviewManager(path_str=repo["source_url"])
                CHECK_PROCESS = CheckProcess(cp_REVIEW_MANAGER)
                repo_stat = CHECK_PROCESS.REVIEW_MANAGER.get_status()
                repo["size"] = repo_stat["colrev_status"]["overall"]["md_processed"]
                if repo_stat["atomic_steps"] != 0:
                    repo["progress"] = round(
                        repo_stat["completed_atomic_steps"] / repo_stat["atomic_steps"],
                        2,
                    )
                else:
                    repo["progress"] = -1

                repo["remote"] = False
                REVIEW_DATASET = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET
                git_repo = REVIEW_DATASET.get_repo()
                for remote in git_repo.remotes:
                    if remote.url:
                        repo["remote"] = True
                repo["behind_remote"] = REVIEW_DATASET.behind_remote()

                repos.append(repo)
            except (NoSuchPathError, InvalidGitRepositoryError):
                broken_links.append(repo)
                pass

        environment_details["local_repos"] = {
            "repos": repos,
            "broken_links": broken_links,
        }
        return environment_details

    @classmethod
    def get_curated_outlets(cls) -> list:
        curated_outlets: typing.List[str] = []
        for source_url in [
            x["source_url"]
            for x in EnvironmentManager.load_local_registry()
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
                    raise CuratedOutletNotUnique(
                        "Error: Duplicate outlets in curated_metadata of "
                        f"{source_url} : {','.join(list(set(outlets)))}"
                    )
        return curated_outlets


class LocalIndex:

    global_keys = ["doi", "dblp_key", "colrev_pdf_id", "url"]
    max_len_sha256 = 2 ** 256

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

    # Note: we need the local_curated_metadata field for is_duplicate()

    def __init__(self):

        self.os = OpenSearch("http://localhost:9200")

        self.opensearch_index.mkdir(exist_ok=True, parents=True)
        self.start_opensearch_docker()
        self.check_opensearch_docker_available()

        logging.getLogger("opensearch").setLevel(logging.ERROR)

    def start_opensearch_docker_dashboards(self) -> None:

        self.start_opensearch_docker()

        os_dashboard_image = EnvironmentManager.docker_images[
            "opensearchproject/opensearch-dashboards"
        ]

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
                    os_dashboard_image,
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
            except docker.errors.APIError as e:
                print(e)
                pass

        return

    def start_opensearch_docker(self) -> None:
        import requests

        os_image = EnvironmentManager.docker_images["opensearchproject/opensearch"]
        client = docker.from_env()
        if not any(
            "opensearch" in container.name for container in client.containers.list()
        ):
            try:
                print("Start LocalIndex")

                if not client.networks.list(names=["opensearch-net"]):
                    client.networks.create("opensearch-net")
                client.containers.run(
                    os_image,
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
            except docker.errors.APIError as e:
                print(e)
                pass

        logging.getLogger("opensearch").setLevel(logging.ERROR)

        available = False
        try:
            self.os.get(index=self.RECORD_INDEX, id="test")
        except (requests.exceptions.RequestException, ConnectionError):
            pass
        except NotFoundError:
            available = True
            pass

        if not available:
            print("Waiting until LocalIndex is available")
            for i in tqdm(range(0, 20)):
                try:
                    self.os.get(index=self.RECORD_INDEX, id="test")
                    break
                except (
                    requests.exceptions.RequestException,
                    ConnectionError,
                    TransportError,
                ):
                    time.sleep(3)
                    pass
                except NotFoundError:
                    pass
                    break
        logging.getLogger("opensearch").setLevel(logging.WARNING)

        return

    def check_opensearch_docker_available(self) -> None:
        # If not available after 120s: raise error
        self.os.info()
        return

    def __get_record_hash(self, record: dict) -> str:
        # Note : may raise NotEnoughDataToIdentifyException
        string_to_hash = Record(record).create_colrev_id()
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
        return self.teiind_path / Path(f"{hash[:2]}/{hash[2:]}.tei.xml")

    def __store_record(self, hash: str, record: dict) -> None:

        if "file" in record:
            try:
                tei_path = self.__get_tei_index_file(hash)
                tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                if Path(record["file"]).is_file():
                    TEI_INSTANCE = TEI(
                        pdf_path=Path(record["file"]),
                        tei_path=tei_path,
                        notify_state_transition_process=False,
                    )
                    record["fulltext"] = TEI_INSTANCE.get_tei_str()
            except (TEI_Exception, AttributeError, SerialisationError):
                pass

        RECORD = Record(record)
        source_info = RECORD.data.get(
            "source_link", RECORD.data.get("source_path", "NA")
        )
        if "NA" != source_info:
            RECORD.complete_provenance(source_info)

        if "colrev_status" in RECORD.data:
            del RECORD.data["colrev_status"]
        if "source_link" in RECORD.data:
            del RECORD.data["source_link"]
        if "source_path" in RECORD.data:
            del RECORD.data["source_path"]

        self.os.index(index=self.RECORD_INDEX, id=hash, body=RECORD.get_data())

        return

    def __retrieve_toc_index(self, toc_key: str) -> list:

        toc_item_response = self.os.get(index=self.TOC_INDEX, id=toc_key)
        toc_item = toc_item_response["_source"]

        return toc_item

    def __amend_record(self, hash: str, record: dict) -> None:

        try:
            saved_record_response = self.os.get(index=self.RECORD_INDEX, id=hash)
            saved_record = saved_record_response["_source"]

            SAVED_RECORD = Record(saved_record)
            source_info = Record(record).get_source_repo()

            RECORD = Record(record)
            source_info = RECORD.data.get(
                "source_link", RECORD.data.get("source_path", "NA")
            )
            if "NA" != source_info:
                RECORD.complete_provenance(source_info)

            if "source_link" in RECORD.data:
                del RECORD.data["source_link"]
            if "source_path" in RECORD.data:
                del RECORD.data["source_path"]
            record = RECORD.get_data()

            # amend saved record
            for k, v in record.items():
                # Note : the record from the first repository should take precedence)
                if k in saved_record or k in ["colrev_status"]:
                    continue

                SAVED_RECORD.update_field(k, v, source_info)

            if "file" in record and "fulltext" not in SAVED_RECORD.data:
                try:
                    tei_path = self.__get_tei_index_file(hash)
                    tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                    if Path(record["file"]).is_file():
                        TEI_INSTANCE = TEI(
                            pdf_path=Path(record["file"]),
                            tei_path=tei_path,
                            notify_state_transition_process=False,
                        )
                        SAVED_RECORD.data["fulltext"] = TEI_INSTANCE.get_tei_str()
                except (TEI_Exception, AttributeError, SerialisationError):
                    pass

            self.os.update(
                index=self.RECORD_INDEX, id=hash, body={"doc": SAVED_RECORD.get_data()}
            )
        except NotFoundError:
            pass
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
        if not Record(record).masterdata_is_curated():
            return

        if record.get("ENTRYTYPE", "") in ["article", "inproceedings"]:
            # Note : records are md_prepared, i.e., complete

            toc_key = self.__get_toc_key(record)
            if "NA" == toc_key:
                return

            # print(toc_key)
            try:
                record_colrev_id = Record(record).create_colrev_id()

                if not self.os.exists(index=self.TOC_INDEX, id=toc_key):
                    toc_item = {
                        "toc_key": toc_key,
                        "colrev_ids": [record_colrev_id],
                    }
                    self.os.index(index=self.TOC_INDEX, id=toc_key, body=toc_item)
                else:
                    toc_item_response = self.os.get(index=self.TOC_INDEX, id=toc_key)
                    toc_item = toc_item_response["_source"]
                    if toc_item["toc_key"] == toc_key:
                        # ok - no collision, update the record
                        # Note : do not update (the record from the first repository
                        #  should take precedence - reset the index to update)
                        if record_colrev_id not in toc_item["colrev_ids"]:
                            toc_item["colrev_ids"].append(  # type: ignore
                                record_colrev_id
                            )
                            self.os.update(
                                index=self.TOC_INDEX, id=toc_key, body={"doc": toc_item}
                            )
            except NotEnoughDataToIdentifyException:
                pass

        return

    def __retrieve_based_on_colrev_id(self, cids_to_retrieve: list) -> dict:
        # Note : may raise NotEnoughDataToIdentifyException

        for cid_to_retrieve in cids_to_retrieve:
            hash = hashlib.sha256(cid_to_retrieve.encode("utf-8")).hexdigest()
            while True:  # Note : while breaks with NotFoundError
                try:
                    res = self.os.get(index=self.RECORD_INDEX, id=hash)
                    retrieved_record = res["_source"]
                    if cid_to_retrieve in Record(retrieved_record).get_colrev_id():
                        return retrieved_record
                    else:
                        # Collision
                        hash = self.__increment_hash(hash)
                except NotFoundError:
                    pass
                    break

        # search colrev_id field
        for cid_to_retrieve in cids_to_retrieve:
            try:
                # match_phrase := exact match
                # TODO : the following requires some testing.
                resp = self.os.search(
                    index=self.RECORD_INDEX,
                    body={"query": {"match": {"colrev_id": cid_to_retrieve}}},
                )
                retrieved_record = resp["hits"]["hits"][0]["_source"]
                if cid_to_retrieve in retrieved_record.get("colrev_id", "NA"):
                    return retrieved_record
            except (IndexError, NotFoundError):
                pass
                raise RecordNotInIndexException

        raise RecordNotInIndexException

    def __retrieve_from_record_index(self, record: dict) -> dict:
        # Note : may raise NotEnoughDataToIdentifyException

        RECORD = Record(record)
        if "colrev_id" in RECORD.data:
            cid_to_retrieve = RECORD.get_colrev_id()
        else:
            cid_to_retrieve = [RECORD.create_colrev_id()]

        retrieved_record = self.__retrieve_based_on_colrev_id(cid_to_retrieve)
        if retrieved_record["ENTRYTYPE"] != record["ENTRYTYPE"]:
            raise RecordNotInIndexException
        return retrieved_record

    def prep_record_for_return(
        self, record: dict, include_file: bool = False, include_colrev_ids=False
    ) -> dict:
        from colrev_core.record import RecordState

        # Casting to string (in particular the RecordState Enum)
        record = {k: str(v) for k, v in record.items()}

        # Note: record['file'] should be an absolute path by definition
        # when stored in the LocalIndex
        if "file" in record:
            if not Path(record["file"]).is_file():
                del record["file"]

        if "fulltext" in record:
            del record["fulltext"]
        if "tei_file" in record:
            del record["tei_file"]
        if "grobid-version" in record:
            del record["grobid-version"]
        if include_colrev_ids:
            if "colrev_id" in record:
                pass
        else:
            if "colrev_id" in record:
                del record["colrev_id"]

        if "excl_criteria" in record:
            del record["excl_criteria"]

        if "local_curated_metadata" in record:
            del record["local_curated_metadata"]

        if "source_path" in record:
            del record["source_path"]
        if "source_link" in record:
            del record["source_link"]

        if not include_file:
            if "file" in record:
                del record["file"]
            if "colref_pdf_id" in record:
                del record["colref_pdf_id"]

        record["colrev_status"] = RecordState.md_prepared

        return record

    def duplicate_outlets(self) -> bool:
        import collections

        print("Validate curated metadata")

        curated_outlets = EnvironmentManager.get_curated_outlets()

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

        return False

    def index_record(self, record: dict) -> None:
        # Note : may raise NotEnoughDataToIdentifyException

        copy_for_toc_index = record.copy()

        if "colrev_status" not in record:
            return

        if record["colrev_status"] in [
            RecordState.md_retrieved,
            RecordState.md_imported,
            RecordState.md_prepared,
            RecordState.md_needs_manual_preparation,
        ]:
            return

        if "exclusion_criteria" in record:
            del record["exclusion_criteria"]
        # Note: if the colrev_pdf_id has not been checked,
        # we cannot use it for retrieval or preparation.
        if record["colrev_status"] not in [
            RecordState.pdf_prepared,
            RecordState.rev_excluded,
            RecordState.rev_included,
            RecordState.rev_synthesized,
        ]:
            if "colrev_pdf_id" in record:
                del record["colrev_pdf_id"]

        if "colrev/curated_metadata" in record["source_path"]:
            record["local_curated_metadata"] = "yes"

        # To fix pdf_hash fields that should have been renamed
        if "pdf_hash" in record:
            record["colref_pdf_id"] = "cpid1:" + record["pdf_hash"]
            del record["pdf_hash"]

        if "colrev_origin" in record:
            del record["colrev_origin"]

        # Note : file paths should be absolute when added to the LocalIndex
        if "file" in record:
            pdf_path = Path(record["file"])
            if pdf_path.is_file:
                record["file"] = str(pdf_path)
            else:
                del record["file"]

        if record.get("year", "NA").isdigit():
            record["year"] = int(record["year"])
        elif "year" in record:
            del record["year"]

        if "colrev_id" in record:
            if isinstance(record["colrev_id"], list):
                record["colrev_id"] = ";".join(record["colrev_id"])

        if "CURATED" == record.get("colrev_masterdata", ""):
            if "source_path" in record:
                record["colrev_masterdata"] = "CURATED:" + record["source_path"]
            if "source_link" in record:
                record["colrev_masterdata"] = "CURATED:" + record["source_link"]

        try:

            cid_to_index = Record(record).create_colrev_id()
            hash = self.__get_record_hash(record)

            try:
                # check if the record is already indexed (based on d)
                retrieved_record = self.retrieve(record, include_colrev_ids=True)
                retrieved_record_cid = Record(retrieved_record).get_colrev_id()

                # if colrev_ids not identical (but overlapping): amend
                if not set(retrieved_record_cid).isdisjoint(list(cid_to_index)):
                    # Note: we need the colrev_id of the retrieved_record
                    # (may be different from record)
                    self.__amend_record(
                        self.__get_record_hash(retrieved_record), record
                    )
                    return
            except RecordNotInIndexException:
                pass

            while True:
                if not self.os.exists(index=self.RECORD_INDEX, id=hash):
                    self.__store_record(hash, record)
                    break
                else:
                    saved_record_response = self.os.get(
                        index=self.RECORD_INDEX, id=hash
                    )
                    saved_record = saved_record_response["_source"]
                    saved_record_cid = Record(saved_record).create_colrev_id(
                        assume_complete=True
                    )
                    if saved_record_cid == cid_to_index:
                        # ok - no collision, update the record
                        # Note : do not update (the record from the first repository
                        # should take precedence - reset the index to update)
                        self.__amend_record(hash, record)
                        break
                    else:
                        # to handle the collision:
                        print(f"Collision: {hash}")
                        print(cid_to_index)
                        print(saved_record_cid)
                        print(saved_record)
                        hash = self.__increment_hash(hash)

        except NotEnoughDataToIdentifyException:
            pass
            return

        # Note : only use curated journal metadata for TOC indices
        # otherwise, TOCs will be incomplete and affect retrieval
        if "colrev/curated_metadata" in copy_for_toc_index["source_path"]:
            self.__toc_index(copy_for_toc_index)
        return

    def index_colrev_project(self, source_url):
        from colrev_core.review_manager import ReviewManager

        try:
            if not Path(source_url).is_dir():
                print(f"Warning {source_url} not a directory")
                return

            print(f"Index records from {source_url}")
            os.chdir(source_url)
            REVIEW_MANAGER = ReviewManager(path_str=str(source_url))
            CHECK_PROCESS = CheckProcess(REVIEW_MANAGER)
            if not CHECK_PROCESS.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
                return
            records = CHECK_PROCESS.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()

            # set a source_path and source_link:
            # source_path for corrections and
            # source_link to reduce prep_record_for_return procedure
            source_link = source_url  # Default to avoid setting it to the previous one
            [record.update(source_path=source_url) for record in records.values()]
            source_link = self.get_source_link(list(records.values())[0])
            [record.update(source_link=source_link) for record in records.values()]
            [
                record.update(file=source_url / Path(record["file"]))
                for record in records.values()
                if "file" in record
            ]

            for record in tqdm(records.values()):
                self.index_record(record)

        except InvalidGitRepositoryError:
            print(f"InvalidGitRepositoryError: {source_url}")
            pass
        except KeyError as e:
            print(f"KeyError: {e}")
            pass
        return

    def index(self) -> None:
        # import shutil

        print("Start LocalIndex")

        if self.duplicate_outlets():
            return

        print(f"Reset {self.RECORD_INDEX} and {self.TOC_INDEX}")
        # if self.teiind_path.is_dir():
        #     shutil.rmtree(self.teiind_path)

        self.opensearch_index.mkdir(exist_ok=True, parents=True)
        if self.RECORD_INDEX in self.os.indices.get_alias().keys():
            self.os.indices.delete(index=self.RECORD_INDEX, ignore=[400, 404])
        if self.TOC_INDEX in self.os.indices.get_alias().keys():
            self.os.indices.delete(index=self.TOC_INDEX, ignore=[400, 404])
        self.os.indices.create(index=self.RECORD_INDEX)
        self.os.indices.create(index=self.TOC_INDEX)

        source_urls = [
            x["source_url"] for x in EnvironmentManager.load_local_registry()
        ]
        for source_url in source_urls:
            self.index_colrev_project(source_url)

        # for annotator in self.annotators_path.glob("*/annotate.py"):
        #     print(f"Load {annotator}")
        #     import imp

        #     annotator_module = imp.load_source("annotator_module", str(annotator))
        #     annotate = getattr(annotator_module, "annotate")
        #     annotate(self)
        # Note : es.update can use functions applied to each record (for the update)

        return

    def retrieve_from_toc(
        self, record: dict, similarity_threshold: float, include_file=False
    ) -> dict:
        toc_key = self.__get_toc_key(record)

        # 1. get TOC
        toc_items = []
        if self.os.exists(index=self.TOC_INDEX, id=toc_key):
            res = self.__retrieve_toc_index(toc_key)
            toc_items = res["colrev_ids"]  # type: ignore

        # 2. get most similar record
        if len(toc_items) > 0:
            try:
                # TODO : we need to search tocs even if records are not complete:
                # and a NotEnoughDataToIdentifyException is thrown
                record_colrev_id = Record(record).create_colrev_id()
                sim_list = []
                for toc_records_colrev_id in toc_items:
                    # Note : using a simpler similarity measure
                    # because the publication outlet parameters are already identical
                    sv = fuzz.ratio(record_colrev_id, toc_records_colrev_id) / 100
                    sim_list.append(sv)

                if max(sim_list) > similarity_threshold:
                    toc_records_colrev_id = toc_items[sim_list.index(max(sim_list))]
                    hash = hashlib.sha256(
                        toc_records_colrev_id.encode("utf-8")
                    ).hexdigest()
                    res = self.os.get(index=self.RECORD_INDEX, id=str(hash))
                    record = res["_source"]  # type: ignore
                    return self.prep_record_for_return(record, include_file)
            except NotEnoughDataToIdentifyException:
                pass

        raise RecordNotInIndexException()
        return record

    def get_from_index_exact_match(self, index_name, key, value) -> dict:
        resp = self.os.search(
            index=index_name, body={"query": {"match_phrase": {key: value}}}
        )
        res = resp["hits"]["hits"][0]["_source"]
        return res

    def retrieve(
        self, record: dict, include_file: bool = False, include_colrev_ids=False
    ) -> dict:
        """
        Convenience function to retrieve the indexed record metadata
        based on another record
        """

        retrieved_record: typing.Dict = dict()

        # 1. Try the record index

        try:
            retrieved_record = self.__retrieve_from_record_index(record)
        except (
            NotFoundError,
            RecordNotInIndexException,
            NotEnoughDataToIdentifyException,
        ):
            pass

        if retrieved_record:
            return self.prep_record_for_return(
                retrieved_record, include_file, include_colrev_ids
            )

        # 2. Try using global-ids
        if not retrieved_record:
            for k, v in record.items():
                if k not in self.global_keys or "ID" == k:
                    continue
                try:
                    retrieved_record = self.get_from_index_exact_match(
                        self.RECORD_INDEX, k, v
                    )
                    break
                except (IndexError, NotFoundError):
                    pass

        if not retrieved_record:
            raise RecordNotInIndexException(record.get("ID", "no-key"))

        return self.prep_record_for_return(
            retrieved_record, include_file, include_colrev_ids
        )

    def get_source_link(self, record: dict) -> str:
        ret = self.set_source_link(record.copy())
        if "source_link" in ret:
            return ret["source_link"]
        else:
            return "NO_SOURCE_LINK"

    def set_source_link(self, record: dict) -> dict:
        if "source_path" in record:
            local_repo = [
                r
                for r in EnvironmentManager.load_local_registry()
                if r["source_url"] == record["source_path"]
            ]
            if len(local_repo) > 0:
                if local_repo[0].get("source_link") is not None:
                    record["source_link"] = local_repo[0]["source_link"]
                else:
                    record["source_link"] = "NO_SOURCE_URL_IN_REGISTRY"
            else:
                record["source_link"] = "REPO_NOT_IN_REGISTRY"
        else:
            record["source_link"] = "NO_SOURCE_PATH"
        return record

    def set_source_path(self, record: dict) -> dict:
        if "source_link" in record:
            for local_repo in EnvironmentManager.load_local_registry():
                if local_repo["source_link"] == record["source_link"]:
                    record["source_path"] = local_repo["source_url"]

        return record

    def is_duplicate(self, record1_colrev_id: list, record2_colrev_id: list) -> str:
        """Convenience function to check whether two records are a duplicate"""

        if not set(record1_colrev_id).isdisjoint(list(record2_colrev_id)):
            return "yes"

        # Note : the __retrieve_based_on_colrev_id(record)
        # also checks the colrev_id lists, i.e.,
        # duplicate (yes) if the IDs and source_links are identical,
        # record1 and record2 have been mapped to the same record
        # no duplicate (no) if record1 ID != record2 ID
        # (both in index and same source_link)
        try:
            r1_index = self.__retrieve_based_on_colrev_id(record1_colrev_id)
            r2_index = self.__retrieve_based_on_colrev_id(record2_colrev_id)
            # Same repo (colrev_masterdata = CURATED: ...) and in LocalIndex
            # implies status > md_processed
            # ie., no duplicates if IDs differ
            if (
                "CURATED:" in r1_index["colrev_masterdata"]
                and "CURATED:" in r2_index["colrev_masterdata"]
            ):
                if r1_index["colrev_masterdata"] == r2_index["colrev_masterdata"]:
                    if r1_index["ID"] == r2_index["ID"]:
                        return "yes"
                    else:
                        return "no"

            # Note : We know that records are not duplicates when they are
            # part of curated_metadata repositories ('local_curated_metadata')
            #  and their IDs are not identical
            # For the same journal, only deduplicated records are indexed
            # We make sure that journals are only indexed once
            if (
                "local_curated_metadata" in r1_index["source_path"]
                and "local_curated_metadata" in r2_index["source_path"]
            ):

                if not set(Record(r1_index).get_colrev_id()).isdisjoint(
                    list(Record(r2_index).get_colrev_id())
                ):
                    return "yes"
                else:
                    # Note : no duplicate if both are index and
                    # the indexed colrev_ids are disjoint
                    return "no"

        except (
            RecordNotInIndexException,
            NotFoundError,
            NotEnoughDataToIdentifyException,
        ):
            pass

        return "unknown"

    def analyze(self, threshold: float = 0.95) -> None:

        # TODO : update analyze() functionality based on es index
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

        # colrev_pdf_ids = []
        # https://bit.ly/3tbypkd
        # for r_file in self.rind_path.rglob("*.bib"):

        #     with open(r_file) as f:
        #         while True:
        #             line = f.readline()
        #             if not line:
        #                 break
        #             if "colrev_pdf_id" in line[:9]:
        #                 val = line[line.find("{") + 1 : line.rfind("}")]
        #                 colrev_pdf_ids.append(val)

        # import collections

        # colrev_pdf_ids_dupes = [
        #     item for item, count in
        #       collections.Counter(colrev_pdf_ids).items() if count > 1
        # ]

        # with open("non-unique-cpids.txt", "w") as o:
        #     o.write("\n".join(colrev_pdf_ids_dupes))
        # print("Export non-unique-cpids.txt")
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
            EnvironmentManager.register_repo(repo_dir)
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


class CuratedOutletNotUnique(Exception):
    def __init__(self, msg: str = None):
        self.message = msg
        super().__init__(self.message)


if __name__ == "__main__":
    pass
