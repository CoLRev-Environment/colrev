#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.util
import typing
from pathlib import Path
from typing import Any

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.doc_registry_manager
import colrev.package_manager.package
from colrev.constants import EndpointType


class PackageManager:
    """The PackageManager provides functionality for package lookup and discovery"""

    def _get_package_dir(self, package_identifier: str) -> Path:
        if package_identifier.startswith("colrev."):
            colrev_package_module = importlib.import_module("colrev.packages")
            if colrev_package_module.__file__:
                colrev_package_dir = Path(colrev_package_module.__file__).parent
                return colrev_package_dir / package_identifier[7:]
            raise colrev_exceptions.MissingDependencyError(
                "Could not find the colrev package"
            )

        raise NotImplementedError

    def _get_packages_dirs(self) -> list:
        colrev_package_module = importlib.import_module("colrev.packages")
        if colrev_package_module.__file__:
            colrev_package_dir = Path(colrev_package_module.__file__).parent
            # Add other packages to package_dirs later
            return [
                package_dir
                for package_dir in colrev_package_dir.iterdir()
                if package_dir.is_dir() and not str(package_dir.name).startswith("__")
            ]
        raise colrev_exceptions.MissingDependencyError(
            "Could not find the colrev package"
        )

    def load_type_identifier_endpoint_dict(self) -> dict:
        """Load the type_identifier_endpoint_dict from the packages"""

        type_identifier_endpoint_dict: typing.Dict[
            EndpointType, typing.Dict[str, Any]
        ] = {endpoint_type: {} for endpoint_type in EndpointType}

        for package_dir in self._get_packages_dirs():
            try:
                package = colrev.package_manager.package.Package(package_dir)
                package.add_to_type_identifier_endpoint_dict(
                    type_identifier_endpoint_dict
                )
            except colrev_exceptions.MissingDependencyError as exc:
                print(exc)
                continue

        return type_identifier_endpoint_dict

    def _load_python_packages(self) -> list:
        # import colrev.env.utils
        # filedata = colrev.env.utils.get_package_file_content(
        #     module="colrev.packages", filename=Path("packages.json")
        # )
        # if not filedata:  # pragma: no cover
        #     raise colrev_exceptions.CoLRevException(
        #         "Package index not available (colrev/packages/packages.json)"
        #     )
        # package_list = json.loads(filedata.decode("utf-8"))
        packages = []
        for package_dir in self._get_packages_dirs():
            try:
                packages.append(colrev.package_manager.package.Package(package_dir))
            except colrev_exceptions.MissingDependencyError as exc:
                print(exc)
                continue

        return packages

    def update_package_list(self) -> None:
        """Generates the package_endpoints.json
        based on the packages in packages/packages.json
        and the endpoints.json files in the top directory of each package."""

        doc_reg_manager = (
            colrev.package_manager.doc_registry_manager.DocRegistryManager(
                package_manager=self, packages=self._load_python_packages()
            )
        )
        doc_reg_manager.update()

    def discover_packages(self, *, package_type: EndpointType) -> typing.Dict:
        """Discover packages (for cli usage)"""

        type_identifier_endpoint_dict = self.load_type_identifier_endpoint_dict()
        # {EndpointType.review_type:
        #   {'colrev.blank': {'endpoint': 'colrev.packages.review_types.blank.BlankReview'},
        #     ...
        # }

        return type_identifier_endpoint_dict[package_type]

    def get_package_endpoint_class(  # type: ignore
        self, *, package_type: EndpointType, package_identifier: str
    ):
        """Load a package endpoint"""

        if not package_identifier.startswith("colrev."):
            raise colrev_exceptions.MissingDependencyError(
                f"{package_identifier} is not a CoLRev package"
            )

        module_path = self._get_package_dir(package_identifier)
        package = colrev.package_manager.package.Package(module_path)
        return package.get_endpoint_class(package_type)
