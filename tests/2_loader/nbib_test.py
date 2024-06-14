#!/usr/bin/env python
"""Tests of the load utils for nbib files"""
import os
from pathlib import Path

import pytest

import colrev.loader.load_utils
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


def test_load_nbib_entries(tmp_path, helpers):  # type: ignore
    os.chdir(tmp_path)

    def entrytype_setter(record_dict: dict) -> None:
        if "Journal Articles" in record_dict["PT"]:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
        else:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC

    def field_mapper(record_dict: dict) -> None:

        key_maps = {
            ENTRYTYPES.ARTICLE: {
                "TI": Fields.TITLE,
                "AU": Fields.AUTHOR,
                "DP": Fields.YEAR,
                "JT": Fields.JOURNAL,
                "VI": Fields.VOLUME,
                "IP": Fields.NUMBER,
                "PG": Fields.PAGES,
                "AB": Fields.ABSTRACT,
                "AID": Fields.DOI,
                "ISSN": Fields.ISSN,
                "OID": "eric_id",
                "OT": Fields.KEYWORDS,
                "LA": Fields.LANGUAGE,
                "PT": "type",
                "LID": "eric_url",
            }
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
        record_dict.pop("OWN", None)
        record_dict.pop("SO", None)

        for key, value in record_dict.items():
            record_dict[key] = str(value)

    # only supports nbib
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
            filename=Path("non-existent.nbib"),
            unique_id_field="doi",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            empty_if_file_not_exists=False,
        )

    helpers.retrieve_test_file(
        source=Path("2_loader/data/nbib_data.nbib"),
        target=Path("bib_data.nbib"),
    )

    entries = colrev.loader.load_utils.load(
        filename=Path("bib_data.nbib"),
        unique_id_field="INCREMENTAL",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )

    assert len(entries) == 1

    assert entries["000001"][Fields.TITLE] == "Paper title"
    assert entries["000001"][Fields.AUTHOR] == "Smith, Tom and Hunter, Shawn"
    assert entries["000001"][Fields.KEYWORDS] == "Keyword 1, Keyword 2, Keyword 3"
    assert entries["000001"][Fields.JOURNAL] == "Journal Name"
    assert entries["000001"][Fields.DOI] == "http://dx.doi.org/10.1000/123456789"
    assert entries["000001"]["eric_id"] == "EJ1131633"
    assert entries["000001"][Fields.VOLUME] == "10"
    assert entries["000001"][Fields.NUMBER] == "1"
    assert entries["000001"][Fields.PAGES] == "1-9"
    assert entries["000001"][Fields.YEAR] == "2000"
    assert entries["000001"]["eric_url"] == "http://eric.ed.gov/?id=EJ1131633"
    assert entries["000001"][Fields.ABSTRACT] == "Abstract ..."
    assert entries["000001"][Fields.ISSN] == "ISSN-1234-4567"
    assert entries["000001"][Fields.LANGUAGE] == "English"
