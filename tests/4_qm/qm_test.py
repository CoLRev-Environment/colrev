#!/usr/bin/env python
"""Tests for the quality model"""
from __future__ import annotations

import pytest

import colrev.qm.quality_model
import colrev.record


@pytest.mark.parametrize(
    "author_str, defect_type, defect",
    [
        ("RAI", "mostly-all-caps", True),  # all-caps
        # this one passes, because of the `,`
        ("Rai, Arun and B,", "incomplete-field", True),
        # FIXME: incomplete part, but error is not marked correctly
        ("Rai, Arun and B", "incomplete-field", True),
        # additional title
        ("Rai, PhD, Arun", "name-format-titles", True),
        # FIXME: additional title, but fails as validation is case-sensitive
        ("Rai, Phd, Arun", "name-format-titles", True),
        # This fails because of the PhD in name
        ("GuyPhD, Arun", "", False),  #
        (
            "Rai, Arun; Straub, Detmar",
            "name-format-separators",
            True,
        ),  # incorrect delimiter
        # author without capital letters
        # NOTE: it's not a separator error, should be something more relevant
        (
            "Mathiassen, Lars and jonsson, katrin",
            "name-format-separators",
            True,
        ),
        # University in author field
        (
            "University, Villanova and Sipior, Janice",
            "erroneous-term-in-field",
            True,
        ),
        # Special characters
        (
            "Mourato, Inês and Dias, Álvaro and Pereira, Leandro",
            "",
            False,
        ),
        ("DUTTON, JANE E. and ROBERTS, LAURA", "mostly-all-caps", True),  # Caps
    ],
)
def test_get_quality_defects_author(
    author_str: str,
    defect_type: str,
    defect: bool,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - author field"""
    v_t_record.data["author"] = author_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if defect:
        assert v_t_record.has_quality_defects()
        assert (
            defect_type
            in v_t_record.data["colrev_masterdata_provenance"]["author"]["note"]
        )
    else:
        assert not v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "title_str, defect_type, defect",
    [
        ("EDITORIAL", "mostly-all-caps", True),
        ("A U-ARCHIT URBAN", "container-title-abbreviated", True),
        ("SOS", "container-title-abbreviated", True),
        ("SAMJ", "container-title-abbreviated", True),
        ("SAMJ�", "erroneous-symbol-in-field", True),
        ("™", "erroneous-symbol-in-field", True),
    ],
)
def test_get_quality_defects_title(
    title_str: str,
    defect_type: str,
    defect: bool,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data["title"] = title_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if defect:
        assert v_t_record.has_quality_defects()
        assert (
            defect_type
            in v_t_record.data["colrev_masterdata_provenance"]["title"]["note"]
        )
    else:
        assert not v_t_record.has_quality_defects()
