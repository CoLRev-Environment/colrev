#!/usr/bin/env python
"""Tests for the dataset"""
import git
import pytest

import colrev.review_manager

# flake8: noqa: E501


def test_get_origin_state_dict(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the retrieval of origin state dictionary."""

    origin_state_dict = base_repo_review_manager.dataset.get_origin_state_dict()

    expected_dict = {
        "test_records.bib/Srivastava2015": colrev.record.RecordState.pdf_needs_manual_retrieval
    }

    assert (
        origin_state_dict == expected_dict
    ), "The origin state dictionary does not match the expected output."


def test_get_committed_origin_state_dict(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the retrieval of committed origin state dictionary."""

    committed_origin_state_dict = (
        base_repo_review_manager.dataset.get_committed_origin_state_dict()
    )

    expected_dict = {
        "test_records.bib/Srivastava2015": colrev.record.RecordState.pdf_needs_manual_retrieval
    }

    assert (
        committed_origin_state_dict == expected_dict
    ), "The committed origin state dictionary does not match the expected output."


def test_get_changed_records(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the retrieval of changed records based on a selected commit."""

    # Simulate changes in records and commit those changes
    changed_record_dict = {
        "Srivastava2015": {
            "colrev_origin": "test_records.bib/Srivastava2015",
            "colrev_status": colrev.record.RecordState.pdf_prepared,
            "ID": "Srivastava2015",
            "ENTRYTYPE": "article",
            "author": "Srivastava, Shirish C. and Shainesh, G.",
            "journal": "Nature",
            "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
            "year": "2015",
            "volume": "39",
            "number": "1",
            "pages": "245--267",
            "language": "eng",
        }
    }
    base_repo_review_manager.dataset.save_records_dict(records=changed_record_dict)
    base_repo_review_manager.dataset._add_record_changes()
    commit_message = "Test commit for changed records"
    author = git.Actor("Author Name", "author@example.com")
    committer = git.Actor("Committer Name", "committer@example.com")
    base_repo_review_manager.dataset.create_commit(
        msg=commit_message, author=author, committer=committer, hook_skipping=True
    )

    # Retrieve the last commit SHA
    last_commit_sha = base_repo_review_manager.dataset.get_last_commit_sha()

    # Retrieve changed records based on the last commit
    changed_records = base_repo_review_manager.dataset.get_changed_records(
        target_commit=last_commit_sha
    )
    expected_changes = [{'ID': 'Srivastava2015', 'ENTRYTYPE': 'article', 'colrev_origin': ['test_records.bib/Srivastava2015'], 'colrev_status': colrev.record.RecordState.pdf_prepared, 'journal': 'Nature', 'title': 'Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers', 'year': '2015', 'volume': '39', 'number': '1', 'pages': '245--267', 'language': 'eng', 'author': 'Srivastava, Shirish C. and Shainesh, G.', 'changed_in_target_commit': 'True'}]
    # Check if the changed records match the expected changes
    assert (
        changed_records == expected_changes
    ), "The retrieved changed records do not match the expected changes."


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
