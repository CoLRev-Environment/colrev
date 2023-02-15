#!/usr/bin/env python
import os
import shutil
from pathlib import Path

from distutils import dir_util
from pytest import fixture

import colrev.review_manager


@fixture
def datadir(tmp_path: Path, request) -> Path:  # type: ignore

    colrev.review_manager.ReviewManager.get_init_operation(
        review_type="literature_review",
        example=False,
        local_pdf_collection=False,
        target_path=tmp_path,
    )

    filename = request.module.__file__
    test_dir, _ = os.path.splitext(filename)

    if os.path.isdir(test_dir):
        dir_util.copy_tree(test_dir, str(tmp_path))

    return tmp_path


def test_prep(tmp_path: Path, datadir) -> None:  # type: ignore
    # use the directory tmp_path

    os.chdir(tmp_path)

    input_records_path = datadir / Path("input_records.bib")
    expected_records_path = datadir / Path("expected_records.bib")

    main_records_path = tmp_path / Path("data/records.bib")
    shutil.copy(input_records_path, main_records_path)

    review_manager = colrev.review_manager.ReviewManager(
        force_mode=True, path_str=str(tmp_path)
    )

    ais_source = colrev.settings.SearchSource(
        endpoint="colrev_built_in.ais_library",
        filename=Path("data/search/search_results-refer.enl"),
        search_type=colrev.settings.SearchType.DB,
        search_parameters={},
        load_conversion_package_endpoint={"endpoint": "colrev_built_in.bibutils"},
        comment="",
    )
    review_manager.settings.sources.append(ais_source)
    review_manager.save_settings()

    prep_operation = review_manager.get_prep_operation(
        notify_state_transition_operation=False, retrieval_similarity=0.8
    )

    assert review_manager.dataset

    prep_operation.main(keep_ids=True)
    expected_records = review_manager.dataset.load_records_dict(
        file_path=expected_records_path
    )

    records = review_manager.dataset.load_records_dict()

    assert set(expected_records.keys()) == set(records.keys())

    # Note : to catch errors in manual creation of test cases:
    # TODO : the same for the input records (should be md_imported)
    for record in expected_records.values():
        assert record["colrev_status"] in [
            colrev.record.RecordState.md_imported,
            colrev.record.RecordState.md_prepared,
            colrev.record.RecordState.md_needs_manual_preparation,
            colrev.record.RecordState.rev_prescreen_excluded,
        ]

    # assert for each record (for better error reporting)
    for expected_record in expected_records.values():
        try:
            prepared_record_dict = records[expected_record["ID"]]
            for time_variant_field in colrev.record.Record.time_variant_fields:
                if time_variant_field in prepared_record_dict:
                    prepared_record = colrev.record.Record(data=prepared_record_dict)
                    prepared_record.remove_field(key=time_variant_field)
            assert expected_record == prepared_record_dict
        except AssertionError as exc:
            expected_records_path = Path(colrev.__file__).parent.parent / Path(
                "tests/prep_test/expected_records.bib"
            )
            review_manager.dataset.save_records_dict_to_file(
                records=records, save_path=expected_records_path
            )
            print("Replaced the tests/prep_test/expected_records.bib.")
            print("Discard changes or add them to update the expected values.")
            print(tmp_path)
            raise AssertionError from exc

    print(review_manager.path)
