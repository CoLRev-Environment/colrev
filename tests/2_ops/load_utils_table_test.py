#!/usr/bin/env python
"""Tests of the load utils for bib files"""
from pathlib import Path

import colrev.ops.load_utils_bib
import colrev.review_manager
import colrev.settings


def test_load(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the load utils for bib files"""

    helpers.reset_commit(review_manager=base_repo_review_manager, commit="load_commit")

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/table_tests.csv"),
        search_type=colrev.settings.SearchType.OTHER,
        search_parameters={"scope": {"path": "test"}},
        comment="",
    )

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("table_tests.csv"),
        target=Path("data/search/") / Path("table_tests.csv"),
    )
    load_operation = base_repo_review_manager.get_load_operation()

    table_loader = colrev.ops.load_utils_table.TableLoader(
        load_operation=load_operation, source=search_source
    )
    table_entries = table_loader.load_table_entries()
    records = table_loader.convert_to_records(entries=table_entries)

    expected = (
        helpers.test_data_path / Path("load_utils/") / Path("table_tests_expected.bib")
    ).read_text(encoding="utf-8")

    actual = base_repo_review_manager.dataset.parse_bibtex_str(recs_dict_in=records)
    if expected != actual:
        with open(
            helpers.test_data_path
            / Path("load_utils/")
            / Path("table_tests_expected.bib"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(actual)
    assert actual == expected
