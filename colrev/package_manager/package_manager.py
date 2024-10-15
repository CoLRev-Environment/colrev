#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import subprocess
import sys
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

    def is_installed(self, package_name: str, *, uv: bool = False) -> bool:
        """Check if a package is installed"""

        fixed_package_name = package_name.replace("_", "-").replace(".", "-")

        if uv:
            try:
                result = subprocess.run(
                    ["uv", "pip", "list"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                installed_packages_uv = {
                    line.split()[0].replace(".", "-")
                    for line in result.stdout.splitlines()[2:]
                }

                if fixed_package_name in installed_packages_uv:
                    return True

            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        else:
            try:
                if sys.version_info >= (3, 10):
                    # Use packages_distributions in Python 3.10+
                    # pylint: disable=import-outside-toplevel
                    from importlib.metadata import distributions

                    installed_packages = [
                        dist.metadata["Name"].replace("_", "-").replace(".", "-")
                        for dist in distributions()
                    ]
                    if fixed_package_name in installed_packages:
                        return True
                else:
                    # Fallback for Python < 3.10 using the distribution method
                    importlib.metadata.distribution(package_name.replace("-", "_"))
                    return True
            except importlib.metadata.PackageNotFoundError:
                pass
        return False

    def _get_packages_to_install(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        uv: bool = False,
    ) -> typing.List[str]:

        review_manager.logger.info("Packages:")
        packages = review_manager.settings.get_packages()

        installed_packages = []
        for package in packages:
            if self.is_installed(package, uv=uv):
                installed_packages.append(package)
                review_manager.logger.info(
                    f" {Colors.GREEN}{package}: installed{Colors.END}"
                )
            else:
                review_manager.logger.info(
                    f" {Colors.ORANGE}{package}: not installed{Colors.END}"
                )

        return [x for x in packages if x not in installed_packages]

    def install_project(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        uv: bool = False,
    ) -> None:
        """Install all packages required for the CoLRev project"""

        review_manager.logger.info("Install project")
        packages = self._get_packages_to_install(review_manager=review_manager, uv=uv)
        if len(packages) == 0:
            review_manager.logger.info("All packages are already installed")
            return

        self.install(packages=packages, uv=uv)

    # def _add_dependencies(self, packages: typing.List[str]) -> None:
    #     packages = list(packages)
    #     if len(packages) == 1 and packages[0] == "colrev_literature_review":
    #         packages.extend(
    #             [
    #                 "colrev_paper_md",
    #                 "colrev_files_dir",
    #                 "colrev_source_specific_prep",
    #                 "colrev_exclude_non_latin_alphabets",
    #                 "colrev_exclude_collections",
    #                 "colrev_exclude_complementary_materials",
    #                 "colrev_local_index",
    #                 "colrev_exclude_languages",
    #                 "colrev_remove_urls_with_500_errors",
    #                 "colrev_remove_broken_ids",
    #                 "colrev_get_doi_from_urls",
    #                 "colrev_get_year_from_vol_iss_jour",
    #                 "colrev_crossref",
    #                 "colrev_pubmed",
    #                 "colrev_europe_pmc",
    #                 "colrev_dblp",
    #                 "colrev_open_library",
    #                 "colrev_export_man_prep",
    #                 "colrev_dedupe",
    #                 "colrev_cli_prescreen",
    #                 "colrev_unpaywall",
    #                 "colrev_download_from_website",
    #                 "colrev_cli_pdf_get_man",
    #                 "colrev_ocrmypdf",
    #                 "colrev_remove_coverpage",
    #                 "colrev_remove_last_page",
    #                 "colrev_grobid_tei",
    #                 "colrev_cli_pdf_prep_man",
    #                 "colrev_cli_screen",
    #                 "colrev_rev_check",
    #             ]
    #         )

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    def install(
        self,
        *,
        packages: typing.List[str],
        upgrade: bool = True,
        editable: bool = False,
        uv: bool = False,
    ) -> None:
        """Install packages using uv if available, otherwise fallback to pip"""

        if uv:
            package_manager = ["uv", "pip"]
        else:
            package_manager = ["pip"]

        print(package_manager)

        internal_packages_dict = (
            colrev.package_manager.colrev_internal_packages.get_internal_packages_dict()
        )

        if len(packages) == 1 and packages[0] == "all_internal_packages":
            packages = list(internal_packages_dict.keys())

        # TODO : this is a temporary method
        # self._add_dependencies(packages)

        # Install packages from colrev monorepository first
        colrev_packages = []
        for package in packages:
            if package in internal_packages_dict:
                colrev_packages.append(package)
        packages = [p for p in packages if p not in colrev_packages]

        print(
            f"Installing ColRev packages: {colrev_packages + packages} using {package_manager}"
        )


        colrev_package_paths = [
            p_path
            for p_name, p_path in internal_packages_dict.items()
            if p_name in colrev_packages
        ]
        print(colrev_package_paths)
        args = [sys.executable, "-m", "pip", "install"]
        args += colrev_package_paths
        if upgrade:
            args += ["--upgrade"]
        if editable:
            args += ["--editable", editable]

        # sys.argv = args
        # run_module("pip", run_name="__main__")
        # use subprocess because run_module does not return control
        subprocess.run(args, check=False)

        # Install both internal and external packages in a single command
        all_packages = [
            internal_packages_dict[p] if p in internal_packages_dict else p
            for p in colrev_packages
        ] + packages

        install_args += all_packages
        subprocess.run(install_args, check=True)
