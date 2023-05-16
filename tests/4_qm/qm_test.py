#!/usr/bin/env python
"""Tests for the quality model"""
from __future__ import annotations

import pytest

import colrev.qm.quality_model
import colrev.record


@pytest.mark.parametrize(
    "author_str, defects",
    [
        ("RAI", ["mostly-all-caps"]),
        ("Rai, Arun and B,", ["incomplete-field"]),
        # FIXME: incomplete part, but error is not marked correctly
        # ("Rai, Arun and B", ["incomplete-field"]),
        # additional title
        ("Rai, PhD, Arun", ["name-format-titles"]),
        ("Rai, Phd, Arun", ["name-format-titles"]),
        ("GuyPhD, Arun", []),  #
        (
            "Rai, Arun; Straub, Detmar",
            ["name-format-separators"],
        ),
        # author without capital letters
        # NOTE: it's not a separator error, should be something more relevant
        (
            "Mathiassen, Lars and jonsson, katrin",
            ["name-format-separators"],
        ),
        (
            "University, Villanova and Sipior, Janice",
            ["erroneous-term-in-field"],
        ),
        (
            "Mourato, Inês and Dias, Álvaro and Pereira, Leandro",
            [],
        ),
        ("DUTTON, JANE E. and ROBERTS, LAURA", ["mostly-all-caps"]),
        ("Rai, Arun et al.", ["incomplete-field"]),
    ],
)
def test_get_quality_defects_author(
    author_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - author field"""
    v_t_record.data["author"] = author_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    assert v_t_record.has_quality_defects()
    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["author"][
            "note"
        ].split(",")


@pytest.mark.parametrize(
    "title_str, defects",
    [
        ("EDITORIAL", ["mostly-all-caps"]),
        ("SAMJ�", ["erroneous-symbol-in-field"]),
        ("™", ["erroneous-symbol-in-field"]),
    ],
)
def test_get_quality_defects_title(
    title_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data["title"] = title_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["title"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "journal_str, defects",
    [
        ("A U-ARCHIT URBAN", ["mostly-all-caps"]),
        ("SOS", ["container-title-abbreviated"]),
        ("SAMJ", ["container-title-abbreviated"]),
        ("SAMJ�", ["erroneous-symbol-in-field"]),
    ],
)
def test_get_quality_defects_journal(
    journal_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - journal field"""
    v_t_record.data["journal"] = journal_str

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["journal"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "name_str, defects",
    [
        ("Author, Name and Other, Author", ["thesis-with-multiple-authors"]),
    ],
)
def test_thesis_multiple_authors(
    name_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - thesis with multiple authors"""
    v_t_record.data["ENTRYTYPE"] = "thesis"
    v_t_record.data["author"] = name_str

    v_t_record.update_masterdata_provenance(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data["colrev_masterdata_provenance"]["author"][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()
