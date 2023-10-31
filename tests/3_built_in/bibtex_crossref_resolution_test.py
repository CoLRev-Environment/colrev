#!/usr/bin/env python
"""Test the bibtex crossref resolution prep"""
from pathlib import Path

import pytest

import colrev.ops.built_in.prep.bibtex_crossref_resolution
import colrev.ops.prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


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
                Fields.ID: "001",
                Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
                Fields.ORIGIN: ["crossref.bib/001"],
                Fields.TITLE: "An Integrated Framework for Understanding Digital Work in Organizations",
                "crossref": "002",
            },
            {
                "002": {
                    Fields.ID: "002",
                    Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
                    Fields.BOOKTITLE: "First Conference on Crossref Records",
                    Fields.ORIGIN: ["crossref.bib/002"],
                }
            },
            {
                Fields.ID: "001",
                Fields.ORIGIN: ["crossref.bib/001"],
                Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
                Fields.TITLE: "An Integrated Framework for Understanding Digital Work in Organizations",
                Fields.BOOKTITLE: "First Conference on Crossref Records",
                Fields.MD_PROV: {
                    Fields.BOOKTITLE: {"note": "", "source": "crossref_resolution"}
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
