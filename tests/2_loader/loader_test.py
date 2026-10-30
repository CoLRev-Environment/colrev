#!/usr/bin/env python
"""Tests of the load utils for bib files"""

import logging
import os
from pathlib import Path

import pytest
from bibliography_io import get_nr_records
from bibliography_io import load_primary
from bibliography_io import load_raw
from bibliography_io import loads_primary
from bibliography_io import loads_raw
from bibliography_io import to_string
from bibliography_io import write
from bibliography_io.exceptions import DuplicateRecordIDError
from bibliography_io.exceptions import MissingRecordIDError
from bibliography_io.exceptions import UnsupportedFormatError
from colrev.record.bibliography import adapt_bibliography_records

import colrev.loader.bib
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.dataset import (
    _load_primary_bibliography,
)
from colrev.loader.loader import Loader


def test_missing_ids_error_explains_incremental_ids(tmp_path: Path) -> None:
    """Test that the missing-ID error explains how to generate IDs."""
    loader = Loader(
        filename=tmp_path / "records.test",
        entrytype_setter=lambda record: None,
        field_mapper=lambda record: None,
        id_labeler=lambda records: None,
        unique_id_field="",
        logger=logging.getLogger(__name__),
    )
    with pytest.raises(ValueError) as exc_info:
        loader._set_ids([{"title": "Record without an ID"}])

    assert str(exc_info.value) == (
        f'{Colors.ORANGE}ID not set in all records. Pass unique_id_field="INCREMENTAL" '
        "to the CoLRev loader to generate sequential IDs."
        f"{Colors.END}"
    )


def test_dataset_adapter_restores_colrev_record_field_types() -> None:
    """CoLRev field conversion is applied at its boundary."""
    records = {
        "example": {
            Fields.STATUS: "md_imported",
            Fields.ORIGIN: "source.bib/1; other.bib/2;",
            Fields.MD_PROV: "title:provider;verified;",
        }
    }

    converted = adapt_bibliography_records(records)

    assert converted["example"][Fields.STATUS] is RecordState.md_imported
    assert converted["example"][Fields.ORIGIN] == ["source.bib/1", "other.bib/2"]
    assert converted["example"][Fields.MD_PROV] == {
        "title": {"source": "provider", "note": "verified"}
    }


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""
    os.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        load_raw(Path("data/search/bib_data.bib"))
    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_tests.xy"),
    )
    with pytest.raises(UnsupportedFormatError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/bib_tests.xy").touch()
        try:
            load_raw(Path("data/search/bib_tests.xy"))
        finally:
            Path("data/search/bib_tests.xy").unlink()

    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_data.bib"),
    )

    colrev.loader.bib.run_fix_bib_file(
        Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    assert get_nr_records(Path("data/search/bib_data.bib")) == 6

    with pytest.raises(UnsupportedFormatError):
        loads_raw("content...", format="xy")
