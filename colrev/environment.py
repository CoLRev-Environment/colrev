#! /usr/bin/env python
from __future__ import annotations

import binascii
import collections
import hashlib
import importlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
import typing
from copy import deepcopy
from datetime import datetime
from datetime import timedelta
from json import JSONDecodeError
from pathlib import Path
from threading import Timer
from typing import TYPE_CHECKING

import docker
import git
import pandas as pd
import requests
import requests_cache
import yaml
from docker.errors import APIError
from git.exc import InvalidGitRepositoryError
from git.exc import NoSuchPathError
from lxml import etree
from opensearchpy import OpenSearch
from opensearchpy.exceptions import NotFoundError
from opensearchpy.exceptions import SerializationError
from opensearchpy.exceptions import TransportError
from pybtex.database.input import bibtex
from thefuzz import fuzz
from tqdm import tqdm
from yaml import safe_load
from zope.interface.verify import verifyObject

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class AdapterManager:
    # pylint: disable=too-few-public-methods

    @classmethod
    def load_scripts(
        cls, *, process, scripts, script_type: str = ""
    ) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=unnecessary-dict-index-lookup
        # Note : when iterating over script_dict.items(),
        # changes to the values (or del k) would not persist

        # avoid changes in the config
        scripts = deepcopy(scripts)
        scripts_dict: typing.Dict = {}
        for script in scripts:
            script_name = script["endpoint"]
            scripts_dict[script_name] = {}

            # 1. Load built-in scripts
            if script_name in process.built_in_scripts:
                scripts_dict[script_name]["settings"] = script
                scripts_dict[script_name]["endpoint"] = process.built_in_scripts[
                    script_name
                ]["endpoint"]

            # 2. Load module scripts
            # TODO : test the module prep_scripts
            elif not Path(script_name + ".py").is_file():
                try:
                    scripts_dict[script_name]["settings"] = script
                    scripts_dict[script_name]["endpoint"] = importlib.import_module(
                        script_name
                    )
                    scripts_dict[script_name]["custom_flag"] = True
                except ModuleNotFoundError as exc:
                    raise colrev_exceptions.MissingDependencyError(
                        "Dependency " + f"{script_name} not found. "
                        "Please install it\n  pip install "
                        f"{script_name}"
                    ) from exc

            # 3. Load custom scripts in the directory
            elif Path(script_name + ".py").is_file():
                sys.path.append(".")  # to import custom scripts from the project dir
                scripts_dict[script_name]["settings"] = script
                scripts_dict[script_name]["endpoint"] = importlib.import_module(
                    script_name, "."
                )
                scripts_dict[script_name]["custom_flag"] = True
            else:
                print(f"Could not load {script}")
                continue
            scripts_dict[script_name]["settings"]["name"] = scripts_dict[script_name][
                "settings"
            ]["endpoint"]
            del scripts_dict[script_name]["settings"]["endpoint"]

        if colrev.process.ProcessType.search == process.type:
            from colrev.process import SearchEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomSearch
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    search_operation=process, settings=script["settings"]
                )
                verifyObject(SearchEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.load == process.type:
            from colrev.process import LoadEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomLoad
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    load_operation=process, settings=script["settings"]
                )
                verifyObject(LoadEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.prep == process.type:
            from colrev.process import PrepEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPrep
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    prep_operation=process, settings=script["settings"]
                )
                verifyObject(PrepEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.prep_man == process.type:
            from colrev.process import PrepManEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPrepMan
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    prep_man_operation=process, settings=script["settings"]
                )
                verifyObject(PrepManEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.dedupe == process.type:
            from colrev.process import DedupeEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomDedupe
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    dedupe_operation=process, settings=script["settings"]
                )
                verifyObject(DedupeEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.prescreen == process.type:
            from colrev.process import PrescreenEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPrescreen
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    prescreen_operation=process, settings=script["settings"]
                )
                verifyObject(PrescreenEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_get == process.type:
            from colrev.process import PDFGetEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFGet
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_get_operation=process, settings=script["settings"]
                )
                verifyObject(PDFGetEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_get_man == process.type:
            from colrev.process import PDFGetManEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFGetMan
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_get_man_operation=process, settings=script["settings"]
                )
                verifyObject(PDFGetManEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_prep == process.type:
            from colrev.process import PDFPrepEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFPrep
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_prep_operation=process, settings=script["settings"]
                )
                verifyObject(PDFPrepEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_prep_man == process.type:
            from colrev.process import PDFPrepManEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFPrepMan
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_prep_man_operation=process, settings=script["settings"]
                )
                verifyObject(PDFPrepManEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.screen == process.type:
            from colrev.process import ScreenEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomScreen
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    screen_operation=process, settings=script["settings"]
                )
                verifyObject(ScreenEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.data == process.type:
            from colrev.process import DataEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomData
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    data_operation=process, settings=script["settings"]
                )
                verifyObject(DataEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.check == process.type:
            if "SearchSource" == script_type:
                from colrev.process import SearchSourceEndpoint

                for k, val in scripts_dict.items():
                    if "custom_flag" in val:
                        scripts_dict[k]["endpoint"] = val["endpoint"].CustomSearchSource
                        del scripts_dict[k]["custom_flag"]

                for endpoint_name, script in scripts_dict.items():
                    scripts_dict[endpoint_name] = script["endpoint"](
                        settings=script["settings"]
                    )
                    verifyObject(SearchSourceEndpoint, scripts_dict[endpoint_name])
            else:
                print(
                    f"ERROR: process type not implemented: {process.type}/{script_type}"
                )

        else:
            print(f"ERROR: process type not implemented: {process.type}")

        return scripts_dict


class EnvironmentManager:

    colrev_path = Path.home().joinpath("colrev")
    cache_path = colrev_path / Path("prep_requests_cache")
    REGISTRY_RELATIVE = Path("registry.yaml")
    registry = colrev_path.joinpath(REGISTRY_RELATIVE)

    os_db = "opensearchproject/opensearch-dashboards:1.3.0"

    # TODO : include ports in the dict?
    docker_images = {
        "lfoppiano/grobid": "lfoppiano/grobid:0.7.1",
        "pandoc/ubuntu-latex": "pandoc/ubuntu-latex:2.14",
        "jbarlow83/ocrmypdf": "jbarlow83/ocrmypdf:v13.3.0",
        "zotero/translation-server": "zotero/translation-server:2.0.4",
        "opensearchproject/opensearch": "opensearchproject/opensearch:1.3.0",
        "opensearchproject/opensearch-dashboards": os_db,
        "browserless/chrome": "browserless/chrome:latest",
        "bibutils": "bibutils:latest",
        "pdf_hash": "pdf_hash:latest",
    }

    def __init__(self) -> None:
        self.local_registry = self.load_local_registry()

    def load_local_registry(self) -> list:

        local_registry_path = self.registry
        local_registry = []
        if local_registry_path.is_file():
            with open(local_registry_path, encoding="utf8") as file:
                local_registry_df = pd.json_normalize(safe_load(file))
                local_registry = local_registry_df.to_dict("records")

        return local_registry

    def save_local_registry(self, *, updated_registry: list) -> None:

        updated_registry_df = pd.DataFrame(updated_registry)
        ordered_cols = [
            "repo_name",
            "repo_source_path",
        ]
        for entry in [x for x in updated_registry_df.columns if x not in ordered_cols]:
            ordered_cols.append(entry)
        updated_registry_df = updated_registry_df.reindex(columns=ordered_cols)

        self.registry.parents[0].mkdir(parents=True, exist_ok=True)
        with open(self.registry, "w", encoding="utf8") as file:
            yaml.dump(
                json.loads(
                    updated_registry_df.to_json(orient="records", default_handler=str)
                ),
                file,
                default_flow_style=False,
                sort_keys=False,
            )

    def register_repo(self, *, path_to_register: Path) -> None:

        local_registry = self.load_local_registry()
        registered_paths = [x["repo_source_path"] for x in local_registry]

        if registered_paths != []:
            if str(path_to_register) in registered_paths:
                print(f"Warning: Path already registered: {path_to_register}")
                return
        else:
            print(f"Creating {self.registry}")

        new_record = {
            "repo_name": path_to_register.stem,
            "repo_source_path": path_to_register,
        }
        git_repo = git.Repo(path_to_register)
        for remote in git_repo.remotes:
            if remote.url:
                new_record["repo_source_url"] = remote.url
        local_registry.append(new_record)
        self.save_local_registry(updated_registry=local_registry)
        print(f"Registered path ({path_to_register})")

    def get_name_mail_from_git(self) -> typing.Tuple[str, str]:

        ggit_conf_path = Path.home() / Path(".gitconfig")
        global_conf_details = ("NA", "NA")
        if ggit_conf_path.is_file():
            glob_git_conf = git.GitConfigParser([str(ggit_conf_path)], read_only=True)
            global_conf_details = (
                glob_git_conf.get("user", "name"),
                glob_git_conf.get("user", "email"),
            )
        return global_conf_details

    def build_docker_images(self) -> None:

        client = docker.from_env()

        repo_tags = [image.tags for image in client.images.list()]
        repo_tags = [tag[0][: tag[0].find(":")] for tag in repo_tags if tag]

        for img_name, img_version in self.docker_images.items():
            if img_name not in repo_tags:

                if "bibutils" == img_name:
                    print("Building bibutils Docker image...")
                    colrev_path = Path(colrev.review_manager.__file__).parents[0]
                    context_path = colrev_path / Path("docker/bibutils")
                    client.images.build(path=str(context_path), tag="bibutils:latest")

                elif "pdf_hash" == img_name:
                    print("Building pdf_hash Docker image...")
                    colrev_path = Path(colrev.review_manager.__file__).parents[0]
                    context_path = colrev_path / Path("docker/pdf_hash")
                    client.images.build(path=str(context_path), tag="pdf_hash:latest")

                else:
                    print(f"Pulling {img_name} Docker image...")
                    client.images.pull(img_version)

    def check_git_installed(self) -> None:
        # pylint: disable=consider-using-with

        try:
            with open("/dev/null", "w", encoding="utf8") as null:
                subprocess.Popen("git", stdout=null, stderr=null)
        except OSError as exc:
            raise colrev_exceptions.MissingDependencyError("git") from exc

    def check_docker_installed(self) -> None:
        # pylint: disable=consider-using-with

        try:
            with open("/dev/null", "w", encoding="utf8") as null:
                subprocess.Popen("docker", stdout=null, stderr=null)
        except OSError as exc:
            raise colrev_exceptions.MissingDependencyError("docker") from exc

    def _get_status(
        self, *, review_manager: colrev.review_manager.ReviewManager
    ) -> dict:
        status_dict = {}
        with open(review_manager.status, encoding="utf8") as stream:
            try:
                status_dict = yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)
        return status_dict

    def get_environment_details(self) -> dict:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=redefined-outer-name
        # pylint: disable=cyclic-import
        import colrev.review_manager

        local_index = LocalIndex()

        environment_details = {}
        size = 0
        last_modified = "NOT_INITIATED"
        status = ""

        def get_last_modified() -> str:

            list_of_files = local_index.opensearch_index.glob(
                "**/*"
            )  # * means all if need specific format then *.csv
            latest_file = max(list_of_files, key=os.path.getmtime)
            last_mod = datetime.fromtimestamp(latest_file.lstat().st_mtime)
            return last_mod.strftime("%Y-%m-%d %H:%M")

        try:
            size = local_index.open_search.cat.count(
                index=local_index.RECORD_INDEX, params={"format": "json"}
            )[0]["count"]
            last_modified = get_last_modified()
            status = "up"
        except (NotFoundError, IndexError):
            status = "down"

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
                cp_review_manager = colrev.review_manager.ReviewManager(
                    path_str=repo["repo_source_path"]
                )
                check_process = colrev.process.CheckProcess(
                    review_manager=cp_review_manager
                )
                repo_stat = self._get_status(review_manager=cp_review_manager)
                repo["size"] = repo_stat["colrev_status"]["overall"]["md_processed"]
                if repo_stat["atomic_steps"] != 0:
                    repo["progress"] = round(
                        repo_stat["completed_atomic_steps"] / repo_stat["atomic_steps"],
                        2,
                    )
                else:
                    repo["progress"] = -1

                repo["remote"] = False
                git_repo = check_process.review_manager.dataset.get_repo()
                for remote in git_repo.remotes:
                    if remote.url:
                        repo["remote"] = True
                repo[
                    "behind_remote"
                ] = check_process.review_manager.dataset.behind_remote()

                repos.append(repo)
            except (NoSuchPathError, InvalidGitRepositoryError):
                broken_links.append(repo)

        environment_details["local_repos"] = {
            "repos": repos,
            "broken_links": broken_links,
        }
        return environment_details

    def get_curated_outlets(self) -> list:
        curated_outlets: typing.List[str] = []
        for repo_source_path in [
            x["repo_source_path"]
            for x in self.load_local_registry()
            if "colrev/curated_metadata/" in x["repo_source_path"]
        ]:
            try:
                with open(f"{repo_source_path}/readme.md", encoding="utf-8") as file:
                    first_line = file.readline()
                curated_outlets.append(first_line.lstrip("# ").replace("\n", ""))

                with open(f"{repo_source_path}/records.bib", encoding="utf-8") as file:
                    outlets = []
                    for line in file.readlines():
                        # Note : the second part ("journal:"/"booktitle:")
                        # ensures that data provenance fields are skipped
                        if (
                            "journal" == line.lstrip()[:7]
                            and "journal:" != line.lstrip()[:8]
                        ):
                            journal = line[line.find("{") + 1 : line.rfind("}")]
                            outlets.append(journal)
                        if (
                            "booktitle" == line.lstrip()[:9]
                            and "booktitle:" != line.lstrip()[:10]
                        ):
                            booktitle = line[line.find("{") + 1 : line.rfind("}")]
                            outlets.append(booktitle)

                    if len(set(outlets)) != 1:
                        raise colrev_exceptions.CuratedOutletNotUnique(
                            "Error: Duplicate outlets in curated_metadata of "
                            f"{repo_source_path} : {','.join(list(set(outlets)))}"
                        )
            except FileNotFoundError as exc:
                print(exc)

        return curated_outlets


