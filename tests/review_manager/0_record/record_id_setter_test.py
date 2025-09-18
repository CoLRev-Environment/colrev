#!/usr/bin/env python
"""Tests for the dataset"""
import pytest

import colrev.review_manager
from colrev.constants import Fields
from colrev.constants import IDPattern
from colrev.constants import RecordState

# flake8: noqa: E501


def test_load_records_dict_not_notified_exception(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test load_records_dict raises not_notified_exception."""

    base_repo_review_manager.notified_next_operation = None

    with pytest.raises(Exception):
        base_repo_review_manager.dataset.load_records_dict()


@pytest.mark.parametrize(
    "record_dict, expected_id",
    [
        ({"author": "Doe, John and Smith, Jane", "year": "2021"}, "Doe2021"),
        ({}, "AnonymousNoYear"),
    ],
)
def test_id_generation_first_author_year(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    record_dict,
    expected_id,
) -> None:
    """Test the id generation process for the first_author_year ID pattern."""

    id_setter = colrev.record.record_id_setter.IDSetter(
        id_pattern=IDPattern.first_author_year,
        skip_local_index=False,
        logger=base_repo_review_manager.report_logger,
    )
    temp_id = id_setter._generate_id(record_dict)

    assert (
        temp_id == expected_id
    ), "ID generation with author failed for first_author_year pattern"


@pytest.mark.parametrize(
    "record_dict, expected_id",
    [
        (
            {"author": "Doe, John and Smith, Jane and Doe, Alice", "year": "2021"},
            "DoeSmithDoe2021",
        ),
        (
            {
                "author": "Clary, William Grant and Dick, Geoffrey N. and Akbulut, Asli Yagmur and Van Slyke, Craig",
                "year": "2022",
            },
            "ClaryDickAkbulutEtAl2022",
        ),
        ({}, "AnonymousNoYear"),
    ],
)
def test_id_generation_three_authors_year(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
    record_dict,
    expected_id,
) -> None:
    """Test the id generation process for the three_authors_year ID pattern."""

    id_setter = colrev.record.record_id_setter.IDSetter(
        id_pattern=IDPattern.three_authors_year,
        skip_local_index=True,
        logger=base_repo_review_manager.report_logger,
    )
    temp_id = id_setter._generate_id(record_dict)

    assert (
        temp_id == expected_id
    ), "ID generation with author failed for three_authors_year pattern"


def test_id_generation_selected(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the id generation process for the three_authors_year ID pattern."""

    record_dict = {
        "0001": {
            "ID": "0001",
            "author": "Wagner, G and Lukyanenko, R and Paré, G",
            "year": "2022",
            Fields.STATUS: RecordState.rev_synthesized,
        }
    }

    id_setter = colrev.record.record_id_setter.IDSetter(
        id_pattern=IDPattern.three_authors_year,
        skip_local_index=True,
        logger=base_repo_review_manager.report_logger,
    )
    actual = id_setter.set_ids(record_dict)
    assert "0001" in actual  # because status is post-md-processed

    actual = id_setter.set_ids(record_dict, selected_ids=["0001"])
    assert "WagnerLukyanenkoPare2022" in actual
