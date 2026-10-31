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
import colrev.loader.load_utils_formatter

from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.record.record_utils import index_records_by_id


def test_index_records_by_id_rejects_missing_and_duplicate_ids() -> None:
    with pytest.raises(MissingRecordIDError):
        index_records_by_id([{"title": "No ID"}])

    with pytest.raises(DuplicateRecordIDError):
        index_records_by_id(
            [
                {Fields.ID: "same"},
                {Fields.ID: "same"},
            ]
        )


def test_dataset_adapter_restores_colrev_record_field_types() -> None:
    """CoLRev field conversion is applied at its boundary."""
    records = {
        "example": {
            Fields.STATUS: "md_imported",
            Fields.ORIGIN: "source.bib/1; other.bib/2;",
            Fields.MD_PROV: "title:provider;verified;",
            Fields.D_PROV: "file:manual;",
        }
    }

    converted = adapt_bibliography_records(records)

    assert converted["example"][Fields.STATUS] is RecordState.md_imported
    assert converted["example"][Fields.ORIGIN] == ["source.bib/1", "other.bib/2"]
    assert converted["example"][Fields.MD_PROV] == {
        "title": {"source": "provider", "note": "verified"}
    }
    assert converted["example"][Fields.D_PROV] == {
        "file": {"source": "manual", "note": ""}
    }


def test_dataset_adapter_restores_structured_bibliography_fields(
    tmp_path: Path,
) -> None:
    """Verify that structured bibliography fields survive BibTeX round-trips.

    Serialize records to BibTeX and reload them through string, raw, and file
    APIs. Confirm that the adapter consistently restores nested mappings,
    sorted lists, and RecordState enums across all three paths.
    """
    records = {
        "example": {
            Fields.ID: "example",
            Fields.ENTRYTYPE: "article",
            Fields.ORIGIN: ["source.bib/1", "other.bib/2"],
            Fields.MD_PROV: {"title": {"source": "provider", "note": "verified"}},
            Fields.D_PROV: {"doi": {"source": "crossref", "note": ""}},
            Fields.STATUS: "md_imported",
        }
    }
    bibtex = to_string(
        records,
        format="bib",
        mapping_fields={Fields.MD_PROV, Fields.D_PROV},
        list_fields={Fields.ORIGIN},
    )

    loaded = loads_primary(
        bibtex,
        format="bib",
        mapping_fields={Fields.MD_PROV, Fields.D_PROV},
        list_fields={Fields.ORIGIN},
    )
    bibtex_path = tmp_path / "structured.bib"
    write(
        records,
        path=bibtex_path,
        mapping_fields={Fields.MD_PROV, Fields.D_PROV},
        list_fields={Fields.ORIGIN},
    )
    file_loaded = load_primary(
        bibtex_path,
        mapping_fields={Fields.MD_PROV, Fields.D_PROV},
        list_fields={Fields.ORIGIN},
    )
    file_converted = adapt_bibliography_records(file_loaded)
    converted = adapt_bibliography_records(loaded)
    raw_loaded = loads_raw(
        bibtex,
        format="bib",
        mapping_fields={Fields.MD_PROV, Fields.D_PROV},
        list_fields={Fields.ORIGIN},
    )
    raw_converted = adapt_bibliography_records(
        {record[Fields.ID]: record for record in raw_loaded}
    )

    expected = {
        "example": {
            Fields.ID: "example",
            Fields.ENTRYTYPE: "article",
            Fields.ORIGIN: ["other.bib/2", "source.bib/1"],
            Fields.MD_PROV: {"title": {"source": "provider", "note": "verified"}},
            Fields.D_PROV: {"doi": {"source": "crossref", "note": ""}},
            Fields.STATUS: RecordState.md_imported,
        }
    }
    assert converted == expected
    assert raw_converted == expected
    assert file_converted == expected


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

    colrev.loader.load_utils_formatter.run_fix_bib_file(
        Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    assert get_nr_records(Path("data/search/bib_data.bib")) == 6

    with pytest.raises(UnsupportedFormatError):
        loads_raw("content...", format="xy")
