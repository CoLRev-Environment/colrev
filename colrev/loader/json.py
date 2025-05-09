#! /usr/bin/env python
"""Function to load JSON files"""
from __future__ import annotations

import json
import logging
import typing
from pathlib import Path

import colrev.loader.loader


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-instance-attributes


class JSONLoader(colrev.loader.loader.Loader):
    """Loads json files"""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: typing.Callable = lambda x: x,
        field_mapper: typing.Callable = lambda x: x,
        id_labeler: typing.Callable = lambda x: x,
        unique_id_field: str = "",
        logger: logging.Logger = logging.getLogger(__name__),
        format_names: bool = False,
    ):
        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
            format_names=format_names,
        )

    @classmethod
    def get_nr_records(cls, filename: Path) -> int:
        """Get the number of records in the file"""
        with open(filename, encoding="utf-8-sig") as file:
            records_list = json.load(file)

        return len(records_list)

    def load_records_list(self) -> list:
        """Load json entries"""

        with open(self.filename, encoding="utf-8-sig") as file:
            records_list = json.load(file)

        return records_list
