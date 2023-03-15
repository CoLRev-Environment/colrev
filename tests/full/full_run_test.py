#!/usr/bin/env python
import os
import shutil
import typing
from pathlib import Path

import pytest
from pybtex.database.input import bibtex

import colrev.env.utils
import colrev.review_manager


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


def test_full_run(tmp_path: Path, mocker, script_loc) -> None:  # type: ignore
    os.chdir(tmp_path)

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Tester Name", "tester@email.de"),
    )

    def load_test_records(script_loc) -> dict:  # type: ignore
        # local_index_bib_path = script_loc.joinpath("local_index.bib")

        test_records_dict: typing.Dict[Path, dict] = {}
        bib_files_to_index = Path(script_loc) / Path("local_index")
        for file_path in bib_files_to_index.glob("**/*"):
            test_records_dict[Path(file_path.name)] = {}

        for path in test_records_dict.keys():
            with open(bib_files_to_index.joinpath(path), encoding="utf-8") as file:
                parser = bibtex.Parser()
                bib_data = parser.parse_string(file.read())
                test_records_dict[path] = colrev.dataset.Dataset.parse_records_dict(
                    records_dict=bib_data.entries
                )
        return test_records_dict

    temp_sqlite = tmp_path / Path("sqlite_index_test.db")
    print(temp_sqlite)
    with mocker.patch.object(
        colrev.env.local_index.LocalIndex, "SQLITE_PATH", temp_sqlite
    ):
        test_records_dict = load_test_records(script_loc)
        local_index = colrev.env.local_index.LocalIndex(verbose_mode=True)
        local_index.reinitialize_sqlite_db()

        for path, records in test_records_dict.items():
            if "cura" in str(path):
                continue
            local_index.index_records(
                records=records,
                repo_source_path=path,
                curated_fields=[],
                curation_url="gh...",
                curated_masterdata=True,
            )

        for path, records in test_records_dict.items():
            if "cura" not in str(path):
                continue
            local_index.index_records(
                records=records,
                repo_source_path=path,
                curated_fields=["literature_review"],
                curation_url="gh...",
                curated_masterdata=False,
            )

    for filename in os.listdir(tmp_path):
        file_path = os.path.join(tmp_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f"Failed to delete {file_path}. Reason: {e}")

    colrev.review_manager.ReviewManager.get_init_operation(
        review_type="literature_review",
        example=False,
    )

    # Note: the strategy is to test the workflow and the endpoints separately
    # We therefore deactivate the (most time consuming endpoints) in the following
    review_manager = colrev.review_manager.ReviewManager()
    colrev.env.utils.retrieve_package_file(
        template_file=Path("template/example/test_records.bib"),
        target=Path("data/search/test_records.bib"),
    )
    review_manager.dataset.add_changes(path=Path("data/search/test_records.bib"))
    review_manager.settings.prep.prep_rounds[0].prep_package_endpoints = [
        {"endpoint": "colrev_built_in.resolve_crossrefs"},
        {"endpoint": "colrev_built_in.source_specific_prep"},
        {"endpoint": "colrev_built_in.exclude_non_latin_alphabets"},
        {"endpoint": "colrev_built_in.exclude_collections"},
    ]
    review_manager.settings.dedupe.dedupe_package_endpoints = [
        {"endpoint": "colrev_built_in.simple_dedupe"}
    ]

    review_manager.settings.pdf_get.pdf_get_package_endpoints = [
        {"endpoint": "colrev_built_in.local_index"}
    ]
    review_manager.settings.pdf_prep.pdf_prep_package_endpoints = []
    review_manager.settings.data.data_package_endpoints = []
    review_manager.save_settings()

    review_manager.logger.info("Start load")
    load_operation = review_manager.get_load_operation()

    load_operation = review_manager.get_load_operation()
    new_sources = load_operation.get_new_sources(skip_query=True)
    load_operation.main(new_sources=new_sources, keep_ids=False, combine_commits=False)

    review_manager.logger.info("Start prep")
    review_manager = colrev.review_manager.ReviewManager()
    prep_operation = review_manager.get_prep_operation()
    prep_operation.main(keep_ids=False)

    search_operation = review_manager.get_search_operation()
    search_operation.main(rerun=True)

    review_manager.logger.info("Start dedupe")
    review_manager = colrev.review_manager.ReviewManager()
    dedupe_operation = review_manager.get_dedupe_operation(
        notify_state_transition_operation=True
    )
    dedupe_operation.main()

    review_manager.logger.info("Start prescreen")
    review_manager = colrev.review_manager.ReviewManager()
    prescreen_operation = review_manager.get_prescreen_operation()
    prescreen_operation.include_all_in_prescreen(persist=False)

    review_manager.logger.info("Start pdf-get")
    review_manager = colrev.review_manager.ReviewManager()
    pdf_get_operation = review_manager.get_pdf_get_operation(
        notify_state_transition_operation=True
    )
    pdf_get_operation.main()

    review_manager.logger.info("Start pdf-prep")
    review_manager = colrev.review_manager.ReviewManager()
    pdf_prep_operation = review_manager.get_pdf_prep_operation(reprocess=False)
    pdf_prep_operation.main(batch_size=0)

    review_manager.logger.info("Start pdfs discard")
    review_manager = colrev.review_manager.ReviewManager()
    pdf_get_man_operation = review_manager.get_pdf_get_man_operation()
    pdf_get_man_operation.discard()

    review_manager = colrev.review_manager.ReviewManager()
    pdf_prep_man_operation = review_manager.get_pdf_prep_man_operation()
    pdf_prep_man_operation.discard()

    review_manager.logger.info("Start screen")
    review_manager = colrev.review_manager.ReviewManager()
    screen_operation = review_manager.get_screen_operation()
    screen_operation.include_all_in_screen(persist=False)

    review_manager.logger.info("Start pdfs data")
    review_manager = colrev.review_manager.ReviewManager()
    data_operation = review_manager.get_data_operation()
    data_operation.main()
    review_manager.create_commit(msg="Data and synthesis", manual_author=True)

    print(tmp_path)

    # assert False
