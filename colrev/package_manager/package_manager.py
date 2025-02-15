#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import platform
import shutil
import subprocess
import typing
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

        # Notes:
        # Cannot import directly and check whether it fails
        # because the package format is non-standard (".")
        # We deactivate the is_installed() temporarily
        # until internal colrev packages comply with naming conventions.
        if platform.system() in ["Darwin", "Windows", "Linux"]:
            return True  # Return True for macOS, Linux, and Windows
        print(package_name)

        # try:
        #     if sys.version_info >= (3, 10):
        #         # Use packages_distributions in Python 3.10+
        #         from importlib.metadata import packages_distributions

        #         installed_packages = packages_distributions()

        #         if package_name.replace("-", "_") in installed_packages:
        #             return True
        #         if (
        #             "src" in installed_packages
        #             and package_name.replace("-", "_") in installed_packages["src"]
        #         ):
        #             return True

        #         return False
        #     else:
        #         # Fallback for Python < 3.10 using the distribution method
        #         importlib.metadata.distribution(package_name.replace("-", "_"))
        #         return True
        # except PackageNotFoundError:
        #     return False
        # except importlib.metadata.PackageNotFoundError:
        #     return False
        return True

    def _get_packages_to_install(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
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

        return packages

    def install_project(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        """Install all packages required for the CoLRev project"""

        review_manager.logger.info("Install project")
        packages = self._get_packages_to_install(review_manager=review_manager)
        if len(packages) == 0:
            review_manager.logger.info("All packages are already installed")
            return

        self.install(packages=packages)

    def install(
        self,
        *,
        packages: typing.List[str],
        upgrade: bool = True,
        editable: bool = False,
    ) -> None:
        """Install packages using uv if available, otherwise fallback to pip"""

        # Check if `uv` is installed, fallback to `pip` if not
        package_manager = "uv pip" if shutil.which("uv") else "pip"

        internal_packages_dict = (
            colrev.package_manager.colrev_internal_packages.get_internal_packages_dict()
        )

        if len(packages) == 1 and packages[0] == "all_internal_packages":
            packages = list(internal_packages_dict.keys())

        # Install internal colrev packages first
        colrev_packages = []
        for package in packages:
            if package in internal_packages_dict:
                colrev_packages.append(package)
        packages = [p for p in packages if p not in colrev_packages]

        print(
            f"Installing ColRev packages: {colrev_packages + packages} using {package_manager}"
        )

        install_args = [package_manager, "install"]
        if upgrade:
            install_args.append("--upgrade")
        if editable:
            install_args.append("--editable")

        # Install both internal and external packages in a single command
        all_packages = [
            internal_packages_dict[p] if p in internal_packages_dict else p
            for p in colrev_packages
        ] + packages

        install_args += all_packages
        subprocess.run(install_args, check=True)
