#!/usr/bin/env python
"""Test the source_specific prep package"""
import platform
import shutil
from pathlib import Path

import pytest

import colrev.review_manager
import colrev.settings


# pylint: disable=line-too-long
# pylint: disable=too-many-arguments

NO_CUSTOM_SOURCE = None


# To create new test datasets, it is sufficient to extend the pytest.mark.parametrize
# and create the source_filepath in tests/data/built_in_search_sources.
# The first test run will create the expected_file and fail on the first run.
@pytest.mark.parametrize(
    "source_filepath, expected_source_identifier, custom_source, expected_file",
    [
        # (Path("pubmed.csv"), "colrev.pubmed", Path("pubmed_result.bib")),
        # (Path("springer.csv"), "colrev.springer_link", Path("springer_result.bib")),
        # https://pypi.org/project/nbib/
        # (Path("eric.nbib"), "colrev.eric", Path("eric_result.bib")),
        # (
        #     Path("ais.txt"),
        #     "colrev.ais_library",
        #     NO_CUSTOM_SOURCE,
        #     Path("ais_result.bib"),
        # ),
        (Path("dblp.bib"), "colrev.dblp", NO_CUSTOM_SOURCE, Path("dblp_result.bib")),
        (
            Path("europe_pmc.bib"),
            "colrev.europe_pmc",
            NO_CUSTOM_SOURCE,
            Path("europe_pmc_result.bib"),
        ),
        (
            Path("acm.bib"),
            "colrev.acm_digital_library",
            NO_CUSTOM_SOURCE,
            Path("acm_result.bib"),
        ),
        (
            Path("abi_inform_proquest.bib"),
            "colrev.abi_inform_proquest",
            NO_CUSTOM_SOURCE,
            Path("abi_inform_proquest_result.bib"),
        ),
        (
            Path("scopus.bib"),
            "colrev.scopus",
            NO_CUSTOM_SOURCE,
            Path("scopus_result.bib"),
        ),
        (
            Path("taylor_and_francis.bib"),
            "colrev.taylor_and_francis",
            NO_CUSTOM_SOURCE,
            Path("taylor_and_francis_result.bib"),
        ),
        (
            Path("web_of_science.bib"),
            "colrev.web_of_science",
            NO_CUSTOM_SOURCE,
            Path("web_of_science_result.bib"),
        ),
        (Path("wiley.bib"), "colrev.wiley", NO_CUSTOM_SOURCE, Path("wiley_result.bib")),
        (
            Path("pdfs_dir.bib"),
            "colrev.pdfs_dir",
            colrev.settings.SearchSource(
                endpoint="colrev.pdfs_dir",
                filename=Path("data/search/pdfs_dir.bib"),
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={"scope": {"path": "test"}},
                load_conversion_package_endpoint={"endpoint": ""},
                comment="",
            ),
            Path("pdfs_dir_result.bib"),
        ),
        (
            Path("ieee.ris"),
            "colrev.ieee",
            colrev.settings.SearchSource(
                endpoint="colrev.ieee",
                filename=Path("data/search/ieee.bib"),
                search_type=colrev.settings.SearchType.OTHER,
                search_parameters={"scope": {"path": "test"}},
                load_conversion_package_endpoint={"endpoint": ""},
                comment="",
            ),
            Path("ieee_result.bib"),
        ),
        (Path("jstor.ris"), "colrev.jstor", NO_CUSTOM_SOURCE, Path("jstor_result.bib")),
        (Path("trid.ris"), "colrev.trid", NO_CUSTOM_SOURCE, Path("trid_result.bib")),
        (
            Path("psycinfo.ris"),
            "colrev.psycinfo",
            NO_CUSTOM_SOURCE,
            Path("psycinfo_result.bib"),
        ),
    ],
)
def test_source(  # type: ignore
    source_filepath: Path,
    expected_source_identifier: str,
    expected_file: Path,
    custom_source: colrev.settings.SearchSource,
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the source_specific prep"""

    helpers.reset_commit(
        review_manager=base_repo_review_manager, commit="changed_settings_commit"
    )

    print(Path.cwd())  # To facilitate debugging

    helpers.retrieve_test_file(
        source=Path("built_in_search_sources/") / source_filepath,
        target=Path("data/search/") / source_filepath,
    )
    if platform.system() not in ["Linux"]:
        if source_filepath.suffix not in [".bib", ".ris", ".csv"]:
            return

    base_repo_review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.source_specific_prep"},
    ]
    base_repo_review_manager.settings.prep.defects_to_ignore = [
        "inconsistent-with-url-metadata",
        "inconsistent-with-doi-metadata",
    ]
    base_repo_review_manager.settings.sources = []

    base_repo_review_manager.save_settings()

    # Run load and test the heuristics
    load_operation = base_repo_review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    if source_filepath.suffix == ".ris" or source_filepath == "ais.txt":
        new_sources[0].load_conversion_package_endpoint = {"endpoint": "colrev.rispy"}
    load_operation.main(new_sources=new_sources)
    if custom_source:
        base_repo_review_manager.settings.sources = [custom_source]
    actual_source_identifier = base_repo_review_manager.settings.sources[0].endpoint
    # Note: fail if the heuristics are inadequate/do not create an erroneous expected_file
    assert expected_source_identifier == actual_source_identifier

    prep_operation = base_repo_review_manager.get_prep_operation()
    prep_operation.main()

    # Test whether the load(fixes) and source-specific prep work as expected
    actual = Path("data/records.bib").read_text(encoding="utf-8")
    try:
        expected = (
            helpers.test_data_path / Path("built_in_search_sources/") / expected_file
        ).read_text(encoding="utf-8")

    except FileNotFoundError as exc:
        # If mismatch: copy the actual file to replace the expected file (facilitating updates)
        shutil.copy(
            Path("data/records.bib"),
            helpers.test_data_path / Path("built_in_search_sources/") / expected_file,
        )
        raise Exception(
            f"The expected_file ({expected_file.name}) was not (yet) available. "
            f"An initial version was created in {expected_file}. "
            "Please check, update, and add/commit it. Afterwards, rerun the tests."
        ) from exc

    if expected != actual:
        shutil.copy(
            Path("data/records.bib"),
            helpers.test_data_path / Path("built_in_search_sources/") / expected_file,
        )
    assert expected == actual
