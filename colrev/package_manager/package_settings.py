#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

from pydantic import BaseModel
from pydantic import Field


class DefaultSettings(BaseModel):
    """Endpoint settings"""

    endpoint: str = Field()


# class DefaultSourceSettings(colrev.settings.SearchSource, BaseModel):
#     """Search source settings"""

#     # pylint: disable=duplicate-code
#     # pylint: disable=too-many-instance-attributes
#     endpoint: str
#     filename: Path
#     search_type: SearchType
#     search_parameters: dict
#     comment: typing.Optional[str]
