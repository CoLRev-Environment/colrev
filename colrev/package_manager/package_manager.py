#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import typing
from importlib.metadata import distribution
from importlib.metadata import PackageNotFoundError
from typing import Any

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.colrev_internal_packages
import colrev.package_manager.package
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Filepaths


class PackageManager:
    """The PackageManager provides functionality for package lookup and discovery"""

    def _get_package_identifiers(self) -> list:
        group = "colrev"
        return [
            dist.metadata["name"]
            for dist in importlib.metadata.distributions()
            for ep in dist.entry_points
            if ep.group == group
        ]

    def _load_type_identifier_endpoint_dict(self) -> dict:
        type_identifier_endpoint_dict: typing.Dict[
            EndpointType, typing.Dict[str, Any]
        ] = {endpoint_type: {} for endpoint_type in EndpointType}

        for package_identifier in self._get_package_identifiers():
            try:
                package = colrev.package_manager.package.Package(package_identifier)
                package.add_to_type_identifier_endpoint_dict(
                    type_identifier_endpoint_dict
                )
            except colrev_exceptions.MissingDependencyError as exc:
                print(exc)

        return type_identifier_endpoint_dict

    def discover_packages(self, *, package_type: EndpointType) -> typing.Dict:
        """Discover packages (registered in the CoLRev environment)"""

        # [{'package_endpoint_identifier': 'colrev.abi_inform_proquest',
        #   'status': '|EXPERIMENTAL|',
        #   'short_description': 'ABI/INFORM (ProQuest) ...'},
        #  ...]
        with open(Filepaths.PACKAGES_ENDPOINTS_JSON, encoding="utf-8") as file:
            package_endpoints = json.load(file)
            return package_endpoints[package_type.value]

    def discover_installed_packages(self, *, package_type: EndpointType) -> typing.Dict:
        """Discover installed packages"""

        # {EndpointType.review_type:
        #   {'colrev.blank': {'endpoint': 'colrev.packages.review_types.blank.BlankReview'},
        #     ...
        # }

        type_identifier_endpoint_dict = self._load_type_identifier_endpoint_dict()
        return type_identifier_endpoint_dict[package_type]

    def get_package_endpoint_class(  # type: ignore
        self, *, package_type: EndpointType, package_identifier: str
    ):
        """Load a package endpoint"""

        package = colrev.package_manager.package.Package(package_identifier)
        return package.get_endpoint_class(package_type)

    def is_installed(self, package_name: str) -> bool:
        """Check if a package is installed"""

        try:
            p_dist = distribution(package_name.replace("-", "_"))
        except PackageNotFoundError:
            return False
        return p_dist is not None

    def _get_packages_to_install(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        force_reinstall: bool,
    ) -> typing.List[str]:

        review_manager.logger.info("Packages:")
        packages = review_manager.settings.get_packages()

        installed_packages = []
        for package in packages:
            if self.is_installed(package):
                installed_packages.append(package)
                review_manager.logger.info(
                    f" {Colors.GREEN}{package}: installed{Colors.END}"
                )
            else:
                review_manager.logger.info(
                    f" {Colors.ORANGE}{package}: not installed{Colors.END}"
                )

        if not force_reinstall:
            packages = [p for p in packages if p not in installed_packages]

        return packages

    def install_project(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        force_reinstall: bool,
    ) -> None:
        """Install all packages required for the CoLRev project"""

        review_manager.logger.info("Install project")
        packages = self._get_packages_to_install(
            review_manager=review_manager, force_reinstall=force_reinstall
        )
        if len(packages) == 0:
            review_manager.logger.info("All packages are already installed")
            return

        self.install(packages=packages)

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    def install(
        self,
        *,
        packages: typing.List[str],
        upgrade: bool = True,
        editable: str = "",
        force_reinstall: bool = True,
        no_cache_dir: bool = True,
    ) -> None:
        """Install packages"""

        internal_packages_dict = (
            colrev.package_manager.colrev_internal_packages.get_internal_packages_dict()
        )

        if len(packages) == 1 and packages[0] == "all_internal_packages":
            packages = list(internal_packages_dict.keys())

        # Install packages from colrev monorepository first
        colrev_packages = []
        for package in packages:
            if package in internal_packages_dict:
                colrev_packages.append(package)
        packages = [p for p in packages if p not in colrev_packages]

        print(f"ColRev packages: {colrev_packages}")
        if colrev_packages:

            colrev_package_paths = [
                p_path
                for p_name, p_path in internal_packages_dict.items()
                if p_name in colrev_packages
            ]
            args = [sys.executable, "-m", "pip", "install"]
            args += colrev_package_paths
            if upgrade:
                args += ["--upgrade"]
            if editable:
                args += ["--editable", editable]
            if force_reinstall:
                args += ["--force-reinstall"]
            if no_cache_dir:
                args += ["--no-cache-dir"]
            # sys.argv = args
            # run_module("pip", run_name="__main__")
            # use subprocess because run_module does not return control
            subprocess.run(args, check=False)

        print(f"Other packages: {packages}")
        if packages:
            args = [sys.executable, "-m", "pip", "install"]
            if upgrade:
                args += ["--upgrade"]
            if editable:
                args += ["--editable", editable]
            if force_reinstall:
                args += ["--force-reinstall"]
            if no_cache_dir:
                args += ["--no-cache-dir"]
            args += list(packages)
            # sys.argv = args
            # run_module("pip", run_name="__main__")
            # use subprocess because run_module does not return control
            subprocess.run(args, check=False)
