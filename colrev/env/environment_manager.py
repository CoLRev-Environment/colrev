#! /usr/bin/env python
"""Manages environment registry, services, and stauts"""
from __future__ import annotations

import json
import logging
import typing
from pathlib import Path

import git
import yaml

import colrev.exceptions as colrev_exceptions
import colrev.ops.check
import colrev.process.operation
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import Filepaths
from colrev.env.utils import dict_set_nested
from colrev.env.utils import get_by_path


class EnvironmentManager:
    """The EnvironmentManager manages environment resources and services"""

    load_yaml = False

    def __init__(self) -> None:
        self.environment_registry = self.load_environment_registry()
        self._registered_ports: typing.List[str] = []

    def register_ports(self, ports: typing.List[str]) -> None:
        """Register a localhost port to avoid conflicts"""
        for port_to_register in ports:
            if port_to_register in self._registered_ports:
                raise colrev_exceptions.PortAlreadyRegisteredException(
                    f"Port {port_to_register} already registered"
                )
            self._registered_ports.append(port_to_register)

    def load_environment_registry(self) -> dict:
        """Load the local registry"""
        environment_registry = {}
        if Filepaths.REGISTRY_FILE.is_file():
            self.load_yaml = False
            with open(Filepaths.REGISTRY_FILE, encoding="utf8") as file:
                environment_registry = json.load(fp=file)
            # assert "local_index" in environment_registry
            # assert "packages" in environment_registry

        return environment_registry

    def local_repos(self) -> list:
        """gets local repos from local index"""
        self.environment_registry = self.load_environment_registry()
        if (
            "local_index" not in self.environment_registry
            or "repos" not in self.environment_registry["local_index"]
        ):
            return []
        return self.environment_registry["local_index"]["repos"]

    def _cast_values_to_str(self, data) -> dict:  # type: ignore
        result = {}
        for key, value in data.items():
            if isinstance(value, dict):
                result[key] = self._cast_values_to_str(value)
            elif isinstance(value, list):
                result[key] = [self._cast_values_to_str(v) for v in value]  # type: ignore
            else:
                result[key] = str(value)  # type: ignore
        return result

    def save_environment_registry(self, updated_registry: dict) -> None:
        """Save the local registry"""
        Filepaths.REGISTRY_FILE.parents[0].mkdir(parents=True, exist_ok=True)
        with open(Filepaths.REGISTRY_FILE, "w", encoding="utf8") as file:
            json.dump(
                dict(self._cast_values_to_str(updated_registry)), indent=4, fp=file
            )

    def register_repo(
        self,
        path_to_register: Path,
        logger: logging.Logger = logging.getLogger(__name__),
    ) -> None:
        """Register a repository"""
        path_to_register = path_to_register.resolve().absolute()
        self.environment_registry = self.load_environment_registry()

        if "local_index" not in self.environment_registry:
            self.environment_registry["local_index"] = {"repos": []}
        registered_paths = [
            x["repo_source_path"]
            for x in self.environment_registry["local_index"]["repos"]
        ]

        if registered_paths:
            if str(path_to_register) in registered_paths:
                logger.warning(f"Warning: Path already registered: {path_to_register}")
                return
        else:
            logger.info("Register %s in %s", path_to_register, Filepaths.REGISTRY_FILE)

        new_record = {
            "repo_name": path_to_register.stem,
            "repo_source_path": path_to_register,
        }
        git_repo = git.Repo(path_to_register)
        try:
            remote_urls = list(git_repo.remote("origin").urls)
            new_record["repo_source_url"] = remote_urls[0]
        except (ValueError, IndexError):  # pragma: no cover
            for remote in git_repo.remotes:
                if remote.url:
                    new_record["repo_source_url"] = remote.url
                    break
        self.environment_registry["local_index"]["repos"].append(new_record)
        self.save_environment_registry(self.environment_registry)
        logger.info(f"Registered path ({path_to_register})")

    @classmethod
    def get_name_mail_from_git(cls) -> typing.Tuple[str, str]:  # pragma: no cover
        """Get the committer name and email from git (globals)"""
        global_conf_details = ("NA", "NA")
        try:
            username = git.config.GitConfigParser().get_value("user", "name")
            email = git.config.GitConfigParser().get_value("user", "email")
            global_conf_details = (username, email)
        except (git.config.cp.NoSectionError, git.config.cp.NoOptionError) as exc:
            raise colrev_exceptions.CoLRevException(
                "Global git variables (user name and email) not available."
            ) from exc
        return global_conf_details

    def check_git_installed(self) -> None:  # pragma: no cover
        """Check whether git is installed"""

        try:
            git_instance = git.Git()
            _ = git_instance.version()
        except git.GitCommandNotFound as exc:
            print(exc)

    def _get_status(self, review_manager: colrev.review_manager.ReviewManager) -> dict:
        status_dict = {}
        status_yml = review_manager.paths.status
        with open(status_yml, encoding="utf8") as stream:
            try:
                status_dict = yaml.safe_load(stream)
            except yaml.YAMLError as exc:  # pragma: no cover
                print(exc)
        return status_dict

    def get_environment_details(self) -> dict:
        """Get the environment details"""

        environment_details = {}
        size = 0
        last_modified = "NOT_INITIATED"
        status = "TODO"

        size = 0
        environment_details["index"] = {
            "size": size,
            "last_modified": last_modified,
            "path": str(Filepaths.LOCAL_ENVIRONMENT_DIR),
            "status": status,
        }

        environment_stats = self._get_environment_stats()

        environment_details["local_repos"] = {
            "repos": environment_stats["repos"],
            "broken_links": environment_stats["broken_links"],
        }
        return environment_details

    def _get_environment_stats(self) -> dict:
        """Get the environment stats"""

        local_repos = self.local_repos()
        repos = []
        broken_links = []
        for repo in local_repos:
            try:
                cp_review_manager = colrev.review_manager.ReviewManager(
                    path_str=repo["repo_source_path"]
                )
                check_operation = colrev.ops.check.CheckOperation(cp_review_manager)
                repo_stat = self._get_status(cp_review_manager)
                repo["size"] = repo_stat["overall"]["md_processed"]
                repo["progress"] = -1
                if repo_stat["atomic_steps"] != 0:
                    repo["progress"] = round(
                        repo_stat["completed_atomic_steps"] / repo_stat["atomic_steps"],
                        2,
                    )

                git_repo = check_operation.review_manager.dataset.get_repo()
                repo["remote"] = bool(git_repo.remotes)
                repo["behind_remote"] = (
                    check_operation.review_manager.dataset.behind_remote()
                )

                repos.append(repo)
            except (
                colrev_exceptions.CoLRevException,
                git.InvalidGitRepositoryError,
            ):  # pragma: no cover
                broken_links.append(repo)
        return {"repos": repos, "broken_links": broken_links}

    def get_curated_outlets(self) -> list:
        """Get the curated outlets"""
        curated_outlets: typing.List[str] = []
        for repo_source_path in [
            x["repo_source_path"]
            for x in self.local_repos()
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
                            Fields.JOURNAL == line.lstrip()[:7]
                            and "journal:" != line.lstrip()[:8]
                        ):
                            journal = line[line.find("{") + 1 : line.rfind("}")]
                            if journal != FieldValues.UNKNOWN:
                                outlets.append(journal)
                        if (
                            line.lstrip()[:9] == Fields.BOOKTITLE
                            and line.lstrip()[:10] != "booktitle:"
                        ):
                            booktitle = line[line.find("{") + 1 : line.rfind("}")]
                            if booktitle != FieldValues.UNKNOWN:
                                outlets.append(booktitle)

                    if len(set(outlets)) > 1:  # pragma: no cover
                        raise colrev_exceptions.CuratedOutletNotUnique(
                            "Error: Duplicate outlets in curated_metadata of "
                            f"{repo_source_path} : {','.join(list(set(outlets)))}"
                        )
            except FileNotFoundError as exc:  # pragma: no cover
                print(exc)

        return curated_outlets

    def _dict_keys_exists(self, element: dict, *keys: str) -> bool:
        """Check if *keys (nested) exists in `element` (dict)."""
        if len(keys) < 2:
            raise AttributeError(
                "keys_exists() expects at least two arguments, one given."
            )

        _element = element
        for key in keys:
            try:
                _element = _element[key]
            except KeyError:
                return False
        return True

    def get_settings_by_key(self, key: str) -> str | None:
        """Loads setting by the given key"""
        environment_registry = self.load_environment_registry()
        keys = key.split(".")
        if self._dict_keys_exists(environment_registry, *keys):
            return get_by_path(environment_registry, keys)
        return None

    def update_registry(self, key: str, value: str) -> None:
        """updates given key in the registry with new value"""

        keys = key.split(".")
        # We don't want to allow user to replace any core settings, so check for packages key
        if keys[0] != "packages" or len(keys) < 2:
            raise colrev_exceptions.PackageSettingMustStartWithPackagesException(key)
        self.environment_registry = self.load_environment_registry()
        dict_set_nested(self.environment_registry, keys, value)
        self.save_environment_registry(self.environment_registry)
