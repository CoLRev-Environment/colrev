#!/usr/bin/env python
"""Tests for the dataset"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager
from colrev.constants import ExitCodes
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState

# flake8: noqa: E501


def test_invalid_git_repository_error(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test handling of InvalidGitRepositoryError when initializing ReviewManager with an invalid repo path."""

    git_folder = base_repo_review_manager.path / ".git"
    temp_git_folder = base_repo_review_manager.path / ".git_temp"
    git_folder.rename(temp_git_folder)

    try:
        with pytest.raises(colrev_exceptions.RepoSetupError):
            colrev.dataset.Dataset(review_manager=base_repo_review_manager)
    finally:  # to avoid side-effects on other tests
        temp_git_folder.rename(git_folder)


def test_load_records_from_history(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test loading records from git history."""

    helpers.reset_commit(base_repo_review_manager, commit="changed_settings_commit")
    last_commit_sha = base_repo_review_manager.dataset.get_last_commit_sha()

    records_from_history = list(
        base_repo_review_manager.dataset.load_records_from_history(
            commit_sha=last_commit_sha
        )
    )

    helpers.reset_commit(base_repo_review_manager, commit="dedupe_commit")

    # Retrieve the last commit sha to use as a reference for loading history
    last_commit_sha = base_repo_review_manager.dataset.get_last_commit_sha()

    helpers.reset_commit(base_repo_review_manager, commit="prescreen_commit")

    # Load records from history using the last commit sha
    records_from_history = list(
        base_repo_review_manager.dataset.load_records_from_history(
            commit_sha=last_commit_sha
        )
    )

    # Check if the loaded records match the new record added
    assert len(records_from_history) == 3, "Expected three records from history"
    assert (
        records_from_history[0]["SrivastavaShainesh2015"]["colrev_status"]
        == RecordState.md_processed
    ), "The record status does not match the expected status."


def test_get_origin_state_dict(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the retrieval of origin state dictionary."""

    origin_state_dict = base_repo_review_manager.dataset.get_origin_state_dict()

    expected_dict = {
        "test_records.bib/Srivastava2015": RecordState.pdf_needs_manual_retrieval
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
        "test_records.bib/Srivastava2015": RecordState.pdf_needs_manual_retrieval
    }

    assert (
        committed_origin_state_dict == expected_dict
    ), "The committed origin state dictionary does not match the expected output."


@pytest.mark.parametrize(
    "record_id, expected_result",
    [
        ("Doe2021", True),
        ("Smith2022", False),
        ("Johnson2023", True),
    ],
)
def test_propagated_id(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    record_id: str,
    expected_result: bool,
) -> None:
    """Test the propagated_id method."""
    original_load_records_dict = base_repo_review_manager.dataset.load_records_dict

    # Mocking the load_records_dict method to return a dictionary with specific IDs and statuses
    base_repo_review_manager.dataset.load_records_dict = MagicMock(  # type: ignore
        return_value={
            "Doe2021": {
                "ID": "Doe2021",
                "colrev_status": RecordState.pdf_prepared,
            },
            "Smith2022": {
                "ID": "Smith2022",
                "colrev_status": RecordState.md_imported,
            },
            "Johnson2023": {
                "ID": "Johnson2023",
                "colrev_status": RecordState.rev_excluded,
            },
        }
    )

    result = base_repo_review_manager.dataset.propagated_id(record_id=record_id)
    assert result == expected_result, f"Propagated ID check failed for {record_id}"

    base_repo_review_manager.dataset.load_records_dict = original_load_records_dict  # type: ignore


def test_get_format_report(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the get_format_report method."""
    # TODO : develop the following test

    base_repo_review_manager.notified_next_operation = OperationsType.check

    records = base_repo_review_manager.dataset.load_records_dict()
    base_repo_review_manager.dataset.save_records_dict(records)
    # Test for None status
    report = base_repo_review_manager.dataset.format_records_file()

    # Assert for None status
    assert (
        report["status"] == ExitCodes.SUCCESS
    ), "Format report status did not match expected for None status"
    assert (
        report["msg"] == "Everything ok."
    ), "Format report message did not match expected for None status"

    records = {
        "SrivastavaShainesh2015": {
            "ID": "SrivastavaShainesh2015",
            "ENTRYTYPE": "article",
            "colrev_origin": ["test_records.bib/Srivastava2015"],
            "colrev_status": RecordState.md_needs_manual_preparation,
            "colrev_masterdata_provenance": {
                "author": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "journal": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "number": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "pages": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "title": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "volume": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "year": {"source": "test_records.bib/Srivastava2015", "note": ""},
            },
            "colrev_data_provenance": {
                "language": {"source": "test_records.bib/Srivastava2015", "note": ""}
            },
            "journal": "MIS Quarterly",
            "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
            "year": "2015",
            "volume": "39",
            "number": "1",
            "pages": "245--267",
            "language": "eng",
            "author": "Srivastava, Shirish C. and Shainesh, G.",
        }
    }
    base_repo_review_manager.dataset.save_records_dict(records)
    report = base_repo_review_manager.dataset.format_records_file()
    records = base_repo_review_manager.dataset.load_records_dict()

    assert records == {
        "SrivastavaShainesh2015": {
            "ID": "SrivastavaShainesh2015",
            "ENTRYTYPE": "article",
            "colrev_origin": ["test_records.bib/Srivastava2015"],
            "colrev_status": RecordState.md_prepared,
            "colrev_masterdata_provenance": {
                "author": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "journal": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "number": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "pages": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "title": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "volume": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "year": {"source": "test_records.bib/Srivastava2015", "note": ""},
            },
            "colrev_data_provenance": {
                "language": {"source": "test_records.bib/Srivastava2015", "note": ""}
            },
            "journal": "MIS Quarterly",
            "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
            "year": "2015",
            "volume": "39",
            "number": "1",
            "pages": "245--267",
            "language": "eng",
            "author": "Srivastava, Shirish C. and Shainesh, G.",
        }
    }

    with open(base_repo_review_manager.paths.records, "a", encoding="utf-8") as file:
        file.write("\n\n")

    report = base_repo_review_manager.dataset.format_records_file()
    print(report)
    assert report == {"status": 0, "msg": "Everything ok."}

    records = {
        "SrivastavaShainesh2015": {
            "ID": "SrivastavaShainesh2015",
            "ENTRYTYPE": "article",
            "colrev_origin": ["test_records.bib/Srivastava2015"],
            "colrev_status": RecordState.pdf_prepared,
            "colrev_masterdata_provenance": {
                "author": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "journal": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "number": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "pages": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "title": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "volume": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "year": {"source": "test_records.bib/Srivastava2015", "note": ""},
            },
            "colrev_data_provenance": {
                "language": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "file": {
                    "source": "test_records.bib/Srivastava2015",
                    "note": "author-not-in-pdf",
                },
            },
            "journal": "MIS Quarterly",
            "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
            "year": "2015",
            "volume": "39",
            "number": "1",
            "pages": "245--267",
            "file": "test.pdf",
            "language": "eng",
            "author": "Srivastava, Shirish C. and Shainesh, G.",
        }
    }
    base_repo_review_manager.dataset.save_records_dict(records)
    report = base_repo_review_manager.dataset.format_records_file()
    records = base_repo_review_manager.dataset.load_records_dict()
    assert records["SrivastavaShainesh2015"][Fields.D_PROV]["file"]["note"] == ""

    records = {
        "SrivastavaShainesh2015": {
            "ID": "SrivastavaShainesh2015",
            "ENTRYTYPE": "article",
            "colrev_origin": ["test_records.bib/Srivastava2015"],
            "colrev_masterdata_provenance": {
                "author": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "journal": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "number": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "pages": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "title": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "volume": {"source": "test_records.bib/Srivastava2015", "note": ""},
                "year": {"source": "test_records.bib/Srivastava2015", "note": ""},
            },
            "colrev_data_provenance": {
                "language": {"source": "test_records.bib/Srivastava2015", "note": ""}
            },
            "journal": "MIS Quarterly",
            "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
            "year": "2015",
            "volume": "39",
            "number": "1",
            "pages": "245--267",
            "language": "eng",
            "author": "Srivastava, Shirish C. and Shainesh, G.",
        }
    }
    base_repo_review_manager.dataset.save_records_dict(records)
    report = base_repo_review_manager.dataset.format_records_file()
    print(report)
    assert report == {
        "status": 1,
        "msg": " no status field in record (SrivastavaShainesh2015)",
    }


def test_get_commit_message(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the get_commit_message method."""
    # Setup
    commit_message = "Initial commit X"
    trivial_file_path = base_repo_review_manager.path / "trivial_file.txt"
    with open(trivial_file_path, "w") as file:
        file.write("This is a trivial change.")
    base_repo_review_manager.dataset.add_changes(trivial_file_path)

    base_repo_review_manager.dataset.create_commit(
        msg=commit_message, manual_author=True
    )

    # Test
    retrieved_commit_message = base_repo_review_manager.dataset.get_commit_message(
        commit_nr=0
    )

    # Assert
    assert (
        retrieved_commit_message.splitlines()[0] == commit_message
    ), f"Commit message did not match expected. Expected: {commit_message}, Got: {retrieved_commit_message.splitlines()[0]}"


def test_get_untracked_files(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the get_untracked_files method."""
    # Setup: Create a new file that is not tracked by git
    untracked_file_path = base_repo_review_manager.path / "untracked_file.txt"
    with open(untracked_file_path, "w") as file:
        file.write("This is an untracked file.")

    # Test
    untracked_files = base_repo_review_manager.dataset.get_untracked_files()

    # Assert
    assert (
        Path(untracked_file_path.name) in untracked_files
    ), "Untracked file was not detected."

    # Cleanup: Remove the untracked file
    untracked_file_path.unlink()


def test_has_untracked_search_records(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the has_untracked_search_records method."""
    # Setup: Create a new search record file that is not tracked by git
    search_dir = base_repo_review_manager.paths.search
    untracked_search_file_path = (
        base_repo_review_manager.path / search_dir / "untracked_search_record.txt"
    )
    untracked_search_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(untracked_search_file_path, "w") as file:
        file.write("This is an untracked search record.")

    # Test
    has_untracked = base_repo_review_manager.dataset.has_untracked_search_records()

    # Assert
    assert has_untracked, "Untracked search record was not detected."

    # Cleanup: Remove the untracked search record file
    untracked_search_file_path.unlink()


def test_has_untracked_search_records_empty(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the has_untracked_search_records method when there are no untracked search records."""
    # Setup: Ensure there are no untracked search records
    search_dir = base_repo_review_manager.paths.search
    search_dir_path = base_repo_review_manager.path / search_dir
    if search_dir_path.exists():
        for file in search_dir_path.iterdir():
            file.unlink()
        search_dir_path.rmdir()

    # Test
    has_untracked = base_repo_review_manager.dataset.has_untracked_search_records()

    # Assert
    assert not has_untracked, "Untracked search records were incorrectly detected."


def test_has_untracked_search_records_present(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the has_untracked_search_records method when there are untracked search records."""
    # Setup: Create a new search record file that is not tracked by git
    search_dir = base_repo_review_manager.paths.search
    untracked_search_file_path = (
        base_repo_review_manager.path
        / search_dir
        / "another_untracked_search_record.txt"
    )
    untracked_search_file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(untracked_search_file_path, "w") as file:
        file.write("This is another untracked search record.")

    # Test
    has_untracked = base_repo_review_manager.dataset.has_untracked_search_records()

    # Assert
    assert has_untracked, "Untracked search record was not detected."

    # Cleanup: Remove the untracked search record file
    untracked_search_file_path.unlink()


def test_get_repo(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the get_repo method."""
    # Test
    with pytest.raises(colrev_exceptions.ReviewManagerNotNotifiedError):
        base_repo_review_manager.dataset.get_repo()

    base_repo_review_manager.notified_next_operation = OperationsType.check

    # Test
    base_repo_review_manager.dataset.get_repo()


def test_has_changes_no_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method when there are no changes."""

    # Test
    has_changes = base_repo_review_manager.dataset.has_record_changes()

    # Assert
    assert not has_changes, "has_changes incorrectly detected changes."


def test_has_changes_with_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method when there are changes."""
    # Setup
    # Create a new file to simulate changes
    new_file_path = base_repo_review_manager.path / "new_file.txt"
    new_file_path.write_text("This is a new file.")
    base_repo_review_manager.dataset._git_repo.git.add("-A")

    # Test
    has_changes = base_repo_review_manager.dataset.has_changes(Path("new_file.txt"))

    # Assert
    assert has_changes, "has_changes failed to detect changes."


def test_has_changes_with_relative_path_new_file(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method with relative path for a new file."""
    # Setup
    # Create a new file to simulate changes
    new_file_path = base_repo_review_manager.path / "new_file_relative.txt"
    new_file_path.write_text("This is a new file with relative path.")
    base_repo_review_manager.dataset._git_repo.git.add("-A")

    # Test
    has_changes = base_repo_review_manager.dataset.has_changes(
        Path("new_file_relative.txt")
    )

    # Assert
    assert (
        has_changes
    ), "has_changes failed to detect changes with relative path for new file."


def test_has_changes_staged_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method with change_type 'staged' when there are staged changes."""
    # Setup
    # Create a new file and stage it to simulate staged changes
    new_file_path = base_repo_review_manager.path / "staged_file.txt"
    new_file_path.write_text("This is a staged file.")
    base_repo_review_manager.dataset._git_repo.git.add(new_file_path)

    # Test
    has_staged_changes = base_repo_review_manager.dataset.has_changes(
        Path("staged_file.txt"), change_type="staged"
    )

    # Assert
    assert has_staged_changes, "has_changes failed to detect staged changes."


def test_has_changes_staged_no_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method with change_type 'staged' when there are no staged changes."""

    base_repo_review_manager.notified_next_operation = OperationsType.check

    # Test
    has_staged_changes = base_repo_review_manager.dataset.has_record_changes(
        change_type="staged"
    )

    # Assert
    assert not has_staged_changes, "has_changes incorrectly detected staged changes."


def test_has_changes_unstaged_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method with change_type 'unstaged' when there are unstaged changes."""
    # Setup
    # Create a new file to simulate unstaged changes
    new_file_path = base_repo_review_manager.path / "unstaged_file.txt"
    new_file_path.write_text("This is an unstaged file.")
    # Note: Do not stage the file to keep it as an unstaged change

    base_repo_review_manager.notified_next_operation = OperationsType.check

    # Test
    has_changes = base_repo_review_manager.dataset.has_changes(
        Path("unstaged_file.txt"), change_type="unstaged"
    )

    # Assert
    assert has_changes, "has_changes failed to detect unstaged changes."


def test_has_changes_unstaged_no_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method with change_type 'unstaged' when there are no unstaged changes."""
    # Setup
    # Ensure there are no unstaged changes by staging any existing changes
    base_repo_review_manager.dataset._git_repo.git.add("-A")

    base_repo_review_manager.notified_next_operation = OperationsType.check

    # Test
    has_changes = base_repo_review_manager.dataset.has_record_changes(
        change_type="unstaged"
    )

    # Assert
    assert not has_changes, "has_changes incorrectly detected unstaged changes."


def test_has_changes_with_relative_path_settings(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test has_changes method with relative path for settings.json."""

    # Test
    has_changes = base_repo_review_manager.dataset.has_changes(Path("settings.json"))

    # Assert
    assert (
        not has_changes
    ), "has_changes failed to detect changes with relative path for settings.json."


def test_add_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test add_changes method."""
    # Setup
    # Create a new file to simulate changes
    new_file_path = base_repo_review_manager.path / "new_file_to_add.txt"
    new_file_path.write_text("This file will be added.")

    # Test
    base_repo_review_manager.dataset.add_changes(new_file_path)

    # Assert
    assert (
        new_file_path.name in base_repo_review_manager.dataset._git_repo.git.ls_files()
    ), "add_changes failed to add the new file to the repository."

    with pytest.raises(FileNotFoundError):
        base_repo_review_manager.dataset.add_changes(Path("non_existsnt.file"))

    base_repo_review_manager.dataset.add_changes(
        Path("non_existsnt.file"), ignore_missing=True
    )


def test_add_changes_remove(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test add_changes method with remove flag."""
    # Setup
    # Create a new file and add it to simulate removal
    file_to_remove_path = base_repo_review_manager.path / "file_to_remove.txt"
    file_to_remove_path.write_text("This file will be removed.")
    base_repo_review_manager.dataset.add_changes(file_to_remove_path)

    # Ensure file is added
    assert (
        file_to_remove_path.name
        in base_repo_review_manager.dataset._git_repo.git.ls_files()
    ), "Setup failed: file_to_remove.txt was not added to the repository."

    # Test removal
    base_repo_review_manager.dataset.add_changes(file_to_remove_path, remove=True)

    # Assert
    assert (
        file_to_remove_path.name
        not in base_repo_review_manager.dataset._git_repo.git.ls_files()
    ), "add_changes failed to remove the file from the repository."


def test_add_changes_ignore_missing(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test add_changes method with ignore_missing flag."""
    # Setup
    # Create a path for a file that does not exist to simulate missing file
    missing_file_path = base_repo_review_manager.path / "missing_file.txt"

    # Test
    # This should not raise FileNotFoundError because of the ignore_missing flag
    base_repo_review_manager.dataset.add_changes(missing_file_path, ignore_missing=True)

    # Assert
    # Since the file does not exist, it should not be added, but also should not raise an error
    assert (
        missing_file_path.name
        not in base_repo_review_manager.dataset._git_repo.git.ls_files()
    ), "add_changes incorrectly handled the missing file with ignore_missing flag."


def test_stash_unstaged_changes(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test stash_unstaged_changes method."""
    # Setup
    # Create a new file to simulate unstaged changes
    unstaged_file_path = base_repo_review_manager.path / "readme.md"
    unstaged_file_path.write_text("This is an unstaged file.")

    # Test
    base_repo_review_manager.dataset.stash_unstaged_changes()

    # Assert
    assert (
        Path(unstaged_file_path.name)
        not in base_repo_review_manager.dataset.get_untracked_files()
    ), "The file should not be recognized as an unstaged change after stashing."
