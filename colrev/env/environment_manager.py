#! /usr/bin/env python
"""Manages environment registry, services, and stauts"""
from __future__ import annotations

import json
import os
import subprocess
import typing
from datetime import datetime
from pathlib import Path

import docker
import git
import pandas as pd
import yaml
from git.exc import InvalidGitRepositoryError
from git.exc import NoSuchPathError
from opensearchpy.exceptions import NotFoundError
from yaml import safe_load

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


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
        self.environment_registry = self.load_environment_registry()

    def load_environment_registry(self) -> list:
        """Load the local registry"""
        environment_registry_path = self.registry
        environment_registry = []
        if environment_registry_path.is_file():
            with open(environment_registry_path, encoding="utf8") as file:
                environment_registry_df = pd.json_normalize(safe_load(file))
                environment_registry = environment_registry_df.to_dict("records")

        return environment_registry

    def save_environment_registry(self, *, updated_registry: list) -> None:
        """Save the local registry"""
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
        """Register a repository"""
        environment_registry = self.load_environment_registry()
        registered_paths = [x["repo_source_path"] for x in environment_registry]

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
        environment_registry.append(new_record)
        self.save_environment_registry(updated_registry=environment_registry)
        print(f"Registered path ({path_to_register})")

    def get_name_mail_from_git(self) -> typing.Tuple[str, str]:
        """Get the committer name and email from git (globals)"""
        ggit_conf_path = Path.home() / Path(".gitconfig")
        global_conf_details = ("NA", "NA")
        if ggit_conf_path.is_file():
            glob_git_conf = git.GitConfigParser([str(ggit_conf_path)], read_only=True)
            global_conf_details = (
                glob_git_conf.get("user", "name"),
                glob_git_conf.get("user", "email"),
            )
        if ("NA", "NA") == global_conf_details:
            raise colrev_exceptions.CoLRevException(
                "Global git variables (user name and email) not available."
            )
        return global_conf_details

    def build_docker_images(self) -> None:
        """Build the docker images"""
        client = docker.from_env()

        repo_tags = [image.tags for image in client.images.list()]
        repo_tags = [tag[0][: tag[0].find(":")] for tag in repo_tags if tag]

        assert colrev.review_manager.__file__
        colrev_path = Path("")
        if colrev.review_manager.__file__:
            colrev_path = Path(colrev.review_manager.__file__).parents[0]

        for img_name, img_version in self.docker_images.items():
            if img_name not in repo_tags:

                if "bibutils" == img_name:
                    print("Building bibutils Docker image...")
                    context_path = colrev_path / Path("docker/bibutils")
                    client.images.build(path=str(context_path), tag="bibutils:latest")

                elif "pdf_hash" == img_name:
                    print("Building pdf_hash Docker image...")
                    context_path = colrev_path / Path("docker/pdf_hash")
                    client.images.build(path=str(context_path), tag="pdf_hash:latest")

                else:
                    print(f"Pulling {img_name} Docker image...")
                    client.images.pull(img_version)

    def check_git_installed(self) -> None:
        """Check whether git is installed"""
        # pylint: disable=consider-using-with

        try:
            with open("/dev/null", "w", encoding="utf8") as null:
                subprocess.Popen("git", stdout=null, stderr=null)
        except OSError as exc:
            raise colrev_exceptions.MissingDependencyError("git") from exc

    def check_docker_installed(self) -> None:
        """Check whether Docker is installed"""
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

    def get_environment_details(
        self, *, review_manager: colrev.review_manager.ReviewManager
    ) -> dict:
        """Get the environment details"""

        def get_last_modified() -> str:

            list_of_files = local_index.opensearch_index.glob(
                "**/*"
            )  # * means all if need specific format then *.csv
            latest_file = max(list_of_files, key=os.path.getmtime)
            last_mod = datetime.fromtimestamp(latest_file.lstat().st_mtime)
            return last_mod.strftime("%Y-%m-%d %H:%M")

        local_index = review_manager.get_local_index()

        environment_details = {}
        size = 0
        last_modified = "NOT_INITIATED"
        status = ""

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
            "path": str(local_index.local_environment_path),
            "status": status,
        }

        environment_stats = self.get_environment_stats()

        environment_details["local_repos"] = {
            "repos": environment_stats["repos"],
            "broken_links": environment_stats["broken_links"],
        }
        return environment_details

    def get_environment_stats(self) -> dict:
        """Get the environment stats"""
        local_repos = self.load_environment_registry()
        repos = []
        broken_links = []
        for repo in local_repos:
            try:
                cp_review_manager = colrev.review_manager.ReviewManager(
                    path_str=repo["repo_source_path"]
                )
                check_operation = colrev.operation.CheckOperation(
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
                git_repo = check_operation.review_manager.dataset.get_repo()
                for remote in git_repo.remotes:
                    if remote.url:
                        repo["remote"] = True
                repo[
                    "behind_remote"
                ] = check_operation.review_manager.dataset.behind_remote()

                repos.append(repo)
            except (NoSuchPathError, InvalidGitRepositoryError):
                broken_links.append(repo)
        return {"repos": repos, "broken_links": broken_links}

    def get_curated_outlets(self) -> list:
        """Get the curated outlets"""
        curated_outlets: typing.List[str] = []
        for repo_source_path in [
            x["repo_source_path"]
            for x in self.load_environment_registry()
            if "colrev/curated_metadata/" in x["repo_source_path"]
        ]:
            try:
                with open(f"{repo_source_path}/readme.md", encoding="utf-8") as file:
                    first_line = file.readline()
                curated_outlets.append(first_line.lstrip("# ").replace("\n", ""))

                with open(
                    f"{repo_source_path}/data/records.bib", encoding="utf-8"
                ) as file:
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


if __name__ == "__main__":
    pass
