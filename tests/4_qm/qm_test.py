#!/usr/bin/env python
"""Tests for the quality model"""
from __future__ import annotations

import pytest

import colrev.qm.quality_model
import colrev.record


@pytest.mark.parametrize(
    "author_str, defect",
    [
        ("RAI", True),  # all-caps
        ("Rai, Arun and B", True),  # incomplete part
        ("Rai, Phd, Arun", True),  # additional title
        ("Rai, Arun; Straub, Detmar", True),  # incorrect delimiter
        (
            "Mathiassen, Lars and jonsson, katrin",
            True,
        ),  # author without capital letters
        (
            "University, Villanova and Sipior, Janice",
            True,
        ),  # University in author field
        (
            "Mourato, Inês and Dias, Álvaro and Pereira, Leandro",
            False,
        ),  # Special characters
        ("DUTTON, JANE E. and ROBERTS, LAURA", True),  # Caps
    ],
)
def test_get_quality_defects_author(
    author_str: str,
    defect: bool,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - author field"""
    v_t_record.data["author"] = author_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if defect:
        assert v_t_record.has_quality_defects()
    else:
        assert not v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "title_str, defect",
    [
        ("EDITORIAL", True),  # all-caps
    ],
)
def test_get_quality_defects_title(
    title_str: str,
    defect: bool,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data["title"] = title_str
    v_t_record.update_masterdata_provenance(qm=quality_model)
    if defect:
        assert v_t_record.has_quality_defects()
    else:
        assert not v_t_record.has_quality_defects()
