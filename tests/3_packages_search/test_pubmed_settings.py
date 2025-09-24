from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.search_file
from colrev.constants import SearchType
from colrev.packages.pubmed.src.pubmed import PubMedSearchSource


@pytest.fixture()
def pubmed_search_file_factory():
    """Return a factory to build PubMed search files for validation tests."""

    def _build(version_marker, include_version_param=True):
        search_file = colrev.search_file.ExtendedSearchFile(
            platform="colrev.pubmed",
            search_results_path=Path("data/search/test_pubmed.bib"),
            search_type=SearchType.API,
            search_string="https://pubmed.ncbi.nlm.nih.gov/?term=validation",
            comment="",
        )

        search_parameters = {"url": search_file.search_string}
        if include_version_param and version_marker is not None:
            search_parameters["version"] = version_marker
        search_file.search_parameters = search_parameters

        # Explicitly set version attribute to mirror persisted search files
        if version_marker is not None:
            search_file.version = version_marker
        else:
            search_file.version = None

        return search_file

    return _build


def test_pubmed_validate_accepts_current_version(pubmed_search_file_factory):
    search_file = pubmed_search_file_factory(PubMedSearchSource.CURRENT_SYNTAX_VERSION)

    PubMedSearchSource(search_file=search_file)


def test_pubmed_validate_rejects_missing_version(pubmed_search_file_factory):
    search_file = pubmed_search_file_factory(
        version_marker=None, include_version_param=False
    )

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        PubMedSearchSource(search_file=search_file)

    assert str(exc_info.value) == "PubMed version should be 1.0.0, found None"


def test_pubmed_validate_rejects_mismatched_version(pubmed_search_file_factory):
    search_file = pubmed_search_file_factory("9.9.9")

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        PubMedSearchSource(search_file=search_file)

    assert str(exc_info.value) == "PubMed version should be 1.0.0, found 9.9.9"
