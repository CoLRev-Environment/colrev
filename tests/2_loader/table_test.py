#!/usr/bin/env python
"""Tests of the load utils for bib files"""

import os
from pathlib import Path

import pytest
from bibliography_io import get_nr_records
from bibliography_io import load_raw
from bibliography_io.exceptions import UnsupportedFormatError

from colrev.constants import Fields


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""

    os.chdir(tmp_path)

    def entrytype_setter(record_dict: dict) -> None:
        record_dict[Fields.ENTRYTYPE] = "article"

    def field_mapper(record_dict: dict) -> None:
        record_dict[Fields.TITLE] = record_dict.pop("Title", "")
        record_dict[Fields.AUTHOR] = record_dict.pop("Authors", "")
        record_dict[Fields.YEAR] = record_dict.pop("Publication Year", "")
        record_dict[Fields.PMCID] = record_dict.pop("PMCID", "")
        record_dict[Fields.DOI] = record_dict.pop("DOI", "")
        record_dict[Fields.JOURNAL] = record_dict.pop("Journal/Book", "")
        record_dict["pmid"] = record_dict.pop("PMID", "")
        record_dict["citation"] = record_dict.pop("Citation", "")
        record_dict.pop("First Author", None)
        record_dict.pop("Create Date", None)
        record_dict.pop("NIHMS ID", None)
        record_dict.pop("number of cited references", None)

        for key, value in record_dict.items():
            record_dict[key] = str(value)

    # only supports csv/xlsx
    with pytest.raises(UnsupportedFormatError):
        load_raw(Path("table.ptvc"))

    # file must exist
    with pytest.raises(FileNotFoundError):
        load_raw(Path("non-existent.xlsx"))

    # Test csv
    helpers.retrieve_test_file(
        source=Path("2_loader/data/csv_data.csv"),
        target=Path("csv_data.csv"),
    )

    records = load_raw(Path("csv_data.csv"), normalize=False)
    for record in records:
        record["ID"] = record["PMID"]
        entrytype_setter(record)
        field_mapper(record)
    entries = {record["ID"]: record for record in records}

    assert len(entries) == 2

    assert entries["11223344"]["ID"] == "11223344"
    assert entries["11223344"]["title"] == "Paper title"
    assert entries["11223344"]["author"] == "Smith A, Walter B"
    assert entries["11223344"]["year"] == "2021"
    assert entries["11223344"]["journal"] == "Nature"
    assert entries["11223344"][Fields.PMCID] == "PMC1122334"
    assert entries["11223344"]["pmid"] == "11223344"
    assert entries["11223344"]["doi"] == "10.1111/nature1111"
    assert (
        entries["11223344"]["citation"]
        == "Nature. 2021 Dec 21;1(2):10-11. doi: 10.1111/nature1111."
    )

    nr_records = get_nr_records(Path("csv_data.csv"))
    assert 2 == nr_records

    # Test xlsx
    helpers.retrieve_test_file(
        source=Path("2_loader/data/xlsx_data.xlsx"),
        target=Path("xlsx_data.xlsx"),
    )
    xlsx_records = load_raw(Path("xlsx_data.xlsx"), normalize=False)
    assert len(xlsx_records) == 3

    nr_records = get_nr_records(Path("xlsx_data.xlsx"))
    assert 3 == nr_records
