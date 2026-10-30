#!/usr/bin/env python
"""Tests of the enl load utils"""

import os
from pathlib import Path

import pytest
from bibliography_io import load_raw
from bibliography_io import to_string
from bibliography_io import write
from bibliography_io.exceptions import UnsupportedFormatError

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the enl load utils"""
    os.chdir(tmp_path)

    # only supports enl
    with pytest.raises(UnsupportedFormatError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/table.ptvc").touch()
        try:
            load_raw(Path("data/search/table.ptvc"))
        finally:
            Path("data/search/table.ptvc").unlink()

    # file must exist
    with pytest.raises(FileNotFoundError):
        load_raw(Path("non-existent.enl"))

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

    records_list = load_raw(Path("enl_data.enl"), normalize=False)
    for next_id, record in enumerate(records_list, 1):
        entrytype_setter(record)
        field_mapper(record)
        record[Fields.ID] = str(next_id).zfill(6)
    records = {record[Fields.ID]: record for record in records_list}

    expected = (
        helpers.test_data_path / Path("2_loader/data/enl_data_expected.bib")
    ).read_text(encoding="utf-8")

    actual = to_string(records, format="bib")
    assert actual == expected.rstrip("\n")

    output = tmp_path / "enl_output.bib"
    write(records, path=output)
    assert output.read_text(encoding="utf-8") == actual
    assert len(load_raw(output)) == len(records)