class LocalIndex:

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

    # Note: we need the local_curated_metadata field for is_duplicate()

    def __init__(self, *, startup_without_waiting: bool = False) -> None:

        self.open_search = OpenSearch("http://localhost:9200")

        self.opensearch_index.mkdir(exist_ok=True, parents=True)
        try:
            self.check_opensearch_docker_available()
        except TransportError:

            self.start_opensearch_docker(
                startup_without_waiting=startup_without_waiting
            )
        if not startup_without_waiting:
            self.check_opensearch_docker_available()

        self.environment_manager = EnvironmentManager()

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
            except docker.errors.APIError as exc:
                print(exc)

    def start_opensearch_docker(self, *, startup_without_waiting: bool = False) -> None:

        os_image = EnvironmentManager.docker_images["opensearchproject/opensearch"]
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
        # If not available after 120s: raise error
        self.open_search.info()

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

    def __store_record(self, *, paper_hash: str, record_dict: dict) -> None:

        if "file" in record_dict:
            try:
                tei_path = self.__get_tei_index_file(paper_hash=paper_hash)
                tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                if Path(record_dict["file"]).is_file():
                    tei = TEIParser(
                        pdf_path=Path(record_dict["file"]),
                        tei_path=tei_path,
                    )
                    record_dict["fulltext"] = tei.get_tei_str()
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

            saved_record = colrev.record.Record(
                data=self.parse_record(record_dict=saved_record_dict)
            )

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
                if key in saved_record_dict or key in ["colrev_status"]:
                    continue

                # source_info = colrev.record.Record(data=record_dict).
                # get_provenance_field_source(key=k)
                source_info, _ = colrev.record.Record(
                    data=record_dict
                ).get_field_provenance(
                    key=key,
                    default_source=record.data.get(
                        "metadata_source_repository_paths", "None"
                    ),
                )

                saved_record.update_field(key=key, value=value, source=source_info)

            if "file" in record_dict and "fulltext" not in saved_record.data:
                try:
                    tei_path = self.__get_tei_index_file(paper_hash=paper_hash)
                    tei_path.parents[0].mkdir(exist_ok=True, parents=True)
                    if Path(record_dict["file"]).is_file():
                        tei = TEIParser(
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

            # pylint: disable=unexpected-keyword-arg
            # Note : update(...) accepts the timeout keyword
            # https://opensearch-project.github.io/opensearch-py/
            # api-ref/client.html#opensearchpy.OpenSearch.update
            self.open_search.update(
                index=self.RECORD_INDEX,
                id=paper_hash,
                body={"doc": saved_record.get_data(stringify=True)},
                timeout=self.request_timeout,
            )
        except (NotFoundError, KeyError):
            pass

    def __get_toc_key(self, *, record_dict: dict) -> str:
        toc_key = "NA"
        if "article" == record_dict["ENTRYTYPE"]:
            toc_key = f"{record_dict.get('journal', '').lower()}"
            if "volume" in record_dict:
                toc_key = toc_key + f"|{record_dict['volume']}"
            if "number" in record_dict:
                toc_key = toc_key + f"|{record_dict['number']}"
            else:
                toc_key = toc_key + "|"
        elif "inproceedings" == record_dict["ENTRYTYPE"]:
            toc_key = (
                f"{record_dict.get('booktitle', '').lower()}"
                + f"|{record_dict.get('year', '')}"
            )

        return toc_key

    def get_fields_to_remove(self, *, record_dict: dict) -> list:
        """Compares the record to available toc items and
        returns fields to remove (if any)"""

        internal_record_dict = deepcopy(record_dict)
        fields_to_remove = []
        if (
            "volume" in internal_record_dict.keys()
            and "number" in internal_record_dict.keys()
        ):

            toc_key_full = self.__get_toc_key(record_dict=internal_record_dict)

            wo_nr = deepcopy(internal_record_dict)
            del wo_nr["number"]
            toc_key_wo_nr = self.__get_toc_key(record_dict=wo_nr)
            if not self.open_search.exists(
                index=self.TOC_INDEX, id=toc_key_full
            ) and self.open_search.exists(index=self.TOC_INDEX, id=toc_key_wo_nr):
                fields_to_remove.append("number")
                return fields_to_remove

            wo_vol = deepcopy(internal_record_dict)
            del wo_vol["volume"]
            toc_key_wo_vol = self.__get_toc_key(record_dict=wo_vol)
            if not self.open_search.exists(
                index=self.TOC_INDEX, id=toc_key_full
            ) and self.open_search.exists(index=self.TOC_INDEX, id=toc_key_wo_vol):
                fields_to_remove.append("volume")
                return fields_to_remove

            wo_vol_nr = deepcopy(internal_record_dict)
            del wo_vol_nr["volume"]
            del wo_vol_nr["number"]
            toc_key_wo_vol_nr = self.__get_toc_key(record_dict=wo_vol_nr)
            if not self.open_search.exists(
                index=self.TOC_INDEX, id=toc_key_full
            ) and self.open_search.exists(index=self.TOC_INDEX, id=toc_key_wo_vol_nr):
                fields_to_remove.append("number")
                fields_to_remove.append("volume")
                return fields_to_remove

        return fields_to_remove

    def __toc_index(self, *, record_dict: dict) -> None:
        if not colrev.record.Record(data=record_dict).masterdata_is_curated():
            return

        if record_dict.get("ENTRYTYPE", "") in ["article", "inproceedings"]:
            # Note : records are md_prepared, i.e., complete

            toc_key = self.__get_toc_key(record_dict=record_dict)
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
                # match_phrase := exact match
                # TODO : the following requires some testing.
                resp = self.open_search.search(
                    index=self.RECORD_INDEX,
                    body={"query": {"match": {"colrev_id": cid_to_retrieve}}},
                )
                retrieved_record = resp["hits"]["hits"][0]["_source"]
                if cid_to_retrieve in retrieved_record.get("colrev_id", "NA"):
                    return retrieved_record
            except (
                IndexError,
                NotFoundError,
                TransportError,
                SerializationError,
            ) as exc:
                raise colrev_exceptions.RecordNotInIndexException from exc
            except KeyError:
                pass

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

    def parse_record(self, *, record_dict: dict) -> dict:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=redefined-outer-name
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

    def prep_record_for_return(
        self, *, record_dict: dict, include_file: bool = False, include_colrev_ids=False
    ) -> dict:

        record_dict = self.parse_record(record_dict=record_dict)

        # Note: record['file'] should be an absolute path by definition
        # when stored in the LocalIndex
        if "file" in record_dict:
            if not Path(record_dict["file"]).is_file():
                del record_dict["file"]

        if "fulltext" in record_dict:
            del record_dict["fulltext"]
        if "tei_file" in record_dict:
            del record_dict["tei_file"]
        if "grobid-version" in record_dict:
            del record_dict["grobid-version"]
        if include_colrev_ids:
            if "colrev_id" in record_dict:
                pass
        else:
            if "colrev_id" in record_dict:
                del record_dict["colrev_id"]

        if "excl_criteria" in record_dict:
            del record_dict["excl_criteria"]
        if "exclusion_criteria" in record_dict:
            del record_dict["exclusion_criteria"]

        if "local_curated_metadata" in record_dict:
            del record_dict["local_curated_metadata"]

        if "metadata_source_repository_paths" in record_dict:
            del record_dict["metadata_source_repository_paths"]

        if not include_file:
            if "file" in record_dict:
                del record_dict["file"]
            if "colref_pdf_id" in record_dict:
                del record_dict["colref_pdf_id"]

        record_dict["colrev_status"] = colrev.record.RecordState.md_prepared

        return record_dict

    def outlets_duplicated(self) -> bool:

        print("Validate curated metadata")

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

        return False

    def index_record(self, *, record_dict: dict) -> None:
        # Note : may raise NotEnoughDataToIdentifyException

        copy_for_toc_index = deepcopy(record_dict)

        if "colrev_status" not in record_dict:
            return

        # Note : it is important to exclude md_prepared if the LocalIndex
        # is used to dissociate duplicates
        if record_dict["colrev_status"] in [
            colrev.record.RecordState.md_retrieved,
            colrev.record.RecordState.md_imported,
            colrev.record.RecordState.md_prepared,
            colrev.record.RecordState.md_needs_manual_preparation,
        ]:
            return

        # TODO : remove provenance on project-specific fields

        if "screening_criteria" in record_dict:
            del record_dict["screening_criteria"]
        # Note: if the colrev_pdf_id has not been checked,
        # we cannot use it for retrieval or preparation.
        if record_dict["colrev_status"] not in [
            colrev.record.RecordState.pdf_prepared,
            colrev.record.RecordState.rev_excluded,
            colrev.record.RecordState.rev_included,
            colrev.record.RecordState.rev_synthesized,
        ]:
            if "colrev_pdf_id" in record_dict:
                del record_dict["colrev_pdf_id"]

        # Note : this is the first run, no need to split/list
        if "colrev/curated_metadata" in record_dict["metadata_source_repository_paths"]:
            # Note : local_curated_metadata is important to identify non-duplicates
            # between curated_metadata_repositories
            record_dict["local_curated_metadata"] = "yes"

        # To fix pdf_hash fields that should have been renamed
        if "pdf_hash" in record_dict:
            record_dict["colref_pdf_id"] = "cpid1:" + record_dict["pdf_hash"]
            del record_dict["pdf_hash"]

        if "colrev_origin" in record_dict:
            del record_dict["colrev_origin"]

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

        try:

            cid_to_index = colrev.record.Record(data=record_dict).create_colrev_id()
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
                saved_record_cid = colrev.record.Record(
                    data=saved_record
                ).create_colrev_id(assume_complete=True)
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

        except (
            colrev_exceptions.NotEnoughDataToIdentifyException,
            TransportError,
            SerializationError,
            KeyError,
        ):
            return

        # Note : only use curated journal metadata for TOC indices
        # otherwise, TOCs will be incomplete and affect retrieval
        if (
            "colrev/curated_metadata"
            in copy_for_toc_index["metadata_source_repository_paths"]
        ):
            self.__toc_index(record_dict=copy_for_toc_index)

    def index_colrev_project(self, *, repo_source_path: Path) -> None:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=redefined-outer-name
        # pylint: disable=cyclic-import
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
            check_process = colrev.process.CheckProcess(review_manager=review_manager)
            if not check_process.review_manager.dataset.records_file.is_file():
                return
            records = check_process.review_manager.dataset.load_records_dict()

            # Add metadata_source_repository_paths : list of repositories from which
            # the record was integrated. Important for is_duplicate(...)

            for record in records.values():
                record.update(metadata_source_repository_paths=repo_source_path)

            # Set masterdata_provenace to CURATED:{url}
            curation_url = check_process.review_manager.settings.project.curation_url
            if check_process.review_manager.settings.project.curated_masterdata:
                for record in records.values():
                    record.update(
                        colrev_masterdata_provenance=f"CURATED:{curation_url};;"
                    )

            # Add curation_url to curated fields (provenance)
            for (
                curated_field
            ) in check_process.review_manager.settings.project.curated_fields:

                for record_dict in records.values():
                    colrev.record.Record(data=record_dict).add_data_provenance(
                        key=curated_field, source=f"CURATED:{curation_url}"
                    )

            # Set absolute file paths (for simpler retrieval)
            for record in records.values():
                if "file" in record:
                    record.update(file=repo_source_path / Path(record["file"]))

            for record_dict in tqdm(records.values()):
                self.index_record(record_dict=record_dict)

        except (colrev_exceptions.InvalidSettingsError) as exc:
            print(exc)

    def index(self) -> None:
        # import shutil

        # Note : this task takes long and does not need to run often
        session = requests_cache.CachedSession(
            str(EnvironmentManager.cache_path),
            backend="sqlite",
            expire_after=timedelta(days=30),
        )
        # pylint: disable=unnecessary-lambda
        # Note : lambda is necessary to prevent immediate function call
        Timer(0.1, lambda: session.remove_expired_responses()).start()

        print("Start LocalIndex")

        if self.outlets_duplicated():
            return

        print(f"Reset {self.RECORD_INDEX} and {self.TOC_INDEX}")
        # if self.teiind_path.is_dir():
        #     shutil.rmtree(self.teiind_path)

        self.opensearch_index.mkdir(exist_ok=True, parents=True)
        if self.RECORD_INDEX in self.open_search.indices.get_alias().keys():
            self.open_search.indices.delete(index=self.RECORD_INDEX)
        if self.TOC_INDEX in self.open_search.indices.get_alias().keys():
            self.open_search.indices.delete(index=self.TOC_INDEX)
        self.open_search.indices.create(index=self.RECORD_INDEX)
        self.open_search.indices.create(index=self.TOC_INDEX)

        repo_source_paths = [
            x["repo_source_path"]
            for x in self.environment_manager.load_local_registry()
        ]
        for repo_source_path in repo_source_paths:
            self.index_colrev_project(repo_source_path=repo_source_path)

        # for annotator in self.annotators_path.glob("*/annotate.py"):
        #     print(f"Load {annotator}")
        #     import imp

        #     annotator_module = imp.load_source("annotator_module", str(annotator))
        #     annotate = getattr(annotator_module, "annotate")
        #     annotate(self)
        # Note : es.update can use functions applied to each record (for the update)

    def get_year_from_toc(self, *, record_dict: dict) -> str:
        year = "NA"

        toc_key = self.__get_toc_key(record_dict=record_dict)
        toc_items = []
        try:
            if self.open_search.exists(index=self.TOC_INDEX, id=toc_key):
                res = self.__retrieve_toc_index(toc_key=toc_key)
                toc_items = res.get("colrev_ids", [])  # type: ignore
        except (TransportError, SerializationError):
            toc_items = []

        if len(toc_items) > 0:
            try:

                toc_records_colrev_id = toc_items[0]
                paper_hash = hashlib.sha256(
                    toc_records_colrev_id.encode("utf-8")
                ).hexdigest()
                res = self.open_search.get(
                    index=self.RECORD_INDEX,
                    id=str(paper_hash),
                )
                record_dict = res["_source"]  # type: ignore
                year = record_dict.get("year", "NA")

            except (
                colrev_exceptions.NotEnoughDataToIdentifyException,
                TransportError,
                SerializationError,
                KeyError,
            ):
                pass

        return year

    def retrieve_from_toc(
        self, *, record_dict: dict, similarity_threshold: float, include_file=False
    ) -> dict:
        toc_key = self.__get_toc_key(record_dict=record_dict)

        # 1. get TOC
        toc_items = []
        if self.open_search.exists(index=self.TOC_INDEX, id=toc_key):
            try:
                res = self.__retrieve_toc_index(toc_key=toc_key)
                toc_items = res.get("colrev_ids", [])  # type: ignore
            except (TransportError, SerializationError):
                toc_items = []

        # 2. get most similar record_dict
        elif len(toc_items) > 0:
            try:
                # TODO : we need to search tocs even if records are not complete:
                # and a NotEnoughDataToIdentifyException is thrown
                record_colrev_id = colrev.record.Record(
                    data=record_dict
                ).create_colrev_id()
                sim_list = []
                for toc_records_colrev_id in toc_items:
                    # Note : using a simpler similarity measure
                    # because the publication outlet parameters are already identical
                    sim_value = (
                        fuzz.ratio(record_colrev_id, toc_records_colrev_id) / 100
                    )
                    sim_list.append(sim_value)

                if max(sim_list) > similarity_threshold:
                    toc_records_colrev_id = toc_items[sim_list.index(max(sim_list))]
                    paper_hash = hashlib.sha256(
                        toc_records_colrev_id.encode("utf-8")
                    ).hexdigest()
                    res = self.open_search.get(
                        index=self.RECORD_INDEX,
                        id=str(paper_hash),
                    )
                    record_dict = res["_source"]  # type: ignore
                    return self.prep_record_for_return(
                        record_dict=record_dict, include_file=include_file
                    )
            except (colrev_exceptions.NotEnoughDataToIdentifyException, KeyError):
                pass

        raise colrev_exceptions.RecordNotInIndexException()

    def get_from_index_exact_match(
        self, *, index_name: str, key: str, value: str
    ) -> dict:

        res = {}
        try:
            resp = self.open_search.search(
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

    def retrieve(
        self, *, record_dict: dict, include_file: bool = False, include_colrev_ids=False
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
            return self.prep_record_for_return(
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
                    retrieved_record_dict = self.get_from_index_exact_match(
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

        return self.prep_record_for_return(
            record_dict=retrieved_record_dict,
            include_file=include_file,
            include_colrev_ids=include_colrev_ids,
        )

    def is_duplicate(self, *, record1_colrev_id: list, record2_colrev_id: list) -> str:
        """Convenience function to check whether two records are a duplicate"""

        try:

            # Ensure that we receive actual lists
            # otherwise, __retrieve_based_on_colrev_id iterates over a string and
            # self.open_search.search returns random results
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
            # see outlets_duplicated(...)

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

    def analyze(self) -> None:

        # TODO : update analyze() functionality based on es index
        # add to method signature:
        # (... , *, threshold: float = 0.95, ...)

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

        #     with open(r_file, encoding="utf8") as f:
        #         while True:
        #             line = f.readline()
        #             if not line:
        #                 break
        #             if "colrev_pdf_id" in line[:9]:
        #                 val = line[line.find("{") + 1 : line.rfind("}")]
        #                 colrev_pdf_ids.append(val)

        # colrev_pdf_ids_dupes = [
        #     item for item, count in
        #       collections.Counter(colrev_pdf_ids).items() if count > 1
        # ]

        # with open("non-unique-cpids.txt", "w", encoding="utf8") as o:
        #     o.write("\n".join(colrev_pdf_ids_dupes))
        # print("Export non-unique-cpids.txt")
        return


class Resources:

    # pylint: disable=too-few-public-methods
    curations_path = Path.home().joinpath("colrev/curated_metadata")
    annotators_path = Path.home().joinpath("colrev/annotators")

    def __init__(self):
        pass

    def install_curated_resource(self, *, curated_resource: str) -> bool:

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

        environment_manager = EnvironmentManager()
        if (repo_dir / Path("records.bib")).is_file():
            environment_manager.register_repo(path_to_register=repo_dir)
        elif (repo_dir / Path("annotate.py")).is_file():
            shutil.move(str(repo_dir), str(annotator_dir))
        elif (repo_dir / Path("readme.md")).is_file():
            text = Path(repo_dir / "readme.md").read_text(encoding="utf-8")
            for line in [x for x in text.splitlines() if "colrev env --install" in x]:
                if line == curated_resource:
                    continue
                self.install_curated_resource(
                    curated_resource=line.replace("colrev env --install ", "")
                )
        else:
            print(f"Error: repo does not contain a records.bib/linked repos {repo_dir}")
        return True


class ZoteroTranslationService:
    def __init__(self):
        pass

    def start_zotero_translators(self) -> None:

        if self.zotero_service_available():
            return

        zotero_image = EnvironmentManager.docker_images["zotero/translation-server"]

        client = docker.from_env()
        for container in client.containers.list():
            if zotero_image in str(container.image):
                return
        try:
            container = client.containers.run(
                zotero_image,
                ports={"1969/tcp": ("127.0.0.1", 1969)},
                auto_remove=True,
                detach=True,
            )
        except APIError:
            pass

        i = 0
        while i < 45:
            if self.zotero_service_available():
                break
            time.sleep(1)
            i += 1
        return

    def zotero_service_available(self) -> bool:

        url = "https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X"
        content_type_header = {"Content-type": "text/plain"}
        try:
            ret = requests.post(
                "http://127.0.0.1:1969/web",
                headers=content_type_header,
                data=url,
            )
            if ret.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        return False


class ScreenshotService:
    def __init__(self):
        pass

    # TODO : close service after the script has run

    def start_screenshot_service(self) -> None:

        if self.screenshot_service_available():
            return

        environment_manager = EnvironmentManager()
        environment_manager.build_docker_images()

        chrome_browserless_image = EnvironmentManager.docker_images[
            "browserless/chrome"
        ]

        client = docker.from_env()

        running_containers = [
            str(container.image) for container in client.containers.list()
        ]
        if chrome_browserless_image not in running_containers:
            client.containers.run(
                chrome_browserless_image,
                ports={"3000/tcp": ("127.0.0.1", 3000)},
                auto_remove=True,
                detach=True,
            )

        i = 0
        while i < 45:
            if self.screenshot_service_available():
                break
            time.sleep(1)
            i += 1
        return

    def screenshot_service_available(self) -> bool:

        content_type_header = {"Content-type": "text/plain"}

        browserless_chrome_available = False
        try:
            ret = requests.get(
                "http://127.0.0.1:3000/",
                headers=content_type_header,
            )
            browserless_chrome_available = ret.status_code == 200

        except requests.exceptions.ConnectionError:
            pass

        if browserless_chrome_available:
            return True
        return False

    def add_screenshot(
        self, *, record: colrev.record.Record, pdf_filepath: Path
    ) -> colrev.record.Record:
        if "url" not in record.data:
            return record

        urldate = datetime.today().strftime("%Y-%m-%d")

        json_val = {
            "url": record.data["url"],
            "options": {
                "displayHeaderFooter": True,
                "printBackground": False,
                "format": "A2",
            },
        }

        ret = requests.post("http://127.0.0.1:3000/pdf", json=json_val)

        if 200 == ret.status_code:
            with open(pdf_filepath, "wb") as file:
                file.write(ret.content)

            record.update_field(
                key="file",
                value=str(pdf_filepath),
                source="browserless/chrome screenshot",
            )
            record.data.update(
                colrev_status=colrev.record.RecordState.rev_prescreen_included
            )
            record.update_field(
                key="urldate", value=urldate, source="browserless/chrome screenshot"
            )

        else:
            print(
                "URL screenshot retrieval error "
                f"{ret.status_code}/{record.data['url']}"
            )

        return record


class GrobidService:

    GROBID_URL = "http://localhost:8070"

    def __init__(self):
        pass

    def check_grobid_availability(self, *, wait=True) -> bool:
        i = 0
        while True:
            i += 1
            time.sleep(1)
            try:
                ret = requests.get(self.GROBID_URL + "/api/isalive")
                if ret.text == "true":
                    return True
            except requests.exceptions.ConnectionError:
                pass
            if not wait:
                return False
            if i == -1:
                break
            if i > 20:
                raise requests.exceptions.ConnectionError()
        return True

    def start(self) -> None:
        # pylint: disable=consider-using-with

        try:
            res = self.check_grobid_availability(wait=False)
            if res:
                return
        except requests.exceptions.ConnectionError:
            pass

        grobid_image = EnvironmentManager.docker_images["lfoppiano/grobid"]

        logging.info("Running docker container created from %s", grobid_image)

        logging.info("Starting grobid service...")
        start_cmd = (
            f'docker run -t --rm -m "4g" -p 8070:8070 -p 8071:8071 {grobid_image}'
        )
        subprocess.Popen(
            [start_cmd],
            shell=True,
            stdin=None,
            stdout=open(os.devnull, "wb"),
            stderr=None,
            close_fds=True,
        )
        self.check_grobid_availability()


class TEIParser:
    ns = {
        "tei": "{http://www.tei-c.org/ns/1.0}",
        "w3": "{http://www.w3.org/XML/1998/namespace}",
    }
    nsmap = {
        "tei": "http://www.tei-c.org/ns/1.0",
        "w3": "http://www.w3.org/XML/1998/namespace",
    }

    def __init__(
        self,
        *,
        pdf_path: Path = None,
        tei_path: Path = None,
    ):
        """Creates a TEI file
        modes of operation:
        - pdf_path: create TEI and temporarily store in self.data
        - pfd_path and tei_path: create TEI and save in tei_path
        - tei_path: read TEI from file
        """

        # pylint: disable=consider-using-with
        assert pdf_path is not None or tei_path is not None
        if pdf_path is not None:
            if pdf_path.is_symlink():
                pdf_path = pdf_path.resolve()
        self.pdf_path = pdf_path
        self.tei_path = tei_path
        if pdf_path is not None:
            assert pdf_path.is_file()
        else:
            assert tei_path.is_file()  # type: ignore

        load_from_tei = False
        if tei_path is not None:
            if tei_path.is_file():
                load_from_tei = True

        if pdf_path is not None and not load_from_tei:
            grobid_service = GrobidService()
            grobid_service.start()
            # Note: we have more control and transparency over the consolidation
            # if we do it in the colrev process
            options = {}
            options["consolidateHeader"] = "0"
            options["consolidateCitations"] = "0"
            try:
                ret = requests.post(
                    GrobidService.GROBID_URL + "/api/processFulltextDocument",
                    files={"input": open(str(pdf_path), "rb")},
                    data=options,
                )

                # Possible extension: get header only (should be more efficient)
                # r = requests.post(
                #     GrobidService.GROBID_URL + "/api/processHeaderDocument",
                #     files=dict(input=open(filepath, "rb")),
                #     data=header_data,
                # )

                if ret.status_code != 200:
                    raise colrev_exceptions.TEIException()

                if b"[TIMEOUT]" in ret.content:
                    raise colrev_exceptions.TEITimeoutException()

                self.root = etree.fromstring(ret.content)

                if tei_path is not None:
                    tei_path.parent.mkdir(exist_ok=True, parents=True)
                    with open(tei_path, "wb") as file:
                        file.write(ret.content)

                    # Note : reopen/write to prevent format changes in the enhancement
                    with open(tei_path, "rb") as file:
                        xml_fstring = file.read()
                    self.root = etree.fromstring(xml_fstring)

                    tree = etree.ElementTree(self.root)
                    tree.write(str(tei_path), pretty_print=True, encoding="utf-8")
            except requests.exceptions.ConnectionError as exc:
                print(exc)
                print(str(pdf_path))
        elif tei_path is not None:
            with open(tei_path, encoding="utf-8") as file:
                xml_string = file.read()
            if "[BAD_INPUT_DATA]" in xml_string[:100]:
                raise colrev_exceptions.TEIException()
            self.root = etree.fromstring(xml_string)

    def get_tei_str(self) -> str:
        return etree.tostring(self.root).decode("utf-8")

    def __get_paper_title(self) -> str:
        title_text = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "fileDesc")
        if file_description is not None:
            title_stmt_node = file_description.find(
                ".//" + self.ns["tei"] + "titleStmt"
            )
            if title_stmt_node is not None:
                title_node = title_stmt_node.find(".//" + self.ns["tei"] + "title")
                if title_node is not None:
                    title_text = (
                        title_node.text if title_node.text is not None else "NA"
                    )
                    title_text = (
                        title_text.replace("(Completed paper)", "")
                        .replace("(Completed-paper)", "")
                        .replace("(Research-in-Progress)", "")
                        .replace("Completed Research Paper", "")
                    )
        return title_text

    def __get_paper_journal(self) -> str:
        journal_name = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    jtitle_node = journal_node.find(".//" + self.ns["tei"] + "title")
                    if jtitle_node is not None:
                        journal_name = (
                            jtitle_node.text if jtitle_node.text is not None else "NA"
                        )
                        if "NA" != journal_name:
                            words = journal_name.split()
                            if sum(word.isupper() for word in words) / len(words) > 0.8:
                                words = [word.capitalize() for word in words]
                                journal_name = " ".join(words)
        return journal_name

    def __get_paper_journal_volume(self) -> str:
        volume = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                    if imprint_node is not None:
                        vnode = imprint_node.find(
                            ".//" + self.ns["tei"] + "biblScope[@unit='volume']"
                        )
                        if vnode is not None:
                            volume = vnode.text if vnode.text is not None else "NA"
        return volume

    def __get_paper_journal_issue(self) -> str:
        issue = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                    if imprint_node is not None:
                        issue_node = imprint_node.find(
                            ".//" + self.ns["tei"] + "biblScope[@unit='issue']"
                        )
                        if issue_node is not None:
                            issue = (
                                issue_node.text if issue_node.text is not None else "NA"
                            )
        return issue

    def __get_paper_journal_pages(self) -> str:
        pages = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
            if journal_node is not None:
                imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                if imprint_node is not None:
                    page_node = imprint_node.find(
                        ".//" + self.ns["tei"] + "biblScope[@unit='page']"
                    )
                    if page_node is not None:
                        if (
                            page_node.get("from") is not None
                            and page_node.get("to") is not None
                        ):
                            pages = (
                                page_node.get("from", "")
                                + "--"
                                + page_node.get("to", "")
                            )
        return pages

    def __get_paper_year(self) -> str:
        year = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "monogr") is not None:
                journal_node = file_description.find(".//" + self.ns["tei"] + "monogr")
                if journal_node is not None:
                    imprint_node = journal_node.find(".//" + self.ns["tei"] + "imprint")
                    if imprint_node is not None:
                        date_node = imprint_node.find(".//" + self.ns["tei"] + "date")
                        if date_node is not None:
                            year = (
                                date_node.get("when", "")
                                if date_node.get("when") is not None
                                else "NA"
                            )
                            year = re.sub(r".*([1-2][0-9]{3}).*", r"\1", year)
        return year

    def get_author_name_from_node(self, *, author_node) -> str:
        authorname = ""

        author_pers_node = author_node.find(self.ns["tei"] + "persName")
        if author_pers_node is None:
            return authorname
        surname_node = author_pers_node.find(self.ns["tei"] + "surname")
        if surname_node is not None:
            surname = surname_node.text if surname_node.text is not None else ""
        else:
            surname = ""

        forename_node = author_pers_node.find(
            self.ns["tei"] + 'forename[@type="first"]'
        )
        if forename_node is not None:
            forename = forename_node.text if forename_node.text is not None else ""
        else:
            forename = ""

        if 1 == len(forename):
            forename = forename + "."

        middlename_node = author_pers_node.find(
            self.ns["tei"] + 'forename[@type="middle"]'
        )
        if middlename_node is not None:
            middlename = (
                " " + middlename_node.text if middlename_node.text is not None else ""
            )
        else:
            middlename = ""

        if 1 == len(middlename):
            middlename = middlename + "."

        authorname = surname + ", " + forename + middlename

        authorname = (
            authorname.replace("\n", " ")
            .replace("\r", "")
            .replace("•", "")
            .replace("+", "")
            .replace("Dipl.", "")
            .replace("Prof.", "")
            .replace("Dr.", "")
            .replace("&apos", "'")
            .replace("❚", "")
            .replace("~", "")
            .replace("®", "")
            .replace("|", "")
        )

        authorname = re.sub("^Paper, Short; ", "", authorname)
        return authorname

    def __get_paper_authors(self) -> str:
        author_string = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        author_list = []

        if file_description is not None:
            if file_description.find(".//" + self.ns["tei"] + "analytic") is not None:
                analytic_node = file_description.find(
                    ".//" + self.ns["tei"] + "analytic"
                )
                if analytic_node is not None:
                    for author_node in analytic_node.iterfind(
                        self.ns["tei"] + "author"
                    ):

                        authorname = self.get_author_name_from_node(
                            author_node=author_node
                        )
                        if authorname in ["Paper, Short"]:
                            continue
                        if authorname not in [", ", ""]:
                            author_list.append(authorname)

                    author_string = " and ".join(author_list)

                    if author_string is None:
                        author_string = "NA"
                    if "" == author_string.replace(" ", "").replace(",", "").replace(
                        ";", ""
                    ):
                        author_string = "NA"
        return author_string

    def __get_paper_doi(self) -> str:
        doi = "NA"
        file_description = self.root.find(".//" + self.ns["tei"] + "sourceDesc")
        if file_description is not None:
            bibl_struct = file_description.find(".//" + self.ns["tei"] + "biblStruct")
            if bibl_struct is not None:
                dois = bibl_struct.findall(".//" + self.ns["tei"] + "idno[@type='DOI']")
                for res in dois:
                    if res.text is not None:
                        doi = res.text
        return doi

    def get_abstract(self) -> str:

        html_tag_regex = re.compile("<.*?>")

        def cleanhtml(raw_html):
            cleantext = re.sub(html_tag_regex, "", raw_html)
            return cleantext

        abstract_text = "NA"
        profile_description = self.root.find(".//" + self.ns["tei"] + "profileDesc")
        if profile_description is not None:
            abstract_node = profile_description.find(
                ".//" + self.ns["tei"] + "abstract"
            )
            html_str = etree.tostring(abstract_node).decode("utf-8")
            abstract_text = cleanhtml(html_str)
        return abstract_text

    def get_metadata(self) -> dict:

        record = {
            "ENTRYTYPE": "article",
            "title": self.__get_paper_title(),
            "author": self.__get_paper_authors(),
            "journal": self.__get_paper_journal(),
            "year": self.__get_paper_year(),
            "volume": self.__get_paper_journal_volume(),
            "number": self.__get_paper_journal_issue(),
            "pages": self.__get_paper_journal_pages(),
            "doi": self.__get_paper_doi(),
        }

        for key, value in record.items():
            if "file" != key:
                record[key] = value.replace("}", "").replace("{", "").rstrip("\\")
            else:
                print(f"problem in filename: {key}")

        return record

    def get_paper_keywords(self) -> list:
        keywords = []
        for keyword_list in self.root.iter(self.ns["tei"] + "keywords"):
            for keyword in keyword_list.iter(self.ns["tei"] + "term"):
                keywords.append(keyword.text)
        return keywords

    # (individual) bibliography-reference elements  ----------------------------

    def __get_reference_bibliography_id(self, *, reference) -> str:
        if "ID" in reference.attrib:
            return reference.attrib["ID"]
        return ""

    def __get_reference_bibliography_tei_id(self, *, reference) -> str:
        return reference.attrib[self.ns["w3"] + "id"]

    def __get_reference_author_string(self, *, reference) -> str:
        author_list = []
        if reference.find(self.ns["tei"] + "analytic") is not None:
            authors_node = reference.find(self.ns["tei"] + "analytic")
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            authors_node = reference.find(self.ns["tei"] + "monogr")

        for author_node in authors_node.iterfind(self.ns["tei"] + "author"):

            authorname = self.get_author_name_from_node(author_node=author_node)

            if authorname not in [", ", ""]:
                author_list.append(authorname)

        author_string = " and ".join(author_list)

        author_string = (
            author_string.replace("\n", " ")
            .replace("\r", "")
            .replace("•", "")
            .replace("+", "")
            .replace("Dipl.", "")
            .replace("Prof.", "")
            .replace("Dr.", "")
            .replace("&apos", "'")
            .replace("❚", "")
            .replace("~", "")
            .replace("®", "")
            .replace("|", "")
        )

        if author_string is None:
            author_string = "NA"
        if "" == author_string.replace(" ", "").replace(",", "").replace(";", ""):
            author_string = "NA"
        return author_string

    def __get_reference_title_string(self, *, reference) -> str:
        title_string = ""
        if reference.find(self.ns["tei"] + "analytic") is not None:
            title = reference.find(self.ns["tei"] + "analytic").find(
                self.ns["tei"] + "title"
            )
        elif reference.find(self.ns["tei"] + "monogr") is not None:
            title = reference.find(self.ns["tei"] + "monogr").find(
                self.ns["tei"] + "title"
            )
        if title is None:
            title_string = "NA"
        else:
            title_string = title.text
        return title_string

    def __get_reference_year_string(self, *, reference) -> str:
        year_string = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            year = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .find(self.ns["tei"] + "date")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            year = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .find(self.ns["tei"] + "date")
            )

        if year is not None:
            for name, value in sorted(year.items()):
                if name == "when":
                    year_string = value
                else:
                    year_string = "NA"
        else:
            year_string = "NA"
        return year_string

    def __get_reference_page_string(self, *, reference) -> str:
        page_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            page_list = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='page']")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            page_list = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='page']")
            )

        for page in page_list:
            if page is not None:
                for name, value in sorted(page.items()):
                    if name == "from":
                        page_string += value
                    if name == "to":
                        page_string += "--" + value
            else:
                page_string = "NA"

        return page_string

    def __get_reference_number_string(self, *, reference) -> str:
        number_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            number_list = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='issue']")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            number_list = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='issue']")
            )

        for number in number_list:
            if number is not None:
                number_string = number.text
            else:
                number_string = "NA"

        return number_string

    def __get_reference_volume_string(self, *, reference) -> str:
        volume_string = ""

        if reference.find(self.ns["tei"] + "monogr") is not None:
            volume_list = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='volume']")
            )
        elif reference.find(self.ns["tei"] + "analytic") is not None:
            volume_list = (
                reference.find(self.ns["tei"] + "analytic")
                .find(self.ns["tei"] + "imprint")
                .findall(self.ns["tei"] + "biblScope[@unit='volume']")
            )

        for volume in volume_list:
            if volume is not None:
                volume_string = volume.text
            else:
                volume_string = "NA"

        return volume_string

    def __get_reference_journal_string(self, *, reference) -> str:
        journal_title = ""
        if reference.find(self.ns["tei"] + "monogr") is not None:
            journal_title = (
                reference.find(self.ns["tei"] + "monogr")
                .find(self.ns["tei"] + "title")
                .text
            )
        if journal_title is None:
            journal_title = ""
        return journal_title

    def __get_entrytype(self, *, reference) -> str:
        entrytype = "misc"
        if reference.find(self.ns["tei"] + "monogr") is not None:
            monogr_node = reference.find(self.ns["tei"] + "monogr")
            title_node = monogr_node.find(self.ns["tei"] + "title")
            if title_node is not None:
                if "j" == title_node.get("level", "NA"):
                    entrytype = "article"
                else:
                    entrytype = "book"
        return entrytype

    def get_bibliography(self):

        bibliographies = self.root.iter(self.ns["tei"] + "listBibl")
        tei_bib_db = []
        for bibliography in bibliographies:
            for reference in bibliography:
                try:
                    entrytype = self.__get_entrytype(reference=reference)
                    if "article" == entrytype:
                        ref_rec = {
                            "ID": self.__get_reference_bibliography_id(
                                reference=reference
                            ),
                            "ENTRYTYPE": entrytype,
                            "tei_id": self.__get_reference_bibliography_tei_id(
                                reference=reference
                            ),
                            "author": self.__get_reference_author_string(
                                reference=reference
                            ),
                            "title": self.__get_reference_title_string(
                                reference=reference
                            ),
                            "year": self.__get_reference_year_string(
                                reference=reference
                            ),
                            "journal": self.__get_reference_journal_string(
                                reference=reference
                            ),
                            "volume": self.__get_reference_volume_string(
                                reference=reference
                            ),
                            "number": self.__get_reference_number_string(
                                reference=reference
                            ),
                            "pages": self.__get_reference_page_string(
                                reference=reference
                            ),
                        }
                    elif "book" == entrytype:
                        ref_rec = {
                            "ID": self.__get_reference_bibliography_id(
                                reference=reference
                            ),
                            "ENTRYTYPE": entrytype,
                            "tei_id": self.__get_reference_bibliography_tei_id(
                                reference=reference
                            ),
                            "author": self.__get_reference_author_string(
                                reference=reference
                            ),
                            "title": self.__get_reference_title_string(
                                reference=reference
                            ),
                            "year": self.__get_reference_year_string(
                                reference=reference
                            ),
                        }
                    elif "misc" == entrytype:
                        ref_rec = {
                            "ID": self.__get_reference_bibliography_id(
                                reference=reference
                            ),
                            "ENTRYTYPE": entrytype,
                            "tei_id": self.__get_reference_bibliography_tei_id(
                                reference=reference
                            ),
                            "author": self.__get_reference_author_string(
                                reference=reference
                            ),
                            "title": self.__get_reference_title_string(
                                reference=reference
                            ),
                        }
                except etree.XMLSyntaxError:
                    continue

                ref_rec = {k: v for k, v in ref_rec.items() if v is not None}
                # print(ref_rec)
                tei_bib_db.append(ref_rec)

        return tei_bib_db

    def get_citations_per_section(self) -> dict:
        section_citations = {}
        sections = self.root.iter(self.ns["tei"] + "head")
        for section in sections:
            section_name = section.text
            if section_name is None:
                continue
            citation_nodes = section.getparent().iter(self.ns["tei"] + "ref")
            citations = [
                x.get("target", "NA").replace("#", "")
                for x in citation_nodes
                if "bibr" == x.get("type", "NA")
            ]
            citations = list(filter(lambda a: a != "NA", citations))
            if len(citations) > 0:
                section_citations[section_name.lower()] = citations
        return section_citations

    def mark_references(self, *, records):

        tei_records = self.get_bibliography()
        for record_dict in tei_records:
            if "title" not in record_dict:
                continue

            max_sim = 0.9
            max_sim_record = {}
            for local_record_dict in records:
                if local_record_dict["status"] not in [
                    colrev.record.RecordState.rev_included,
                    colrev.record.RecordState.rev_synthesized,
                ]:
                    continue
                rec_sim = colrev.record.Record.get_record_similarity(
                    record_a=colrev.record.Record(data=record_dict),
                    record_b=colrev.record.Record(data=local_record_dict),
                )
                if rec_sim > max_sim:
                    max_sim_record = local_record_dict
                    max_sim = rec_sim
            if len(max_sim_record) == 0:
                continue

            # Record found: mark in tei
            bibliography = self.root.find(".//" + self.ns["tei"] + "listBibl")
            # mark reference in bibliography
            for ref in bibliography:
                if ref.get(self.ns["w3"] + "id") == record_dict["tei_id"]:
                    ref.set("ID", max_sim_record["ID"])
            # mark reference in in-text citations
            for reference in self.root.iter(self.ns["tei"] + "ref"):
                if "target" in reference.keys():
                    if reference.get("target") == f"#{record_dict['tei_id']}":
                        reference.set("ID", max_sim_record["ID"])

            # if settings file available: dedupe_io match agains records

        if self.tei_path:
            tree = etree.ElementTree(self.root)
            tree.write(str(self.tei_path), pretty_print=True, encoding="utf-8")

        return self.root


class PDFHashService:
    # pylint: disable=too-few-public-methods
    def __init__(self):
        pass

    def get_pdf_hash(self, *, pdf_path: Path, page_nr: int, hash_size: int = 32) -> str:

        assert isinstance(page_nr, int)
        assert isinstance(hash_size, int)

        pdf_path = pdf_path.resolve()
        pdf_dir = pdf_path.parents[0]

        command = (
            f'docker run --rm -v "{pdf_dir}:/home/docker" '
            f'pdf_hash python app.py "{pdf_path.name}" {page_nr} {hash_size}'
        )
        ret = subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

        # TODO : raise exception if errors occur

        return ret.decode("utf-8").replace("\n", "")


if __name__ == "__main__":
    pass
