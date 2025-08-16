#!/usr/bin/env python
"""Tests for the status stats"""
import colrev.process.status
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.constants import ScreenCriterionType

# flake8: noqa: E501


def compare(
    expected_stats: colrev.process.status.StatusStats,
    given_stats: colrev.process.status.StatusStats,
) -> None:

    expected = expected_stats.model_dump()
    given = given_stats.model_dump()
    assert expected == given


def test_check_status_stats_attributes(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:

    print(f"{Colors.RED}{base_repo_review_manager.path}{Colors.END}")

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="changed_settings_commit"
    )
    expected_stats = base_repo_review_manager.get_status_stats()

    assert expected_stats.atomic_steps == 0
    assert expected_stats.nr_curated_records == 0
    assert expected_stats.md_duplicates_removed == 0
    assert expected_stats.currently.md_retrieved == 0
    assert expected_stats.currently.md_imported == 0
    assert expected_stats.currently.md_prepared == 0
    assert expected_stats.currently.md_needs_manual_preparation == 0
    assert expected_stats.currently.md_processed == 0
    assert expected_stats.currently.rev_prescreen_excluded == 0
    assert expected_stats.currently.rev_prescreen_included == 0
    assert expected_stats.currently.pdf_needs_manual_retrieval == 0
    assert expected_stats.currently.pdf_not_available == 0
    assert expected_stats.currently.pdf_imported == 0
    assert expected_stats.currently.pdf_needs_manual_preparation == 0
    assert expected_stats.currently.pdf_prepared == 0
    assert expected_stats.currently.rev_excluded == 0
    assert expected_stats.currently.rev_included == 0
    assert expected_stats.currently.rev_synthesized == 0
    assert expected_stats.currently.pdf_needs_retrieval == 0
    assert expected_stats.currently.non_completed == 0
    assert expected_stats.currently.exclusion == {}
    assert expected_stats.overall.md_retrieved == 0
    assert expected_stats.overall.md_imported == 0
    assert expected_stats.overall.md_prepared == 0
    assert expected_stats.overall.md_processed == 0
    assert expected_stats.overall.rev_prescreen_excluded == 0
    assert expected_stats.overall.rev_prescreen_included == 0
    assert expected_stats.overall.pdf_not_available == 0
    assert expected_stats.overall.pdf_imported == 0
    assert expected_stats.overall.pdf_prepared == 0
    assert expected_stats.overall.rev_excluded == 0
    assert expected_stats.overall.rev_included == 0
    assert expected_stats.overall.rev_synthesized == 0
    assert expected_stats.completed_atomic_steps == 0
    assert expected_stats.completeness_condition

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="load_commit")
    given_stats = base_repo_review_manager.get_status_stats()
    expected_stats.atomic_steps = 9  # Note: overall / does not change
    expected_stats.completed_atomic_steps = 2
    expected_stats.nr_incomplete = 1
    expected_stats.nr_origins = 1
    expected_stats.origin_states_dict = {
        "test_records.bib/Srivastava2015": RecordState.md_imported
    }
    expected_stats.currently.md_imported = 1
    expected_stats.currently.non_completed = 1
    expected_stats.overall.md_imported = 1
    expected_stats.overall.md_retrieved = 1
    expected_stats.completeness_condition = False
    compare(expected_stats, given_stats)
    assert "1 to prepare" == given_stats.get_active_metadata_operation_info()
    assert "" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.prep] == given_stats.get_priority_operations()
    assert [OperationsType.prep] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="prep_commit")
    given_stats = base_repo_review_manager.get_status_stats()
    expected_stats.completed_atomic_steps = 3
    expected_stats.currently.md_imported = 0
    expected_stats.currently.md_prepared = 1
    expected_stats.overall.md_prepared = 1
    expected_stats.origin_states_dict = {
        "test_records.bib/Srivastava2015": RecordState.md_prepared
    }
    compare(expected_stats, given_stats)
    assert "1 to deduplicate" == given_stats.get_active_metadata_operation_info()
    assert "" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.dedupe] == given_stats.get_priority_operations()
    assert [OperationsType.dedupe] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="dedupe_commit"
    )
    given_stats = base_repo_review_manager.get_status_stats()
    expected_stats.completed_atomic_steps = 4
    expected_stats.currently.md_prepared = 0
    expected_stats.currently.md_processed = 1
    expected_stats.overall.md_processed = 1
    expected_stats.overall.rev_prescreen = 1
    expected_stats.origin_states_dict = {
        "test_records.bib/Srivastava2015": RecordState.md_processed
    }
    compare(expected_stats, given_stats)
    assert "" == given_stats.get_active_metadata_operation_info()
    assert "" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.prescreen] == given_stats.get_priority_operations()
    assert [OperationsType.prescreen] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="prescreen_commit"
    )
    given_stats = base_repo_review_manager.get_status_stats()
    expected_stats.completed_atomic_steps = 5
    expected_stats.currently.md_processed = 0
    expected_stats.currently.rev_prescreen_included = 1
    expected_stats.currently.pdf_needs_retrieval = 1
    expected_stats.overall.rev_prescreen_included = 1
    expected_stats.overall.rev_prescreen = 1
    expected_stats.origin_states_dict = {
        "test_records.bib/Srivastava2015": RecordState.rev_prescreen_included
    }
    compare(expected_stats, given_stats)
    assert "" == given_stats.get_active_metadata_operation_info()
    assert "1 to retrieve" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.pdf_get] == given_stats.get_priority_operations()
    assert [OperationsType.pdf_get] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_get_commit"
    )
    given_stats = base_repo_review_manager.get_status_stats()
    expected_stats.completed_atomic_steps = 5
    expected_stats.currently.pdf_needs_retrieval = 0
    expected_stats.currently.pdf_needs_manual_retrieval = 1
    expected_stats.currently.rev_prescreen_included = 0
    expected_stats.origin_states_dict = {
        "test_records.bib/Srivastava2015": RecordState.pdf_needs_manual_retrieval
    }
    compare(expected_stats, given_stats)
    assert "" == given_stats.get_active_metadata_operation_info()
    assert "1 to retrieve manually" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.pdf_get_man] == given_stats.get_priority_operations()
    assert [OperationsType.pdf_get_man] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="pdf_prep_commit"
    )
    given_stats = base_repo_review_manager.get_status_stats()
    compare(expected_stats, given_stats)
    assert "" == given_stats.get_active_metadata_operation_info()
    assert "1 to retrieve manually" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.pdf_get_man] == given_stats.get_priority_operations()
    assert [OperationsType.pdf_get_man] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(
        base_repo_review_manager, commit="screen_commit"
    )
    given_stats = base_repo_review_manager.get_status_stats()
    compare(expected_stats, given_stats)
    assert "" == given_stats.get_active_metadata_operation_info()
    assert "1 to retrieve manually" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.pdf_get_man] == given_stats.get_priority_operations()
    assert [OperationsType.pdf_get_man] == given_stats.get_active_operations()

    review_manager_helpers.reset_commit(base_repo_review_manager, commit="data_commit")
    given_stats = base_repo_review_manager.get_status_stats()
    compare(expected_stats, given_stats)
    assert "" == given_stats.get_active_metadata_operation_info()
    assert "1 to retrieve manually" == given_stats.get_active_pdf_operation_info()
    assert [OperationsType.pdf_get_man] == given_stats.get_priority_operations()
    assert [OperationsType.pdf_get_man] == given_stats.get_active_operations()

    # test screening statistics
    review_manager_helpers.reset_commit(base_repo_review_manager, commit="data_commit")
    records = base_repo_review_manager.dataset.load_records_dict()
    record_dict = records["SrivastavaShainesh2015"]
    screening_criteria_list = ["bc_1", "bc_2"]
    record_dict.update(
        screening_criteria=";".join([e + "=out" for e in screening_criteria_list])
    )
    record_dict.update(colrev_status=RecordState.rev_excluded)
    base_repo_review_manager.dataset.save_records_dict(records)
    base_repo_review_manager.settings.screen.criteria = {
        "bc_1": colrev.settings.ScreenCriterion(
            explanation="Explanation of bc_1",
            comment="",
            criterion_type=ScreenCriterionType.inclusion_criterion,
        ),
        "bc_2": colrev.settings.ScreenCriterion(
            explanation="Explanation of bc_2",
            comment="",
            criterion_type=ScreenCriterionType.inclusion_criterion,
        ),
    }
    base_repo_review_manager.save_settings()
    given_stats = base_repo_review_manager.get_status_stats()
    assert {"bc_1": 1, "bc_2": 1} == given_stats.screening_statistics


