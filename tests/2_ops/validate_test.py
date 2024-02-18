import colrev.review_manager

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
                    "colrev_status": colrev.record.RecordState.pdf_needs_manual_retrieval,
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
                    "title": "Bridging the service divide through digitally enabled service innovations: Evidence from Indian healthcare service providers",
                    "year": "2015",
                    "volume": "39",
                    "number": "1",
                    "pages": "245--267",
                    "language": "eng",
                    "author": "Srivastava, Shirish C. and Shainesh, G.",
                },
                "change_score_max": 0.010204081632652962,
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
                        "colrev_status": colrev.record.RecordState.md_retrieved,
                        "change_score": 0.010204081632652962,
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
                "msg": "Get PDFs",
                "author": "script: -s test_records.bib",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Pre-screen (include_all)",
                "author": "script: -s test_records.bib",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Merge duplicate records",
                "author": "script: -s test_records.bib",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Prepare records (prep)",
                "author": "script: -s test_records.bib",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
            {
                "msg": "Load test_records.bib",
                "author": "script: -s test_records.bib",
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
                "msg": "Initial commit",
                "author": "Tester Name",
                "author_email": "tester@email.de",
                "committer": "Tester Name",
                "committer_email": "tester@email.de",
            },
        ]
    }
    print(report)

    assert report == expected_report
