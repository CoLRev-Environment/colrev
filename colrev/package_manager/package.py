#! /usr/bin/env python
"""CoLRev package."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import toml
import zope.interface.exceptions
from zope.interface.verify import verifyClass

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import EndpointType

# Inspiration for package descriptions:
# https://github.com/rstudio/reticulate/blob/
# 9ebca7ecc028549dadb3d51d2184f9850f6f9f9d/DESCRIPTION


ENDPOINT_OVERVIEW = colrev.package_manager.interfaces.ENDPOINT_OVERVIEW


class Package:
    """A Python package for CoLRev"""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, package_dir: Path) -> None:
        self.package_dir = package_dir
        self.config = self._load_config()
        self.name = self.config["project"]["name"]
        self.version = self.config["project"]["version"]
        self.authors = self.config["project"]["authors"]
        self.license = self.config["project"]["license"]
        self.repository = self.config["project"].get("repository", "")
        self.documentation = self.config["project"].get("documentation", "")

        self.status = self.config["tool"]["colrev"]["dev_status"]
        self.colrev_doc_link = self.config["tool"]["colrev"]["colrev_doc_link"]

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

    def has_endpoint(self, endpoint_type: EndpointType) -> bool:
        """Check if the package has a specific endpoint type"""
        return endpoint_type.value in self.config["tool"]["colrev"]

    def get_endpoint(self, endpoint_type: EndpointType) -> str:
        """Get the endpoint for a package type"""
        return self.config["tool"]["colrev"][endpoint_type.value]

    def _endpoint_verified(
        self, endpoint_class: Any, endpoint_type: EndpointType, identifier: str
    ) -> bool:
        interface_definition = ENDPOINT_OVERVIEW[endpoint_type]["import_name"]
        try:
            verifyClass(interface_definition, endpoint_class)  # type: ignore
            return True
        except zope.interface.exceptions.BrokenImplementation as exc:
            print(f"Error registering endpoint {identifier}: {exc}")
        return False

    def get_endpoint_class(self, package_type: EndpointType) -> Any:
        """Get the endpoint class for a package type"""
        if not self.has_endpoint(package_type):
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.name} does not have a {package_type} endpoint"
            )

        endpoint_path = self.get_endpoint(package_type)
        module_name, class_name = endpoint_path.split(":")
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
        if not self._endpoint_verified(cls, package_type, self.name):
            raise colrev_exceptions.MissingDependencyError(
                f"Endpoint {class_name} in {module_name} "
                f"does not implement the {package_type} interface"
            )
        return cls

    def add_to_type_identifier_endpoint_dict(
        self, type_identifier_endpoint_dict: dict
    ) -> None:
        """Add the package to the type_identifier_endpoint_dict dict"""
        if "tool" not in self.config or "colrev" not in self.config["tool"]:
            return

        for endpoint_type in EndpointType:
            if self.has_endpoint(endpoint_type):
                type_identifier_endpoint_dict[endpoint_type][self.name] = (
                    self.get_endpoint(endpoint_type)
                )
