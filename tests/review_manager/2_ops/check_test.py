#!/usr/bin/env python
"""Tests of the CoLRev checks"""
import json as stdjson
import platform
import typing

import colrev.review_manager


def test_checks(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the checks"""

    checker = colrev.ops.checker.Checker(review_manager=base_repo_review_manager)

    checker.check_repository_setup()

    # Note: no assertion (yet)
    checker.in_virtualenv()

    actual = checker.check_repo_extended()
    current_platform = platform.system()
    expected: typing.List[str] = []
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

    search_sources = base_repo_review_manager.settings.sources
    actual = [s.model_dump() for s in search_sources]  # type: ignore

    def canon(d: dict) -> str:
        # Canonicalize dicts so we can compare order-insensitively
        return stdjson.dumps(d, sort_keys=True)

    if current_platform in ["Linux", "Darwin"]:
        expected = [  # type: ignore
            {  # type: ignore
                "platform": "colrev.unknown_source",
                "search_results_path": "data/search/test_records.bib",
                "search_type": "DB",
                "search_string": "",
            },
            {  # type: ignore
                "platform": "colrev.files_dir",
                "search_results_path": "data/search/files.bib",
                "search_type": "FILES",
                # "search_parameters": {"scope": {"path": "data/pdfs"}},
                "search_string": "",
            },
        ]

        assert sorted(map(canon, actual)) == sorted(
            map(canon, expected)  # type: ignore
        )
