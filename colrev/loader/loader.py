#! /usr/bin/env python
"""Function to load files (BiBTeX, RIS, CSV, etc.)"""
import logging
import typing
from pathlib import Path

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.loader.load_utils_name_formatter import parse_names_in_records

# pylint: disable=too-many-arguments


class Loader:
    """Loader class"""

    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: typing.Callable,
        field_mapper: typing.Callable,
        id_labeler: typing.Callable,
        unique_id_field: str,
        logger: logging.Logger,
        format_names: bool = False,
    ):
        self.filename = filename
        self.unique_id_field = unique_id_field
        assert id_labeler is not None or unique_id_field != ""
        self.id_labeler = id_labeler
        self.entrytype_setter = entrytype_setter
        self.field_mapper = field_mapper
        self.format_names = format_names

        self.logger = logger

    def _set_ids(self, records_list: list) -> None:
        if self.unique_id_field == "INCREMENTAL":
            for next_id, record_dict in enumerate(records_list, 1):
                record_dict[Fields.ID] = str(next_id).zfill(6)

        elif self.unique_id_field != "":
            for record_dict in records_list:
                record_dict[Fields.ID] = record_dict[self.unique_id_field]
        else:
            self.id_labeler(records_list)  # type: ignore

        assert all(
            Fields.ID in record_dict for record_dict in records_list
        ), "ID not set in all records"
        unique_ids = {record_dict[Fields.ID] for record_dict in records_list}
        non_unique_ids = [
            id
            for id in unique_ids
            if sum(1 for r in records_list if r[Fields.ID] == id) > 1
        ]
        assert not non_unique_ids, f"ID is not unique in records: {non_unique_ids}"

    def _set_entrytypes(self, records_dict: dict) -> None:
        for r_dict_val in records_dict.values():
            self.entrytype_setter(r_dict_val)
        assert all(
            Fields.ENTRYTYPE in r for r in records_dict.values()
        ), "ENTRYTYPE not set in all records"
        invalid_entrytypes = [
            r[Fields.ENTRYTYPE]
            for r in records_dict.values()
            if r[Fields.ENTRYTYPE] not in ENTRYTYPES.get_all()
        ]
        assert (
            len(invalid_entrytypes) == 0
        ), f"Invalid ENTRYTYPE in some records: {invalid_entrytypes}"

    def _set_fields(self, records_dict: dict) -> None:
        for record_dict in records_dict.values():
            self.field_mapper(record_dict)

        # assert all(
        #     mandatory_field in record_dict
        #     for record_dict in records_dict.values()
        #     for mandatory_field in [Fields.AUTHOR, Fields.TITLE, Fields.YEAR]
        # ), "Mandatory field not set in all records"

        error_field_list = [
            field if any(c in field for c in [" ", ";"]) else None
            for record_dict in records_dict.values()
            for field in record_dict.keys()
        ]

        error_fields = {field for field in error_field_list if field is not None}

        if any(error_fields):
            error_cases = [
                r
                for r in records_dict.values()
                if any(error_field in r for error_field in error_fields)
            ]
            self.logger.error(
                f"Record contains invalid keys: {error_fields},\n record: {error_cases}"
            )

    def load_records_list(self) -> list:
        """The load_records_list must be implemented by the inheriting class
        (e.g., for ris/bib/...)"""
        raise NotImplementedError  # pragma: no cover

    def load(self) -> dict:
        """Load table entries from the source"""

        records_list = self.load_records_list()
        self._set_ids(records_list)
        records_dict = {str(r[Fields.ID]): r for r in records_list}
        self._set_entrytypes(records_dict)
        self._set_fields(records_dict)

        if self.format_names:
            parse_names_in_records(records_dict)

        return records_dict
