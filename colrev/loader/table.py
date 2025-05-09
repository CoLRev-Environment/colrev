#! /usr/bin/env python
"""Function to load tabular files (csv, xlsx)"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.loader.loader


# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments


class TableLoader(colrev.loader.loader.Loader):
    """Loads csv and Excel files (based on pandas)"""

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
        if filename.name.endswith(".csv"):
            data = pd.read_csv(filename)
        elif filename.name.endswith((".xls", ".xlsx")):
            data = pd.read_excel(filename, dtype=str)
        else:
            raise NotImplementedError
        count = len(data)
        return count

    def load_records_list(self) -> list:
        try:
            if self.filename.name.endswith(".csv"):
                data = pd.read_csv(self.filename)
            elif self.filename.name.endswith((".xls", ".xlsx")):
                data = pd.read_excel(
                    self.filename, dtype=str
                )  # dtype=str to avoid type casting
            else:
                raise NotImplementedError

        except pd.errors.ParserError as exc:  # pragma: no cover
            raise colrev_exceptions.ImportException(
                f"Error: Not a valid file? {self.filename.name}"
            ) from exc

        records_list = data.to_dict("records")
        return records_list
