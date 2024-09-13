#!/usr/bin/env python
"""Tests of the CoLRev search operation"""
from pathlib import Path
from unittest.mock import patch

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.review_manager
import colrev.settings
from colrev.constants import EndpointType
from colrev.constants import SearchType


@patch("colrev.review_manager.ReviewManager.in_ci_environment")
def test_search(  # type: ignore
    ci_env_patcher, base_repo_review_manager: colrev.review_manager.ReviewManager
) -> None:
    """Test the search operation"""

    ci_env_patcher.return_value = True
    search_operation = base_repo_review_manager.get_search_operation()
    base_repo_review_manager.settings.search.retrieve_forthcoming = False
    search_operation.main(rerun=True)


def test_search_selection(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
) -> None:
    """Test the search selection"""
    helpers.reset_commit(base_repo_review_manager, commit="load_commit")

    search_operation = base_repo_review_manager.get_search_operation()

    with pytest.raises(
        colrev_exceptions.ParameterError,
    ):
        search_operation.main(rerun=False, selection_str="BROKEN")

    # Note : DB search registered, which requires input() to complete
    # search_operation.main(rerun=False, selection_str="data/search/test_records.bib")


def test_search_add_source(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the search add_source"""

    search_operation = base_repo_review_manager.get_search_operation()
    add_source = colrev.settings.SearchSource(
        endpoint="colrev.crossref",
        filename=Path("data/search/crossref_search.bib"),
        search_type=SearchType.DB,
        search_parameters={
            "url": "https://api.crossref.org/works?query.bibliographic=test"
        },
        comment="",
    )

    package_manager = search_operation.review_manager.get_package_manager()

    search_source_class = package_manager.get_package_endpoint_class(
        package_type=EndpointType.search_source,
        package_identifier=add_source.endpoint,
    )

    endpoint = search_source_class(
        source_operation=search_operation, settings=add_source.model_dump()
    )
    query = "issn=1234-5678"
    endpoint.add_endpoint(search_operation, query)  # type: ignore

    search_operation.review_manager.settings.sources.pop()


def test_search_get_unique_filename(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    """Test the search.get_unique_filename()"""

    search_operation = base_repo_review_manager.get_search_operation()
    expected = Path("data/search/test_records_1.bib")
    actual = search_operation.get_unique_filename(file_path_string="test_records.bib")
    assert expected == actual

    expected = Path("data/search/dbs.bib")
    actual = search_operation.get_unique_filename(file_path_string="dbs.bib")
    assert expected == actual


# TODO : reactivate
# def test_search_remove_forthcoming(  # type: ignore
#     base_repo_review_manager: colrev.review_manager.ReviewManager, helpers
# ) -> None:
#     """Test the search.remove_forthcoming()"""

#     helpers.reset_commit(
#         base_repo_review_manager, commit="changed_settings_commit"
#     )

#     print(Path.cwd())  # To facilitate debugging

#     helpers.retrieve_test_file(
#         source=Path("data/search_files/crossref_feed.bib"),
#         target=Path("data/search/crossref_issn=1234-5678.bib"),
#     )

#     search_operation = base_repo_review_manager.get_search_operation()

#     base_repo_review_manager.settings.search.retrieve_forthcoming = False
#     package_manager = search_operation.review_manager.get_package_manager()

#     search_source = package_manager.load_packages(
#         package_type=EndpointType.search_source,
#         selected_packages=[{"endpoint": "colrev.crossref"}],
#         operation=search_operation,
#         instantiate_objects=False,
#     )
#     s_obj = search_source["colrev.crossref"]
#     query = "issn=1234-5678"
#     source = s_obj.add_endpoint(search_operation, query, None)  # type: ignore
#     search_operation.review_manager.settings.sources.append(source)
#     search_operation.review_manager.save_settings()

#     search_operation.remove_forthcoming(source=source)


#     with open(source.filename, encoding="utf8") as bibtex_file:
#         records = base_repo_review_manager.dataset.load_records_dict(
#             load_str=bibtex_file.read()
#         )
#         assert "00003" not in records.keys()

#     source.filename.unlink()
#     search_operation.review_manager.settings.sources.pop()
