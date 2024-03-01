#! /usr/bin/env python
"""Convenience functions to load tabular files (csv, xlsx)

This module provides utility functions to load data from tabular files (e.g., CSV and Excel).
The data is loaded using pandas and then converted into a dictionary of records.
The records are then preprocessed to ensure they are in the correct format for the CoLRev system.

Usage::

    import colrev.ops.load_utils_table
    from colrev.constants import Fields

    # If unique_id_field == "":
    load_operation.ensure_append_only(file=filename)

    table_loader = colrev.ops.load_utils_table.TableLoader(
        load_operation=load_operation,
        source=self.search_source,
    )

    # Note : fixes can be applied before each of the following steps

    records = table_loader.load_table_entries()

Example csv records::

    title;author;year;
    How Trust Leads to Commitment;Guo, W. and Straub, D.;2021;

"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields


# pylint: disable=duplicate-code


class TableLoader:
    """Loads csv and Excel files (based on pandas)"""

    def __init__(
        self,
        *,
        source_file: Path,
        unique_id_field: str = "",
        logger: logging.Logger,
        force_mode: bool = False,
    ):
        if not source_file.name.endswith((".csv", ".xls", ".xlsx")):
            raise colrev_exceptions.ImportException(
                f"File not supported by TableLoader: {source_file.name}"
            )
        if not source_file.exists():
            raise colrev_exceptions.ImportException(
                f"File not found: {source_file.name}"
            )

        self.source_file = source_file
        self.unique_id_field = unique_id_field
        self.logger = logger
        self.force_mode = force_mode

    def _get_records_dict(self, *, records: list) -> dict:
        next_id = 1
        for record_dict in records:
            if self.unique_id_field != "" and self.unique_id_field in record_dict:
                record_dict[Fields.ID] = record_dict[self.unique_id_field]
            else:
                record_dict[Fields.ID] = str(next_id + 1).zfill(6)
                next_id += 1
            for key, value in record_dict.items():
                record_dict[key] = str(value)

        records_dict = {r[Fields.ID]: r for r in records}
        return records_dict

    def load_table_entries(self) -> dict:
        """Load table entries from the source"""

        try:
            if self.source_file.name.endswith(".csv"):
                data = pd.read_csv(self.source_file)
            elif self.source_file.name.endswith((".xls", ".xlsx")):
                data = pd.read_excel(
                    self.source_file, dtype=str
                )  # dtype=str to avoid type casting

        except pd.errors.ParserError as exc:  # pragma: no cover
            raise colrev_exceptions.ImportException(
                f"Error: Not a valid file? {self.source_file.name}"
            ) from exc

        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data.columns = data.columns.str.replace(";", "_")
        data.columns = [
            col.lower() if col not in ["ID", "ENTRYTYPE"] else col
            for col in data.columns
        ]
        records_value_list = data.to_dict("records")
        records_dict = self._get_records_dict(records=records_value_list)

        return records_dict
