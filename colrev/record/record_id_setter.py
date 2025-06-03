#!/usr/bin/env python3
"""Record ID setter."""
from __future__ import annotations

import itertools
import logging
import re
import string
import typing

from tqdm import tqdm

import colrev.env.local_index
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import IDPattern
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods


class IDSetter:
    """The IDSetter class"""

    def __init__(
        self,
        *,
        id_pattern: IDPattern,
        skip_local_index: bool = False,
        logger: logging.Logger = logging.getLogger(__name__),
    ) -> None:

        self.id_pattern = id_pattern
        self.skip_local_index = skip_local_index
        if not self.skip_local_index:
            self.local_index = colrev.env.local_index.LocalIndex()
        self.logger = logger

    def _get_author_last_names(self, record_dict: dict) -> list:
        if record_dict.get(Fields.AUTHOR, record_dict.get(Fields.EDITOR, "")) != "":
            authors_string = record_dict.get(
                Fields.AUTHOR, record_dict.get(Fields.EDITOR, FieldValues.ANONYMOUS)
            )
            authors = colrev.record.record_prep.PrepRecord.format_author_field(
                authors_string
            ).split(" and ")
        else:
            authors = [FieldValues.ANONYMOUS]

        # Use family names
        for i, author in enumerate(authors):
            if "," in author:
                authors[i] = author.split(",", maxsplit=1)[0]
            else:
                authors[i] = author.split(" ", maxsplit=1)[0]

        return authors

    def _generate_id_from_pattern(self, record_dict: dict) -> str:
        authors = self._get_author_last_names(record_dict)

        if IDPattern.first_author_year == self.id_pattern:
            temp_id = f'{authors[0]}{str(record_dict.get(Fields.YEAR, "NoYear"))}'
        elif IDPattern.three_authors_year == self.id_pattern:
            temp_id = ""
            indices = len(authors)
            if len(authors) > 3:
                indices = 3
            for ind in range(0, indices):
                temp_id = temp_id + f"{authors[ind]}"
            if len(authors) > 3:
                temp_id = temp_id + "EtAl"
            temp_id = temp_id + str(record_dict.get(Fields.YEAR, "NoYear"))

        # Replace special characters
        # (because IDs may be used as file names)
        temp_id = colrev.env.utils.remove_accents(temp_id)
        temp_id = temp_id.replace(" ", "")
        temp_id = re.sub(r"\(.*\)", "", temp_id)
        temp_id = re.sub("[^0-9a-zA-Z ]+", "", temp_id)
        if temp_id.isupper():  # pragma: no cover
            temp_id = temp_id.capitalize()
        return temp_id

    def _make_id_unique(
        self,
        temp_id: str,
        *,
        existing_ids: list,
    ) -> str:
        """Get the next unique ID"""

        order = 0
        letters = list(string.ascii_lowercase)
        next_unique_id = temp_id
        appends: list = []
        while next_unique_id.lower() in [i.lower() for i in existing_ids]:
            if len(appends) == 0:
                order += 1
                appends = list(itertools.product(letters, repeat=order))
            next_unique_id = temp_id + "".join(list(appends.pop(0)))
        temp_id = next_unique_id
        return temp_id

    def _generate_id(
        self,
        record_dict: dict,
        *,
        existing_ids: typing.Optional[list] = None,
    ) -> str:
        """Generate a blacklist to avoid setting duplicate IDs"""

        if self.skip_local_index:
            temp_id = self._generate_id_from_pattern(record_dict)
        else:
            try:
                retrieved_record = self.local_index.retrieve(record_dict)
                temp_id = retrieved_record.data[Fields.ID]  # pragma: no cover
            except (
                colrev_exceptions.RecordNotInIndexException,
                colrev_exceptions.NotEnoughDataToIdentifyException,
            ):
                temp_id = self._generate_id_from_pattern(record_dict)

        if existing_ids:
            temp_id = self._make_id_unique(
                temp_id,
                existing_ids=existing_ids,
            )

        return temp_id

    def set_ids(
        self, records: dict, *, selected_ids: typing.Optional[list] = None
    ) -> dict:
        """Set the IDs for the records in the dataset"""

        id_list = list(records.keys())

        for record_id in tqdm(list(records.keys())):
            record_dict = records[record_id]
            if selected_ids is not None:
                if record_id not in selected_ids:  # pragma: no cover
                    continue
            elif Fields.STATUS in record_dict and record_dict[Fields.STATUS] not in [
                RecordState.md_imported,
                RecordState.md_prepared,
            ]:
                continue
            old_id = record_id

            temp_stat = record_dict.get(Fields.STATUS, "")
            if selected_ids:
                record = colrev.record.record.Record(record_dict)
                record.set_status(RecordState.md_prepared)

            new_id = old_id
            if Fields.STATUS not in record_dict:
                new_id = self._generate_id(
                    record_dict,
                    existing_ids=[x for x in id_list if x != record_id],
                )
            # Only change IDs that are before md_processed
            elif record_dict[Fields.STATUS] not in RecordState.get_post_x_states(
                state=RecordState.md_processed
            ):
                new_id = self._generate_id(
                    record_dict,
                    existing_ids=[x for x in id_list if x != record_id],
                )

            if selected_ids:
                record = colrev.record.record.Record(record_dict)
                if temp_stat:
                    record.set_status(temp_stat)

            self._update_id(
                records,
                id_list=id_list,
                record_dict=record_dict,
                old_id=old_id,
                new_id=new_id,
            )

        return records

    # pylint: disable=too-many-arguments
    def _update_id(
        self,
        records: dict,
        *,
        id_list: list,
        record_dict: dict,
        old_id: str,
        new_id: str,
    ) -> None:
        id_list.append(new_id)
        if old_id != new_id:
            # We need to insert the a new element into records
            # to make sure that the IDs are actually saved
            record_dict.update(ID=new_id)
            records[new_id] = record_dict
            del records[old_id]
            self.logger.info(f"set_ids({old_id}) to {new_id}")
            if old_id in id_list:
                id_list.remove(old_id)
