#!/usr/bin/env python
"""Tests of the CoLRev validate operation"""
import colrev.review_manager
from colrev.constants import OperationsType
from colrev.constants import RecordState

# flake8: noqa: E501


def test_prep_validation(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the prep validation"""

    validate_operation = base_repo_review_manager.get_validate_operation()

    report = validate_operation.main(scope=".", filter_setting="prepare")

    expected_report = {
        "prep_prescreen_exclusions": [],
        "prep": [
            {
                "record_dict": {
                    "ID": "SrivastavaShainesh2015",
                    "ENTRYTYPE": "article",
                    "colrev_origin": ["test_records.bib/Srivastava2015"],
                    "colrev_status": RecordState.pdf_needs_manual_retrieval,
                    "colrev_masterdata_provenance": {
                        "author": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                        "journal": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                        "number": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                        "pages": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                        "title": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                        "volume": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                        "year": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        },
                    },
                    "colrev_data_provenance": {
                        "language": {
                            "source": "test_records.bib/Srivastava2015",
                            "note": "",
                        }
                    },
                    "journal": "MIS Quarterly",
                    "title": "Bridging the service divide through digitally enabled service innovations: {E}vidence from {I}ndian healthcare service providers",
                    "year": "2015",
                    "volume": "39",
                    "number": "1",
                    "pages": "245--267",
                    "language": "eng",
                    "author": "Srivastava, Shirish C. and Shainesh, G.",
                },
                "change_score_max": 0.0,
                "origins": [
                    {
                        "ID": "Srivastava2015",
                        "ENTRYTYPE": "article",
                        "journal": "MIS Quarterly",
                        "title": "Bridging the service divide through digitally enabled service innovations: {E}vidence from {I}ndian healthcare service providers",
                        "year": "2015",
                        "volume": "39",
                        "number": "1",
                        "pages": "245--267",
                        "language": "eng",
                        "author": "Srivastava, Shirish C. and Shainesh, G.",
                        "colrev_origin": ["test_records.bib/Srivastava2015"],
                        "colrev_status": RecordState.md_retrieved,
                        "change_score": 0.0,
                    }
                ],
            }
        ],
    }

    assert report == expected_report


def test_contributor_validation(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the contributor validation"""

    validate_operation = base_repo_review_manager.get_validate_operation()

    report = validate_operation.main(
        scope="tester@email.de", filter_setting="contributor"
    )
    print(report)
    for item in report["contributor_commits"]:
        print(item)
        assert "colrev validate " + item["commit_sha"] == item["validate"]
        item.pop("commit_sha", None)
        item.pop("validate", None)
        item.pop("date", None)

    expected_report = {
        "contributor_commits": [
            {
                "msg": "PDFs: get and prepare",
                "author": "script:",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Prescreen: include all",
                "author": "script:",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Dedupe: merge duplicate records",
                "author": "script:",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Prep: improve record metadata",
                "author": "script:",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Load: data/search/test_records.bib → data/records.bib",
                "author": "script:",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "add test_records.bib",
                "author": "Tester Name",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "change settings",
                "author": "Tester Name",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Init: Create CoLRev project",
                "author": "Tester Name",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Init: Create CoLRev repository",
                "author": "Tester Name",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
        ]
    }
    print(report)

    assert report == expected_report


def test_get_changed_records(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the retrieval of changed records based on a selected commit."""

    validate_operation = base_repo_review_manager.get_validate_operation()

    # Simulate changes in records and commit those changes
    changed_record_dict = {
        "SrivastavaShainesh2015": {
            "colrev_origin": ["test_records.bib/Srivastava2015"],
            "colrev_status": RecordState.pdf_prepared,
            "ID": "SrivastavaShainesh2015",
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
    base_repo_review_manager.dataset.save_records_dict(changed_record_dict)
    base_repo_review_manager.dataset.git_repo.add_changes(
        base_repo_review_manager.paths.RECORDS_FILE
    )
    commit_message = "Test commit for changed records"
    base_repo_review_manager.create_commit(msg=commit_message, manual_author=True)
    # Retrieve the last commit SHA
    last_commit_sha = base_repo_review_manager.dataset.git_repo.get_last_commit_sha()

    base_repo_review_manager.notified_next_operation = OperationsType.check

    # Retrieve changed records based on the last commit
    changed_records = validate_operation._get_changed_records(
        target_commit=last_commit_sha
    )
    expected_changes = [
        {
            "ID": "SrivastavaShainesh2015",
            "ENTRYTYPE": "article",
            "colrev_origin": ["test_records.bib/Srivastava2015"],
            "colrev_status": RecordState.pdf_prepared,
            "journal": "Nature",
            "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
            "year": "2015",
            "volume": "39",
            "number": "1",
            "pages": "245--267",
            "language": "eng",
            "author": "Srivastava, Shirish C. and Shainesh, G.",
            "changed_in_target_commit": "True",
        }
    ]
    # Check if the changed records match the expected changes
    assert (
        changed_records == expected_changes
    ), "The retrieved changed records do not match the expected changes."
