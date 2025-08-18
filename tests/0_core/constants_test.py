#!/usr/bin/env python
"""Test the colrev project settings"""
import colrev.settings
from colrev.constants import IDPattern
from colrev.constants import OperationsType
from colrev.constants import PDFPathType
from colrev.constants import ScreenCriterionType
from colrev.constants import SearchType


def test_search_type() -> None:
    assert set(SearchType.get_options()) == {
        "MD",
        "API",
        "OTHER",
        "FORWARD_SEARCH",
        "DB",
        "TOC",
        "FILES",
        "BACKWARD_SEARCH",
    }


def test_pdf_path_type() -> None:
    assert PDFPathType.get_options() == ["symlink", "copy"]


def test_screen_criterion_type() -> None:
    assert ScreenCriterionType.get_options() == [
        "inclusion_criterion",
        "exclusion_criterion",
    ]


def test_id_pattern() -> None:
    pattern = IDPattern("first_author_year")
    print(pattern)
    assert pattern.get_options() == ["first_author_year", "three_authors_year"]


def test_sharing_req() -> None:
    assert colrev.settings.ShareStatReq.get_options() == [
        "none",
        "processed",
        "screened",
        "completed",
    ]


def test_operation_type_print() -> None:
    print(OperationsType.search)
    assert OperationsType.get_manual_extra_operations() == [
        OperationsType.pdf_prep_man,
        OperationsType.pdf_get_man,
        OperationsType.prep_man,
    ]
