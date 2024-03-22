#!/usr/bin/env python
"""Tests of the CoLRev checks"""
import platform
from dataclasses import asdict
from pathlib import Path

import colrev.review_manager
from colrev.constants import SearchType


def test_checks(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the checks"""

    checker = colrev.checker.Checker(review_manager=base_repo_review_manager)

    expected = ["0.11.0", "0.11.0"]
    actual = checker.get_colrev_versions()
    assert expected == actual

    checker.check_repository_setup()

    # Note: no assertion (yet)
    checker.in_virtualenv()

    actual = checker.check_repo_extended()
    current_platform = platform.system()
    expected = []
    assert expected == actual

    actual = checker.check_repo()  # type: ignore

    expected = {"status": 0, "msg": "Everything ok."}  # type: ignore
    assert expected == actual

    expected = []
    actual = checker.check_repo_basics()
    assert expected == actual

    if current_platform in ["Linux"]:
        expected = []
        actual = checker.check_change_in_propagated_id(
            prior_id="Srivastava2015",
            new_id="Srivastava2015a",
            project_context=base_repo_review_manager.path,
        )
        assert expected == actual

    base_repo_review_manager.get_search_sources()
    search_sources = base_repo_review_manager.settings.sources
    actual = [asdict(s) for s in search_sources]  # type: ignore

    if current_platform in ["Linux", "Darwin"]:
        expected = [  # type: ignore
            # {  # type: ignore
            #     "endpoint": "colrev.files_dir",
            #     "filename": Path("data/search/pdfs.bib"),
            #     "search_type": SearchType.PDFS,
            #     "search_parameters": {"scope": {"path": "data/pdfs"}},
            #     "comment": "",
            # },
            {  # type: ignore
                "endpoint": "colrev.unknown_source",
                "filename": Path("data/search/test_records.bib"),
                "search_type": SearchType.DB,
                "search_parameters": {
                    "query_file": "data/search/test_records_query.txt"
                },
                "comment": "",
            },
        ]
        assert expected == actual
