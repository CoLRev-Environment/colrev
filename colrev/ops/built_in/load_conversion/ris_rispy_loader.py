#! /usr/bin/env python
"""Load conversion of bib files using rispy"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager

if TYPE_CHECKING:
    import colrev.ops.load


# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class RisRispyLoader(JsonSchemaMixin):
    """Loads BibTeX files (based on rispy)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["ris"]

    ci_supported: bool = True

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ) -> None:
        self.entries = None
        self.settings = self.settings_class.load_settings(data=settings)
        self.review_manager = load_operation.review_manager

    def __get_endpoint(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
    ) -> typing.Dict[str, typing.Any]:
        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[source.get_dict()],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]
        return endpoint

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        records: dict = {}

        # TODO:
        # ultimately, the load operation should call load scripts in the search sources
        # which are then responsible for the whole parsing/fixing steps (in one place)
        # once we replace the load-package-endpoints, we should call the corresponding
        # load method of the searchsources
        endpoint = self.__get_endpoint(load_operation=load_operation, source=source)
        if hasattr(endpoint, "load"):
            records = endpoint.load(load_operation=load_operation)
            return records
        raise NotImplementedError
