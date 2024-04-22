#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import dataclasses
import typing
from dataclasses import dataclass
from pathlib import Path

import dacite
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import SearchType


@dataclass
class DefaultSettings(JsonSchemaMixin):
    """Endpoint settings"""

    endpoint: str

    @classmethod
    def load_settings(cls, *, data: dict):  # type: ignore
        """Load the settings from dict"""

        required_fields = [field.name for field in dataclasses.fields(cls)]
        available_fields = list(data.keys())
        non_supported_fields = [f for f in available_fields if f not in required_fields]
        if non_supported_fields:
            raise colrev_exceptions.ParameterError(
                parameter="non_supported_fields",
                value=",".join(non_supported_fields),
                options=[],
            )

        converters = {Path: Path}
        settings = from_dict(
            data_class=cls,
            data=data,
            config=dacite.Config(type_hooks=converters),  # type: ignore  # noqa
        )
        return settings


@dataclass
class DefaultSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
    """Search source settings"""

    # pylint: disable=duplicate-code
    # pylint: disable=too-many-instance-attributes
    endpoint: str
    filename: Path
    search_type: SearchType
    search_parameters: dict
    comment: typing.Optional[str]
