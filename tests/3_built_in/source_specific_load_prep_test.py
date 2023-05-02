#!/usr/bin/env python
import shutil
from pathlib import Path

import pytest

import colrev.review_manager
import colrev.settings

actual_file = Path("data/records.bib")


@pytest.fixture
def ssp_review_manager(base_repo_review_manager) -> colrev.review_manager.ReviewManager:  # type: ignore
    # select the colrev.source_specific_prep exclusively
    base_repo_review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.source_specific_prep"},
    ]
    base_repo_review_manager.settings.sources = []
    base_repo_review_manager.save_settings()
    return base_repo_review_manager


# To create new test datasets, it is sufficient to extend the pytest.mark.parametrize
# and create the source_filepath in tests/data/built_in_search_sources.
# The first test run will create the expected_file and fail on the first run.
@pytest.mark.parametrize(
    "source_filepath, expected_source_identifier, expected_file",
    [
        # (Path("ais.txt"), "colrev.ais_library", Path("ais_result.bib")),
        # (Path("pubmed.csv"), "colrev.pubmed", Path("pubmed_result.bib")),
        # (Path("dblp.bib"), "colrev.dblp", Path("dblp_result.bib")),
        # (Path("europe_pmc.bib"), "colrev.europe_pmc", Path("europe_pmc_result.bib")),
        # (Path("acm.bib"), "colrev.acm_digital_library", Path("acm_result.bib")),
        # (Path("eric.nbib"), "colrev.eric", Path("eric_result.bib")),
        # (Path("ieee.ris"), "colrev.ieee", Path("ieee_result.bib")),
        # (Path("jstor.ris"), "colrev.jstor", Path("jstor_result.bib")),
        # (Path("psycinfo.ris"), "colrev.psycinfo", Path("psycinfo_result.bib")),
        # (Path("springer.csv"), "colrev.springer_link", Path("springer_result.bib")),
        # (
        #     Path("taylor_and_francis.ris"),
        #     "colrev.taylor_and_francis",
        #     Path("taylor_and_francis_result.bib"),
        # ),
        # (Path("trid.ris"), "colrev.trid", Path("trid_result.bib")),
        # (
        #     Path("web_of_science.bib"),
        #     "colrev.web_of_science",
        #     Path("web_of_science_result.bib"),
        # ),
        # (Path("wiley.bib"), "colrev.wiley", Path("wiley_result.bib")),
    ],
)
def test_source(  # type: ignore
    source_filepath: Path,
    expected_source_identifier: str,
    expected_file: Path,
    ssp_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    print(Path.cwd())  # To facilitate debugging

    expected_file = (
        helpers.test_data_path / Path("built_in_search_sources") / expected_file
    )
    helpers.retrieve_test_file(
        source=Path("built_in_search_sources/") / source_filepath,
        target=Path("data/search/") / source_filepath,
    )

    # Run load and test the heuristics
    load_operation = ssp_review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources)
    actual_source_identifier = ssp_review_manager.settings.sources[0].endpoint
    # Note: fail if the heuristics are inadequate/do not create an erroneous expected_file
    assert expected_source_identifier == actual_source_identifier

    # Run prep nad test source-specific prep
    prep_operation = ssp_review_manager.get_prep_operation()
    prep_operation.main()

    if not expected_file.is_file():
        shutil.copy(actual_file, expected_file)
        raise Exception(
            f"The expected_file ({expected_file.name}) was not (yet) available. "
            f"An initial version was created in {expected_file}. "
            "Please check, update, and add/commit it. Afterwards, rerun the tests."
        )

    # Test whether the load(fixes) and source-specific prep work as expected
    actual = actual_file.read_text()
    expected = expected_file.read_text()

    # If mismatch: copy the actual file to replace the expected file (facilitating updates)
    if expected != actual:
        shutil.copy(actual_file, expected_file)

    assert expected == actual
