#!/usr/bin/env python
import os
import platform
import shutil
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.review_manager
import colrev.settings

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]


# @pytest.fixture(scope="module")
@pytest.fixture
def review_manager(session_mocker, tmp_path: Path, helpers) -> colrev.review_manager.ReviewManager:  # type: ignore
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


# To create new test datasets, it is sufficient to
# create the source_filepath and an empty expected_file
# running the test will update the expected_file
@pytest.mark.parametrize(
    "source_filepath, expected_source_identifier, expected_file",
    [
        (Path("ais.txt"), "colrev.ais_library", Path("ais_result.bib")),
        (Path("pubmed.csv"), "colrev.pubmed", Path("pubmed_result.bib")),
        (Path("dblp.bib"), "colrev.dblp", Path("dblp_result.bib")),
    ],
)
def test_source(  # type: ignore
    source_filepath: Path,
    expected_source_identifier: str,
    expected_file: Path,
    review_manager: colrev.review_manager.ReviewManager,
    helpers,
) -> None:
    helpers.retrieve_test_file(
        source=Path("built_in_search_sources/") / source_filepath,
        target=Path("data/search/") / source_filepath,
    )
    if platform.system() not in ["Linux"]:
        if source_filepath.suffix not in [".bib", ".csv"]:
            return

    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources)
    actual_source_identifier = review_manager.settings.sources[0].endpoint

    # This tests the heuristics
    assert expected_source_identifier == actual_source_identifier

    prep_operation = review_manager.get_prep_operation()
    prep_operation.main()

    # Test whether the load(fixes) and source-specific prep work as expected
    actual = Path("data/records.bib").read_text(encoding="utf-8")
    expected = (
        helpers.test_data_path / Path("built_in_search_sources/") / expected_file
    ).read_text()

    # If mismatch: copy the actual file to replace the expected file (facilitating updates)
    if expected != actual:
        print(Path.cwd())
        shutil.copy(
            Path("data/records.bib"),
            helpers.test_data_path / Path("built_in_search_sources/") / expected_file,
        )

    assert expected == actual
