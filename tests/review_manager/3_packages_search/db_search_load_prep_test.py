#!/usr/bin/env python
"""Test the source_specific prep package"""
import shutil
from pathlib import Path

import pytest

import colrev.review_manager
import colrev.search_file
from colrev.constants import SearchType

# pylint: disable=line-too-long
# pylint: disable=too-many-arguments

NO_CUSTOM_SOURCE = None


# To create new test datasets, it is sufficient to extend the pytest.mark.parametrize
# and create the search_results_path in tests/data/built_in_search_sources.
# The first test run will create the expected_file and fail on the first run.
# To test an individual case, run:
# pytest tests/3_built_in/source_specific_load_prep_test.py -vv -k crossref
@pytest.mark.parametrize(
    "search_results_path, expected_source_identifier, custom_source, expected_file",
    [
        (
            Path("google_scholar.json"),
            "colrev.google_scholar",
            NO_CUSTOM_SOURCE,
            Path("google_scholar_result.bib"),
        ),
        (
            Path("eric_nbib.nbib"),
            "colrev.eric",
            NO_CUSTOM_SOURCE,
            Path("eric_nbib_result.bib"),
        ),
        (
            Path("ais_enl.txt"),
            "colrev.ais_library",
            NO_CUSTOM_SOURCE,
            Path("ais_enl_result.bib"),
        ),
        (
            Path("crossref_bib.bib"),
            "colrev.crossref",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.crossref",
                search_results_path=Path("data/search/crossref_bib.bib"),
                search_type=SearchType.API,
                search_string="",
                search_parameters={
                    "url": "https://api.crossref.org/works?query.bibliographic=test",
                },
                comment="",
                version="0.1.0",
            ),
            Path("crossref_bib_result.bib"),
        ),
        (
            Path("pubmed_csv.csv"),
            "colrev.pubmed",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.pubmed",
                search_results_path=Path("data/search/pubmed_csv.csv"),
                search_type=SearchType.DB,
                search_string="digital[ti]",
                comment="",
                version="0.1.0",
            ),
            Path("pubmed_csv_result.bib"),
        ),
        (
            Path("springer_csv.csv"),
            "colrev.springer_link",
            NO_CUSTOM_SOURCE,
            Path("springer_csv_result.bib"),
        ),
        (
            Path("ebsco_bib.bib"),
            "colrev.ebsco_host",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.ebsco_host",
                search_results_path=Path("data/search/ebsco_bib.bib"),
                search_type=SearchType.DB,
                search_string="TI digital",
                comment="",
                version="0.1.0",
            ),
            Path("ebsco_bib_result.bib"),
        ),
        (
            Path("dblp_bib.bib"),
            "colrev.dblp",
            NO_CUSTOM_SOURCE,
            Path("dblp_bib_result.bib"),
        ),
        (
            Path("europe_pmc_bib.bib"),
            "colrev.europe_pmc",
            NO_CUSTOM_SOURCE,
            Path("europe_pmc_bib_result.bib"),
        ),
        (
            Path("acm_bib.bib"),
            "colrev.acm_digital_library",
            NO_CUSTOM_SOURCE,
            Path("acm_bib_result.bib"),
        ),
        (
            Path("abi_inform_proquest_bib.bib"),
            "colrev.abi_inform_proquest",
            NO_CUSTOM_SOURCE,
            Path("abi_inform_proquest_bib_result.bib"),
        ),
        (
            Path("abi_inform_proquest_ris.ris"),
            "colrev.abi_inform_proquest",
            NO_CUSTOM_SOURCE,
            Path("abi_inform_proquest_ris_result.bib"),
        ),
        (
            Path("scopus_bib.bib"),
            "colrev.scopus",
            NO_CUSTOM_SOURCE,
            Path("scopus_bib_result.bib"),
        ),
        (
            Path("taylor_and_francis_bib.bib"),
            "colrev.taylor_and_francis",
            NO_CUSTOM_SOURCE,
            Path("taylor_and_francis_bib_result.bib"),
        ),
        (
            Path("web_of_science_bib.bib"),
            "colrev.web_of_science",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.web_of_science",
                search_results_path=Path("data/search/web_of_science_bib.bib"),
                search_type=SearchType.DB,
                search_string="TI=digital",
                comment="",
                version="0.1.0",
            ),
            Path("web_of_science_bib_result.bib"),
        ),
        (
            Path("wiley_bib.bib"),
            "colrev.wiley",
            NO_CUSTOM_SOURCE,
            Path("wiley_bib_result.bib"),
        ),
        (
            Path("files_dir_bib.bib"),
            "colrev.files_dir",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.files_dir",
                search_results_path=Path("data/search/files_dir_bib.bib"),
                search_type=SearchType.FILES,
                search_string="",
                search_parameters={"scope": {"path": "test"}},
                comment="",
                version="0.1.0" "",
            ),
            Path("files_dir_bib_result.bib"),
        ),
        (
            Path("ieee_ris.ris"),
            "colrev.ieee",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.ieee",
                search_results_path=Path("data/search/ieee_ris.ris"),
                search_type=SearchType.DB,
                search_string="",
                comment="",
                version="0.1.0",
            ),
            Path("ieee_ris_result.bib"),
        ),
        (
            Path("ieee_csv.csv"),
            "colrev.ieee",
            colrev.search_file.ExtendedSearchFile(
                platform="colrev.ieee",
                search_results_path=Path("data/search/ieee_csv.csv"),
                search_type=SearchType.DB,
                search_string="",
                comment="",
                version="0.1.0",
            ),
            Path("ieee_csv_result.bib"),
        ),
        (
            Path("jstor_ris.ris"),
            "colrev.jstor",
            NO_CUSTOM_SOURCE,
            Path("jstor_ris_result.bib"),
        ),
        (
            Path("trid_ris.ris"),
            "colrev.trid",
            NO_CUSTOM_SOURCE,
            Path("trid_ris_result.bib"),
        ),
        (
            Path("psycinfo_ris.ris"),
            "colrev.psycinfo",
            NO_CUSTOM_SOURCE,
            Path("psycinfo_ris_result.bib"),
        ),
        (
            Path("unknown_source_bib.bib"),
            "colrev.unknown_source",
            NO_CUSTOM_SOURCE,
            Path("unknown_source_bib_result.bib"),
        ),
    ],
)
def test_source(  # type: ignore
    search_results_path: Path,
    expected_source_identifier: str,
    custom_source: colrev.search_file.ExtendedSearchFile,
    expected_file: Path,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
    helpers,
) -> None:
    """Test the source_specific prep"""

    if custom_source is not None:
        assert (
            custom_source.search_results_path
            == Path("data/search") / search_results_path
        )

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="changed_settings_commit"
    )

    print(Path.cwd())  # To facilitate debugging

    helpers.retrieve_test_file(
        source=Path("review_manager/3_packages_search/data/") / search_results_path,
        target=Path("data/search/") / search_results_path,
    )

    base_repo_review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.source_specific_prep"},
    ]
    base_repo_review_manager.settings.prep.defects_to_ignore = [
        "inconsistent-with-url-metadata",
        "inconsistent-with-doi-metadata",
        "language-unknown",
    ]
    base_repo_review_manager.settings.sources = []

    # Run search and load and test the heuristics

    if custom_source:
        base_repo_review_manager.settings.sources = [custom_source]
    else:
        search_operation = base_repo_review_manager.get_search_operation()
        search_operation.add_most_likely_sources()

    base_repo_review_manager.save_settings()

    base_repo_review_manager.dataset.git_repo.repo.git.add(A=True)
    base_repo_review_manager.create_commit(msg="add search files")

    load_operation = base_repo_review_manager.get_load_operation()
    load_operation.main()

    actual_source_identifier = base_repo_review_manager.settings.sources[0].platform
    # Note: fail if the heuristics are inadequate/do not create an erroneous expected_file
    assert expected_source_identifier == actual_source_identifier

    prep_operation = base_repo_review_manager.get_prep_operation()
    prep_operation.main()

    # Test whether the load(fixes) and source-specific prep work as expected
    actual = Path("data/records.bib").read_text(encoding="utf-8")
    try:
        expected = (
            helpers.test_data_path
            / Path("review_manager/3_packages_search/data/")
            / expected_file
        ).read_text(encoding="utf-8")

    except FileNotFoundError as exc:
        # If mismatch: copy the actual file to replace the expected file (facilitating updates)
        shutil.copy(
            Path("data/records.bib"),
            helpers.test_data_path
            / Path("review_manager/3_packages_search/data/")
            / expected_file,
        )
        raise Exception(
            f"The expected_file ({expected_file.name}) was not (yet) available. "
            f"An initial version was created in {expected_file}. "
            "Please check, update, and add/commit it. Afterwards, rerun the tests."
        ) from exc

    if expected != actual:
        shutil.copy(
            Path("data/records.bib"),
            helpers.test_data_path
            / Path("review_manager/3_packages_search/data/")
            / expected_file,
        )
    assert expected == actual
