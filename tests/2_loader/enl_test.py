#!/usr/bin/env python
"""Tests of the enl load utils"""
import logging
import os
from pathlib import Path

import pytest

import colrev.review_manager
import colrev.settings
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.writer.write_utils import to_string


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the enl load utils"""
    os.chdir(tmp_path)

    # only supports enl
    with pytest.raises(NotImplementedError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/table.ptvc").touch()
        try:
            colrev.loader.load_utils.load(
                filename=Path("data/search/table.ptvc"),
            )
        finally:
            Path("data/search/table.ptvc").unlink()

    # file must exist
    with pytest.raises(FileNotFoundError):
        colrev.loader.load_utils.load(
            filename=Path("data/search/bib_tests.xy"),
            logger=logging.getLogger(__name__),
            empty_if_file_not_exists=False,
        )

    def entrytype_setter(record_dict: dict) -> None:
        if "0" not in record_dict:
            keys_to_check = ["V", "N"]
            if any(k in record_dict for k in keys_to_check):
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
        else:
            if record_dict["0"] == "Journal Article":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            elif record_dict["0"] == "Inproceedings":
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
            else:
                record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

    def field_mapper(record_dict: dict) -> None:

        key_maps = {
            ENTRYTYPES.ARTICLE: {
                "T": Fields.TITLE,
                "A": Fields.AUTHOR,
                "D": Fields.YEAR,
                "B": Fields.JOURNAL,
                "V": Fields.VOLUME,
                "N": Fields.NUMBER,
                "P": Fields.PAGES,
                "X": Fields.ABSTRACT,
                "U": Fields.URL,
                "8": "date",
                "0": "type",
            },
            ENTRYTYPES.INPROCEEDINGS: {
                "T": Fields.TITLE,
                "A": Fields.AUTHOR,
                "D": Fields.YEAR,
                "B": Fields.JOURNAL,
                "V": Fields.VOLUME,
                "N": Fields.NUMBER,
                "P": Fields.PAGES,
                "X": Fields.ABSTRACT,
                "U": Fields.URL,
                "8": "date",
                "0": "type",
            },
        }

        key_map = key_maps[record_dict[Fields.ENTRYTYPE]]
        for ris_key in list(record_dict.keys()):
            if ris_key in key_map:
                standard_key = key_map[ris_key]
                record_dict[standard_key] = record_dict.pop(ris_key)

        if Fields.AUTHOR in record_dict and isinstance(
            record_dict[Fields.AUTHOR], list
        ):
            record_dict[Fields.AUTHOR] = " and ".join(record_dict[Fields.AUTHOR])
        if Fields.EDITOR in record_dict and isinstance(
            record_dict[Fields.EDITOR], list
        ):
            record_dict[Fields.EDITOR] = " and ".join(record_dict[Fields.EDITOR])
        if Fields.KEYWORDS in record_dict and isinstance(
            record_dict[Fields.KEYWORDS], list
        ):
            record_dict[Fields.KEYWORDS] = ", ".join(record_dict[Fields.KEYWORDS])

        record_dict.pop("type", None)

        for key, value in record_dict.items():
            record_dict[key] = str(value)

    helpers.retrieve_test_file(
        source=Path("2_loader/data/enl_data.enl"),
        target=Path("enl_data.enl"),
    )

    records = colrev.loader.load_utils.load(
        filename=Path("enl_data.enl"),
        unique_id_field="INCREMENTAL",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )

    expected = (
        helpers.test_data_path / Path("2_loader/data/enl_data_expected.bib")
    ).read_text(encoding="utf-8")

    actual = to_string(records_dict=records, implementation="bib")
    assert actual == expected
