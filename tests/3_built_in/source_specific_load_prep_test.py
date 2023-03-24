#!/usr/bin/env python
import os
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.review_manager
import colrev.settings

# Note : the following produces different relative paths locally/on github.
# Path(colrev.__file__).parents[1]

test_data_path = Path()


def retrieve_test_file(*, source: Path, target: Path) -> None:
    target.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(
        test_data_path / source,
        target,
    )


# @pytest.fixture(scope="module")
@pytest.fixture
def review_manager(session_mocker, tmp_path: Path, request) -> colrev.review_manager.ReviewManager:  # type: ignore
    global test_data_path
    test_data_path = Path(request.fspath).parents[1] / Path("data")

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

    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(test_repo_dir), force_mode=True
    )
    review_manager.settings = colrev.settings.load_settings(
        settings_path=test_data_path.parents[1]
        / Path("colrev/template/init/settings.json")
    )

    review_manager.settings.project.title = "topic a - a review"
    review_manager.get_init_operation(
        review_type="literature_review",
        example=False,
        target_path=test_repo_dir,
        light=True,
    )

    # Note: the strategy is to test the workflow and the endpoints separately
    # We therefore deactivate the (most time consuming endpoints) in the following
    review_manager = colrev.review_manager.ReviewManager(
        path_str=str(review_manager.path)
    )

    # review_manager.dataset.add_changes(path=Path("data/search/test_records.bib"))
    review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev.source_specific_prep"},
    ]
    review_manager.settings.sources = []

    review_manager.save_settings()
    return review_manager


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
def test_source(
    source_filepath: Path,
    expected_source_identifier: str,
    expected_file: Path,
    review_manager: colrev.review_manager.ReviewManager,
) -> None:
    retrieve_test_file(
        source=Path("built_in_search_sources/") / source_filepath,
        target=Path("data/search/") / source_filepath,
    )

    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources)
    actual_source_identifier = review_manager.settings.sources[0].endpoint

    # This tests the heuristics
    assert expected_source_identifier == actual_source_identifier

    prep_operation = review_manager.get_prep_operation()
    prep_operation.main()

    # Test whether the load(fixes) and source-specific prep work as expected
    actual = Path("data/records.bib").read_text()
    expected = (
        test_data_path / Path("built_in_search_sources/") / expected_file
    ).read_text()

    # If mismatch: copy the actual file to replace the expected file (facilitating updates)
    if expected != actual:
        print(Path.cwd())
        shutil.copy(
            Path("data/records.bib"),
            test_data_path / Path("built_in_search_sources/") / expected_file,
        )

    assert expected == actual
