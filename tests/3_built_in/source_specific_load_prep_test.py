#!/usr/bin/env python
"""Test the source_specific prep package"""
import os
import platform
import shutil
from pathlib import Path

import pytest

import colrev.review_manager
import colrev.settings


# pylint: disable=line-too-long

@pytest.fixture(name="ssp_review_manager")
def fixture_ssp_review_manager(  # type: ignore
    session_mocker, tmp_path: Path, helpers
) -> colrev.review_manager.ReviewManager:
    """Fixture returning a review_manager"""
    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    session_mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.register_repo",
        return_value=(),
    )

    # test_repo_dir = tmp_path_factory.mktemp("test_review_example")  # type: ignore
    test_repo_dir = tmp_path
    os.chdir(test_repo_dir)
    print(test_repo_dir)

    rev_man = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    rev_man.settings = colrev.settings.load_settings(
        settings_path=helpers.test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    rev_man.settings.project.title = "topic a - a review"
    colrev.review_manager.get_init_operation(
        review_type="literature_review",
        example=False,
        target_path=test_repo_dir,
        light=True,
    )

    # Note: the strategy is to test the workflow and the endpoints separately
    # We therefore deactivate the (most time consuming endpoints) in the following
    rev_man = colrev.review_manager.ReviewManager(path_str=str(rev_man.path))

    # review_manager.dataset.add_changes(path=Path("data/search/test_records.bib"))
    rev_man.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.source_specific_prep"},
    ]
    rev_man.settings.sources = []

    rev_man.save_settings()
    return rev_man


# To create new test datasets, it is sufficient to extend the pytest.mark.parametrize
# and create the source_filepath in tests/data/built_in_search_sources.
# The first test run will create the expected_file and fail on the first run.
@pytest.mark.parametrize(
    "source_filepath, expected_source_identifier, oni, expected_file",
    [
        # (Path("ais.txt"), "colrev.ais_library", Path("ais_result.bib")),
        # (Path("pubmed.csv"), "colrev.pubmed", Path("pubmed_result.bib")),
        (Path("dblp.bib"), "colrev.dblp", False, Path("dblp_result.bib")),
        (
            Path("europe_pmc.bib"),
            "colrev.europe_pmc",
            False,
            Path("europe_pmc_result.bib"),
        ),
        (Path("acm.bib"), "colrev.acm_digital_library", False, Path("acm_result.bib")),
        # (Path("eric.nbib"), "colrev.eric", Path("eric_result.bib")),
        # (Path("ieee.ris"), "colrev.ieee",True, Path("ieee_result.bib")),
        # (Path("jstor.ris"), "colrev.jstor",False, Path("jstor_result.bib")),
        (
            Path("abi_inform_proquest.bib"),
            "colrev.abi_inform_proquest",
            False,
            Path("abi_inform_proquest_result.bib"),
        ),
        (Path("scopus.bib"), "colrev.scopus", False, Path("scopus_result.bib")),
        # (Path("psycinfo.ris"), "colrev.psycinfo", Path("psycinfo_result.bib")),
        # (Path("springer.csv"), "colrev.springer_link", Path("springer_result.bib")),
        (
            Path("taylor_and_francis.bib"),
            "colrev.taylor_and_francis",
            False,
            Path("taylor_and_francis_result.bib"),
        ),
        # (Path("trid.ris"), "colrev.trid", Path("trid_result.bib")),
        (
            Path("web_of_science.bib"),
            "colrev.web_of_science",
            False,
            Path("web_of_science_result.bib"),
        ),
        (Path("wiley.bib"), "colrev.wiley", False, Path("wiley_result.bib")),
    ],
)
def test_source(  # type: ignore
    source_filepath: Path,
    expected_source_identifier: str,
    expected_file: Path,
    oni: bool,
    ssp_review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    """Test the source_specific prep"""

    print(Path.cwd())  # To facilitate debugging

    helpers.retrieve_test_file(
        source=Path("built_in_search_sources/") / source_filepath,
        target=Path("data/search/") / source_filepath,
    )
    if platform.system() not in ["Linux"]:
        if source_filepath.suffix not in [".bib", ".csv"]:
            return

    # Run load and test the heuristics
    load_operation = ssp_review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources)
    actual_source_identifier = ssp_review_manager.settings.sources[0].endpoint
    if oni:
        ssp_review_manager.settings.sources = [{"endpoint": actual_source_identifier}]  # type: ignore
    else:
        # Note: fail if the heuristics are inadequate/do not create an erroneous expected_file
        assert expected_source_identifier == actual_source_identifier

    prep_operation = ssp_review_manager.get_prep_operation()
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