def test_get_transitioned_records(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    review_manager_helpers,
) -> None:
    review_manager_helpers.reset_commit(base_repo_review_manager, commit="prep_commit")
    base_repo_review_manager.get_dedupe_operation()
    records = base_repo_review_manager.dataset.load_records_dict()

    record_dict = list(records.values())[0]
    record_dict[Fields.STATUS] = RecordState.md_processed
    base_repo_review_manager.dataset.save_records_dict(records)

    status_stats = base_repo_review_manager.get_status_stats()
    transitioned_records = status_stats.get_transitioned_records(
        base_repo_review_manager
    )
    assert transitioned_records == [
        {
            "origin": "test_records.bib/Srivastava2015",
            "source": RecordState.md_prepared,
            "dest": RecordState.md_processed,
            "type": OperationsType.dedupe,
        }
    ]
    operation_in_progress = status_stats.get_operation_in_progress(
        transitioned_records=transitioned_records
    )
    assert {"dedupe"} == operation_in_progress

    records = base_repo_review_manager.dataset.load_records_dict()

    record_dict = list(records.values())[0]
    record_dict[Fields.STATUS] = RecordState.rev_included
    base_repo_review_manager.dataset.save_records_dict(records)

    status_stats = base_repo_review_manager.get_status_stats()
    transitioned_records = status_stats.get_transitioned_records(
        base_repo_review_manager
    )
    assert transitioned_records == [
        {
            "origin": "test_records.bib/Srivastava2015",
            "source": RecordState.md_prepared,
            "dest": RecordState.rev_included,
            "type": "invalid_transition",
        }
    ]
