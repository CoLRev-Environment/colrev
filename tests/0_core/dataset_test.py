#!/usr/bin/env python
"""Tests for the dataset"""
import pytest

import colrev.review_manager

# flake8: noqa: E501


@pytest.mark.parametrize(
    "record_dict, expected_id",
    [
        ({"author": "Doe, John and Smith, Jane", "year": "2021"}, "Doe2021"),
        ({}, "AnonymousNoYear"),
    ],
)
def test_id_generation_first_author_year(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
    record_dict,
    expected_id,
) -> None:
    """Test the id generation process for the first_author_year ID pattern."""
    local_index = base_repo_review_manager.get_local_index()

    base_repo_review_manager.settings.project.id_pattern = (
        colrev.settings.IDPattern.first_author_year
    )
    temp_id = base_repo_review_manager.dataset._generate_temp_id(
        local_index=local_index, record_dict=record_dict
    )

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
    local_index = base_repo_review_manager.get_local_index()

    base_repo_review_manager.settings.project.id_pattern = (
        colrev.settings.IDPattern.three_authors_year
    )
    temp_id = base_repo_review_manager.dataset._generate_temp_id(
        local_index=local_index, record_dict=record_dict
    )

    assert (
        temp_id == expected_id
    ), "ID generation with author failed for three_authors_year pattern"
