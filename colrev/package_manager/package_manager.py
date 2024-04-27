#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import importlib.util
import json
import typing
from pathlib import Path
from typing import Any

import toml
import zope.interface.exceptions
from zope.interface.verify import verifyClass

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.doc_registry_manager
import colrev.package_manager.interfaces
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import PackageEndpointType

# Inspiration for package descriptions:
# https://github.com/rstudio/reticulate/blob/
# 9ebca7ecc028549dadb3d51d2184f9850f6f9f9d/DESCRIPTION


PACKAGE_TYPE_OVERVIEW = colrev.package_manager.interfaces.PACKAGE_TYPE_OVERVIEW


class Package:
    """A Python package for CoLRev"""

    def __init__(self, package_dir: Path) -> None:
        self.package_dir = package_dir
        self.config = self._load_config()
        self.name = self.config["project"]["name"]
        self.version = self.config["project"]["version"]
        self.status = self.config["tool"]["colrev"]["dev_status"]

    def _load_config(self) -> dict:
        config_path = self.package_dir / "pyproject.toml"
        if not self.package_dir.is_dir():
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.package_dir} not a CoLRev package "
                "(directory does not exist)"
            )
        if not config_path.is_file():
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.package_dir} not a CoLRev package "
                "(pyproject.toml missing)"
            )
        with open(config_path, encoding="utf-8") as file:
            config = toml.load(file)
        if "tool" not in config or "colrev" not in config["tool"]:
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.package_dir} not a CoLRev package "
                "(section tool.colrev missing in pyproject.toml)"
            )
        colrev_details = config["tool"]["colrev"]
        if "dev_status" not in colrev_details:
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.package_dir} not a CoLRev package "
                "(dev_status missing in tool.colrev)"
            )
        return config

    def _has_endpoint(self, endpoint_type: PackageEndpointType) -> bool:

        return endpoint_type.value in self.config["tool"]["colrev"]

    def _get_endpoint(self, endpoint_type: PackageEndpointType) -> str:
        return self.config["tool"]["colrev"][endpoint_type.value]

    def _endpoint_verified(
        self, endpoint_class: Any, endpoint_type: PackageEndpointType, identifier: str
    ) -> bool:
        interface_definition = PACKAGE_TYPE_OVERVIEW[endpoint_type]["import_name"]
        try:
            verifyClass(interface_definition, endpoint_class)  # type: ignore
            return True
        except zope.interface.exceptions.BrokenImplementation as exc:
            print(f"Error registering endpoint {identifier}: {exc}")
        return False

    def add_to_type_identifier_endpoint_dict(
        self, type_identifier_endpoint_dict: dict
    ) -> None:
        """Add the package to the type_identifier_endpoint_dict dict"""
        if "tool" not in self.config or "colrev" not in self.config["tool"]:
            return

        for endpoint_type in PackageEndpointType:
            if self._has_endpoint(endpoint_type):
                type_identifier_endpoint_dict[endpoint_type][self.name] = (
                    self._get_endpoint(endpoint_type)
                )

    def get_endpoint_cls(self, package_type: PackageEndpointType) -> Any:
        """Get the endpoint class for a package type"""
        if not self._has_endpoint(package_type):
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.name} does not have a {package_type} endpoint"
            )

        endpoint_path = self._get_endpoint(package_type)
        module_name, class_name = endpoint_path.split(":")
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        if not self._endpoint_verified(cls, package_type, self.name):
            raise colrev_exceptions.MissingDependencyError(
                f"Endpoint {class_name} in {module_name} "
                f"does not implement the {package_type} interface"
            )
        return cls


class PackageManager:
    """The PackageManager provides functionality for package lookup and discovery"""

    def __init__(self) -> None:
        self.type_identifier_endpoint_dict = self._load_type_identifier_endpoint_dict()
        # {PackageEndpointType.review_type:
        #   {'colrev.blank': {'endpoint': 'colrev.packages.review_types.blank.BlankReview'},
        #     ...
        # }
        self.endpoints: typing.Dict[PackageEndpointType, dict] = {}

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

    def _load_type_identifier_endpoint_dict(self) -> dict:

        type_identifier_endpoint_dict: typing.Dict[
            PackageEndpointType, typing.Dict[str, Any]
        ] = {endpoint_type: {} for endpoint_type in PackageEndpointType}

        for package_dir in self._get_packages_dirs():
            package = Package(package_dir)
            package.add_to_type_identifier_endpoint_dict(type_identifier_endpoint_dict)

        return type_identifier_endpoint_dict

    def _load_python_packages(self) -> list:
        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.packages", filename=Path("packages.json")
        )
        if not filedata:  # pragma: no cover
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/packages/packages.json)"
            )
        package_list = json.loads(filedata.decode("utf-8"))
        packages = []
        for package in package_list:
            try:
                packages.append(Package(package["module"]))
            except json.decoder.JSONDecodeError as exc:  # pragma: no cover
                print(f"Invalid json {exc}")
                continue
            except AttributeError:
                continue

        return packages

    def update_package_list(self) -> None:
        """Generates the packages/package_endpoints.json
        based on the packages in packages/packages.json
        and the endpoints.json files in the top directory of each package."""

        doc_reg_manager = (
            colrev.package_manager.doc_registry_manager.DocRegistryManager(
                package_manager=self, packages=self._load_python_packages()
            )
        )
        doc_reg_manager.update()

    def discover_packages(self, *, package_type: PackageEndpointType) -> typing.Dict:
        """Discover packages (for cli usage)"""

        return self.type_identifier_endpoint_dict[package_type]

    def load_package_endpoint(  # type: ignore
        self, *, package_type: PackageEndpointType, package_identifier: str
    ):
        """Load a package endpoint"""

        if not package_identifier.startswith("colrev."):
            raise colrev_exceptions.MissingDependencyError(
                f"{package_identifier} is not a CoLRev package"
            )

        module_path = self._get_package_dir(package_identifier)
        package = Package(module_path)
        return package.get_endpoint_cls(package_type)
