#! /usr/bin/env python
"""Convenience functions to load tabular files (csv, xlsx)

Example csv records::

    title;author;year;
    How Trust Leads to Commitment;Guo, W. and Straub, D.;2021;

"""
from __future__ import annotations

import logging
import typing
from pathlib import Path
from typing import Callable

import pandas as pd

import colrev.exceptions as colrev_exceptions
import colrev.loader.loader

# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


class TableLoader(colrev.loader.loader.Loader):
    """Loads csv and Excel files (based on pandas)"""

    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: Callable,
        field_mapper: Callable,
        id_labeler: typing.Optional[Callable] = None,
        unique_id_field: str = "",
        logger: typing.Optional[logging.Logger] = None,
    ):
        self.filename = filename
        self.unique_id_field = unique_id_field
        assert id_labeler is not None or unique_id_field != ""
        self.id_labeler = id_labeler
        self.entrytype_setter = entrytype_setter
        self.field_mapper = field_mapper

        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger
        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
        )

    def load_records_list(self) -> list:
        try:
            if self.filename.name.endswith(".csv"):
                data = pd.read_csv(self.filename)
            elif self.filename.name.endswith((".xls", ".xlsx")):
                data = pd.read_excel(
                    self.filename, dtype=str
                )  # dtype=str to avoid type casting

        except pd.errors.ParserError as exc:  # pragma: no cover
            raise colrev_exceptions.ImportException(
                f"Error: Not a valid file? {self.filename.name}"
            ) from exc

        records_list = data.to_dict("records")
        return records_list
