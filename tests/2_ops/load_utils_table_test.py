#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import logging
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
from colrev.ops.load_utils_table import TableLoader


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""

    os.chdir(tmp_path)

    # only supports csv/xlsx
    with pytest.raises(colrev_exceptions.ImportException):
        table_loader = TableLoader(
            filename=Path("table.ptvc"),
            unique_id_field="pmid",
            force_mode=False,
            logger=logging.getLogger(__name__),
        )

    # file must exist
    with pytest.raises(colrev_exceptions.ImportException):
        table_loader = TableLoader(
            filename=Path("non-existent.xlsx"),
            force_mode=False,
            logger=logging.getLogger(__name__),
        )

    # Test csv
    helpers.retrieve_test_file(
        source=Path("load_utils/table.csv"),
        target=Path("table.csv"),
    )

    table_loader = TableLoader(
        filename=Path("table.csv"),
        unique_id_field="pmid",
        force_mode=False,
        logger=logging.getLogger(__name__),
    )

    entries = table_loader.load_table_entries()

    assert len(entries) == 1
    print(entries)
    assert entries["11223344"]["pmid"] == "11223344"
    assert entries["11223344"]["title"] == "Paper title"
    assert (
        entries["11223344"]["citation"]
        == "Nature. 2021 Dec 21;1(2):10-11. doi: 10.1111/nature1111."
    )
    assert entries["11223344"]["first_author"] == "Smith A"
    assert entries["11223344"]["create_date"] == "2021/12/21"
    assert entries["11223344"]["pmcid"] == "PMC1122334"
    assert entries["11223344"]["doi"] == "10.1111/nature1111"
    assert entries["11223344"]["ID"] == "11223344"
    assert entries["11223344"]["authors"] == "Smith A, Walter B"
    assert entries["11223344"]["publication_year"] == "2021"
    assert entries["11223344"]["journal/book"] == "Nature"

    # Test xlsx
    helpers.retrieve_test_file(
        source=Path("load_utils/table.xlsx"),
        target=Path("table.xlsx"),
    )
    table_loader = TableLoader(
        filename=Path("table.xlsx"),
        force_mode=False,
        logger=logging.getLogger(__name__),
    )
    table_loader.load_table_entries()
