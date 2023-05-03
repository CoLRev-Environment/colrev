#!/usr/bin/env python
"""Test the bibtex crossref resolution prep"""
from pathlib import Path

import pytest

import colrev.ops.built_in.prep.bibtex_crossref_resolution
import colrev.ops.prep


@pytest.fixture(name="bcr")
def get_bcr(
    prep_operation: colrev.ops.prep.Prep,
) -> colrev.ops.built_in.prep.bibtex_crossref_resolution.BibTexCrossrefResolutionPrep:
    """Get the BibTexCrossrefResolutionPrep fixture"""
    settings = {"endpoint": "colrev.resolve_crossrefs"}
    elp = colrev.ops.built_in.prep.bibtex_crossref_resolution.BibTexCrossrefResolutionPrep(
        prep_operation=prep_operation, settings=settings
    )
    return elp


@pytest.mark.parametrize(
    "input_rec, crossref_rec, expected",
    [
        (
            {
                "ID": "001",
                "ENTRYTYPE": "inproceedings",
                "colrev_origin": ["crossref.bib/001"],
                "title": "An Integrated Framework for Understanding Digital Work in Organizations",
                "crossref": "002",
            },
            {
                "002": {
                    "ID": "002",
                    "ENTRYTYPE": "inproceedings",
                    "booktitle": "First Conference on Crossref Records",
                    "colrev_origin": ["crossref.bib/002"],
                }
            },
            {
                "ID": "001",
                "colrev_origin": ["crossref.bib/001"],
                "ENTRYTYPE": "inproceedings",
                "title": "An Integrated Framework for Understanding Digital Work in Organizations",
                "booktitle": "First Conference on Crossref Records",
                "colrev_masterdata_provenance": {
                    "booktitle": {"note": "", "source": "crossref_resolution"}
                },
            },
        ),
    ],
)
def test_prep_exclude_languages(
    bcr: colrev.ops.built_in.prep.bibtex_crossref_resolution.BibTexCrossrefResolutionPrep,
    prep_operation: colrev.ops.prep.Prep,
    input_rec: dict,
    crossref_rec: dict,
    expected: dict,
) -> None:
    """Test the prep_exclude_languages()"""
    record = colrev.record.PrepRecord(data=input_rec)
    # Save the crossref_rec as data/records.bib
    prep_operation.review_manager.dataset.save_records_dict_to_file(
        records=crossref_rec,
        save_path=(prep_operation.review_manager.path / Path("data/records.bib")),
    )
    returned_record = bcr.prepare(prep_operation=prep_operation, record=record)
    actual = returned_record.data
    assert expected == actual
    (prep_operation.review_manager.path / Path("data/records.bib")).unlink()
