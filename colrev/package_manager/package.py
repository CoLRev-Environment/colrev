#! /usr/bin/env python
"""CoLRev package."""
from __future__ import annotations

import importlib.util
from importlib.metadata import distribution
from importlib.metadata import distributions
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any

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

    def __init__(self, package_identifier: str) -> None:
        try:
            self.package = distribution(package_identifier)
        except PackageNotFoundError as exc:
            # Note: The distribution(package_identifier)
            # does not seem to work reliably (across matrix tests on GitHub Actions)
            for dist in distributions():
                if dist.metadata["Name"] == package_identifier:
                    self.package = dist
                    break
            else:
                raise colrev_exceptions.MissingDependencyError(
                    f"Package {package_identifier} not found"
                ) from exc

        if not self.package.files:
            raise colrev_exceptions.MissingDependencyError(
                f"Package {package_identifier} not a CoLRev package " "(no files found)"
            )

        package_path = self.package.files[0].locate()
        self.package_dir = Path(package_path).parent

        # Note: The metadata() function does not work reliably
        # package_metadata = metadata(package_identifier)
        self.name = self.package.metadata["Name"]
        self.version = self.package.metadata["Version"]

    def has_endpoint(self, endpoint_type: EndpointType) -> bool:
        """Check if the package has a specific endpoint type"""

        return endpoint_type.value in [e.name for e in self.package.entry_points]

    def get_endpoint(self, endpoint_type: EndpointType) -> str:
        """Get the endpoint for a package type"""

        if endpoint_type.value not in [e.name for e in self.package.entry_points]:
            raise colrev_exceptions.MissingDependencyError(
                f"Package {self.name} does not have a {endpoint_type} endpoint"
            )

        return [e for e in self.package.entry_points if e.name == endpoint_type.value][
            0
        ].value

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

        for endpoint_type in EndpointType:
            if self.has_endpoint(endpoint_type):
                type_identifier_endpoint_dict[endpoint_type][self.name] = (
                    self.get_endpoint(endpoint_type)
                )
