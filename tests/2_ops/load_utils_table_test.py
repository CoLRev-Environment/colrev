#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
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
    with pytest.raises(colrev_exceptions.ImportException):
        colrev.loader.load_utils.load(
            filename=Path("table.ptvc"),
            unique_id_field="pmid",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
        )

    # file must exist
    with pytest.raises(colrev_exceptions.ImportException):
        colrev.loader.load_utils.load(
            filename=Path("non-existent.xlsx"),
            unique_id_field="INCREMENTAL",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
        )

    # Test csv
    helpers.retrieve_test_file(
        source=Path("load_utils/table.csv"),
        target=Path("table.csv"),
    )

    entries = colrev.loader.load_utils.load(
        filename=Path("table.csv"),
        unique_id_field="PMID",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )

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

    # Test xlsx
    helpers.retrieve_test_file(
        source=Path("load_utils/table.xlsx"),
        target=Path("table.xlsx"),
    )
    colrev.loader.load_utils.load(
        filename=Path("table.xlsx"),
        unique_id_field="INCREMENTAL",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )
