#!/usr/bin/env python
"""Tests for the DOIPatternChecker."""
from __future__ import annotations

import pytest

import colrev.qm.checkers.doi_not_matching_pattern


@pytest.fixture(scope="session", name="doi_not_matching_pattern_checker")
def fixture_doi_not_matching_pattern_checker(
    quality_model: colrev.qm.quality_model.QualityModel,
) -> colrev.qm.checkers.doi_not_matching_pattern.DOIPatternChecker:
    """Fixture for the DOIPatternChecker"""
    return colrev.qm.checkers.doi_not_matching_pattern.DOIPatternChecker(
        quality_model=quality_model
    )


@pytest.mark.parametrize(
    "input_string, expected",
    [
        ("10.1177/02683962211048201", True),
        ("https://journals.sagepub.com/doi/10.1177/02683962211048201", False),
        # Even though it is lexically correct, this should be a
        # problematic doi, according to this:
        # https://www.crossref.org/documentation/member-setup/constructing-your-dois/
        ("10.5555/2014-04-01", True),
    ],
)
def test_doi_not_matching_pattern(
    input_string: str,
    expected: bool,
    doi_not_matching_pattern_checker: colrev.qm.checkers.doi_not_matching_pattern.DOIPatternChecker,
    record_with_pdf: colrev.record.Record,
) -> None:
    """Test the doi-not-matching-pattern checker"""
    record_with_pdf.data["doi"] = input_string
    doi_not_matching_pattern_checker.run(record=record_with_pdf)
    if expected:
        assert not record_with_pdf.has_quality_defects()
    else:
        assert record_with_pdf.has_quality_defects()
