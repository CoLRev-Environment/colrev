#!/usr/bin/env python
"""Tests of the load utils for ris files"""
import os
from pathlib import Path

import pytest

import colrev.loader.load_utils
from colrev.constants import Fields


def test_load_ris_entries(tmp_path, helpers):  # type: ignore
    os.chdir(tmp_path)

    def entrytype_setter(record_dict: dict) -> None:
        record_dict[Fields.ENTRYTYPE] = "article"

    def field_mapper(record_dict: dict) -> None:
        record_dict[Fields.TITLE] = record_dict.pop("TI", "")
        record_dict[Fields.AUTHOR] = " and ".join(record_dict.pop("AU", ""))
        record_dict[Fields.YEAR] = record_dict.pop("PY", "")
        record_dict[Fields.JOURNAL] = record_dict.pop("T2", "")
        record_dict[Fields.DOI] = record_dict.pop("DO", "")
        record_dict[Fields.NUMBER] = record_dict.pop("IS", "")
        record_dict[Fields.VOLUME] = record_dict.pop("VL", "")
        record_dict[Fields.ISSN] = record_dict.pop("SN", "")
        if "SP" in record_dict and "EP" in record_dict:
            record_dict[Fields.PAGES] = (
                f"{record_dict.pop('SP')}--{record_dict.pop('EP')}"
            )
        for key, value in record_dict.items():
            record_dict[key] = str(value)

    # only supports ris
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
            filename=Path("non-existent.ris"),
            unique_id_field="doi",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            empty_if_file_not_exists=False,
        )

    helpers.retrieve_test_file(
        source=Path("2_loader/data/ris_data.ris"),
        target=Path("ris_data.ris"),
    )

    entries = colrev.loader.load_utils.load(
        filename=Path("ris_data.ris"),
        unique_id_field="DO",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )

    assert len(entries) == 2
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.TITLE]
        == "Title of a conference paper"
    )
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.AUTHOR]
        == "A. Author-One and B. Author-Two and C. Author-Three and D. Author-Four and E. Author-Five"
    )
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.JOURNAL]
        == "Secondary Title (booktitle title, if applicable)"
    )
    assert entries["10.1234/Random-name55555.2020.00050"][Fields.PAGES] == "183--186"
    assert entries["10.1234/Random-name55555.2020.00050"][Fields.YEAR] == "2020"
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.DOI]
        == "10.1234/Random-name55555.2020.00050"
    )
    assert entries["10.1234/Random-name55555.2020.00050"][Fields.ISSN] == "1111-3333"
    assert entries["10.1234/Random-name55555.2020.00050"]["Y1"] == "4-8 Aug. 2020"

    assert entries["10.1111/MC.2017.66"]["TY"] == "JOUR"
    assert entries["10.1111/MC.2017.66"][Fields.TITLE] == "Title of a journal paper"
    assert (
        entries["10.1111/MC.2017.66"][Fields.JOURNAL]
        == "Secondary Title (journal title, if applicable)"
    )
    assert entries["10.1111/MC.2017.66"][Fields.PAGES] == "14--25"
    assert (
        entries["10.1111/MC.2017.66"][Fields.AUTHOR]
        == "A. Author-One and B. Author-Two and C. Author-Three"
    )
    assert entries["10.1111/MC.2017.66"][Fields.YEAR] == "2017"
    assert entries["10.1111/MC.2017.66"][Fields.DOI] == "10.1111/MC.2017.66"
    assert (
        entries["10.1111/MC.2017.66"][Fields.JOURNAL]
        == "Secondary Title (journal title, if applicable)"
    )
    assert entries["10.1111/MC.2017.66"][Fields.NUMBER] == "3"
    assert entries["10.1111/MC.2017.66"][Fields.VOLUME] == "50"
    assert entries["10.1111/MC.2017.66"][Fields.ISSN] == "1111-2222"

    nr_records = colrev.loader.load_utils.get_nr_records(Path("ris_data.ris"))
    assert 2 == nr_records
