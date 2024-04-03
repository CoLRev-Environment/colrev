#!/usr/bin/env python3
"""Functionality for record ID setting."""
from __future__ import annotations

import itertools
import re
import string
from typing import Optional

from tqdm import tqdm

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.loader.bib
import colrev.loader.load_utils
import colrev.process.operation
import colrev.record.record
import colrev.settings
from colrev.constants import Fields
from colrev.constants import Filepaths
from colrev.constants import IDPattern
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods


class IDSetter:
    """The IDSetter class"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager
        self.local_index = colrev.env.local_index.LocalIndex()

    def _generate_temp_id(self, record_dict: dict) -> str:
        # pylint: disable=too-many-branches

        try:
            retrieved_record = self.local_index.retrieve(record_dict)
            temp_id = retrieved_record.data[Fields.ID]

            # Do not use IDs from local_index for curated_metadata repositories
            if self.review_manager.settings.is_curated_masterdata_repo():
                raise colrev_exceptions.RecordNotInIndexException()

        except (
            colrev_exceptions.RecordNotInIndexException,
            colrev_exceptions.NotEnoughDataToIdentifyException,
        ):
            if record_dict.get(Fields.AUTHOR, record_dict.get(Fields.EDITOR, "")) != "":
                authors_string = record_dict.get(
                    Fields.AUTHOR, record_dict.get(Fields.EDITOR, "Anonymous")
                )
                authors = colrev.record.record_prep.PrepRecord.format_author_field(
                    input_string=authors_string
                ).split(" and ")
            else:
                authors = ["Anonymous"]

            # Use family names
            for author in authors:
                if "," in author:
                    author = author.split(",", maxsplit=1)[0]
                else:
                    author = author.split(" ", maxsplit=1)[0]

            id_pattern = self.review_manager.settings.project.id_pattern
            if IDPattern.first_author_year == id_pattern:
                first_author = authors[0].split(",")[0].replace(" ", "")
                temp_id = f'{first_author}{str(record_dict.get(Fields.YEAR, "NoYear"))}'
            elif IDPattern.three_authors_year == id_pattern:
                temp_id = ""
                indices = len(authors)
                if len(authors) > 3:
                    indices = 3
                for ind in range(0, indices):
                    temp_id = temp_id + f'{authors[ind].split(",")[0].replace(" ", "")}'
                if len(authors) > 3:
                    temp_id = temp_id + "EtAl"
                temp_id = temp_id + str(record_dict.get(Fields.YEAR, "NoYear"))

            if temp_id.isupper():
                temp_id = temp_id.capitalize()
            # Replace special characters
            # (because IDs may be used as file names)
            temp_id = colrev.env.utils.remove_accents(temp_id)
            temp_id = re.sub(r"\(.*\)", "", temp_id)
            temp_id = re.sub("[^0-9a-zA-Z]+", "", temp_id)

        return temp_id

    def _generate_next_unique_id(
        self,
        *,
        temp_id: str,
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
        existing_ids: Optional[list] = None,
    ) -> str:
        """Generate a blacklist to avoid setting duplicate IDs"""

        # Only change IDs that are before md_processed
        if record_dict[Fields.STATUS] in RecordState.get_post_x_states(
            state=RecordState.md_processed
        ):
            raise colrev_exceptions.PropagatedIDChange([record_dict[Fields.ID]])
        # Alternatively, we could change IDs except for those
        # that have been propagated to the
        # screen or data will not be replaced
        # (this would break the chain of evidence)

        temp_id = self._generate_temp_id(record_dict)

        if existing_ids:
            temp_id = self._generate_next_unique_id(
                temp_id=temp_id,
                existing_ids=existing_ids,
            )

        return temp_id

    def set_ids(
        self, *, records: Optional[dict] = None, selected_ids: Optional[list] = None
    ) -> dict:
        """Set the IDs for the records in the dataset"""

        if records is None:
            records = {}

        if len(records) == 0:
            records = self.review_manager.dataset.load_records_dict()

        id_list = list(records.keys())

        for record_id in tqdm(list(records.keys())):
            try:
                record_dict = records[record_id]
                if selected_ids is not None:
                    if record_id not in selected_ids:
                        continue
                if record_dict[Fields.STATUS] not in [
                    RecordState.md_imported,
                    RecordState.md_prepared,
                ]:
                    continue
                old_id = record_id

                temp_stat = record_dict[Fields.STATUS]
                if selected_ids:
                    record = colrev.record.record.Record(record_dict)
                    record.set_status(RecordState.md_prepared)
                new_id = self._generate_id(
                    record_dict,
                    existing_ids=[x for x in id_list if x != record_id],
                )
                if selected_ids:
                    record = colrev.record.record.Record(record_dict)
                    record.set_status(temp_stat)

                id_list.append(new_id)
                if old_id != new_id:
                    # We need to insert the a new element into records
                    # to make sure that the IDs are actually saved
                    record_dict.update(ID=new_id)
                    records[new_id] = record_dict
                    del records[old_id]
                    self.review_manager.report_logger.info(
                        f"set_ids({old_id}) to {new_id}"
                    )
                    if old_id in id_list:
                        id_list.remove(old_id)
            except colrev_exceptions.PropagatedIDChange as exc:
                print(exc)

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.add_changes(Filepaths.RECORDS_FILE)

        return records
