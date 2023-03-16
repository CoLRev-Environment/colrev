#!/usr/bin/env python
from pathlib import Path

import pytest

import colrev.record


def test_record_state_model() -> None:
    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.md_processed)

    expected = {
        colrev.record.RecordState.md_retrieved,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.md_imported)
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
    }
    actual = rsm.get_preceding_states(
        state=colrev.record.RecordState.md_needs_manual_preparation
    )
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.md_prepared)
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.md_processed)
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
    }
    actual = rsm.get_preceding_states(
        state=colrev.record.RecordState.rev_prescreen_included
    )
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
        colrev.record.RecordState.rev_prescreen_included,
    }
    actual = rsm.get_preceding_states(
        state=colrev.record.RecordState.pdf_needs_manual_retrieval
    )
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
        colrev.record.RecordState.rev_prescreen_included,
        colrev.record.RecordState.pdf_needs_manual_retrieval,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.pdf_imported)
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
        colrev.record.RecordState.rev_prescreen_included,
        colrev.record.RecordState.pdf_needs_manual_retrieval,
        colrev.record.RecordState.pdf_imported,
    }
    actual = rsm.get_preceding_states(
        state=colrev.record.RecordState.pdf_needs_manual_preparation
    )
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
        colrev.record.RecordState.rev_prescreen_included,
        colrev.record.RecordState.pdf_needs_manual_retrieval,
        colrev.record.RecordState.pdf_imported,
        colrev.record.RecordState.pdf_needs_manual_preparation,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.pdf_prepared)
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
        colrev.record.RecordState.pdf_needs_manual_retrieval,
        colrev.record.RecordState.pdf_imported,
        colrev.record.RecordState.pdf_prepared,
        colrev.record.RecordState.pdf_needs_manual_preparation,
        colrev.record.RecordState.rev_prescreen_included,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.rev_included)
    assert expected == actual

    expected = {
        colrev.record.RecordState.md_retrieved,
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
        colrev.record.RecordState.md_prepared,
        colrev.record.RecordState.md_processed,
        colrev.record.RecordState.pdf_needs_manual_retrieval,
        colrev.record.RecordState.pdf_imported,
        colrev.record.RecordState.pdf_prepared,
        colrev.record.RecordState.pdf_needs_manual_preparation,
        colrev.record.RecordState.rev_prescreen_included,
        colrev.record.RecordState.rev_included,
    }
    actual = rsm.get_preceding_states(state=colrev.record.RecordState.rev_synthesized)
    assert expected == actual


def test_get_valid_transitions() -> None:
    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.md_retrieved)
    expected = {"load"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.md_imported)
    expected = {"prep"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(
        state=colrev.record.RecordState.md_needs_manual_preparation
    )
    expected = {"prep_man"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.md_prepared)
    expected = {"dedupe"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(
        state=colrev.record.RecordState.rev_prescreen_excluded
    )
    expected = set()
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(
        state=colrev.record.RecordState.rev_prescreen_included
    )
    expected = {"pdf_get"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.pdf_imported)
    expected = {"pdf_prep"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(
        state=colrev.record.RecordState.pdf_needs_manual_retrieval
    )
    expected = {"pdf_get_man"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.pdf_prepared)
    expected = {"screen"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(
        state=colrev.record.RecordState.pdf_needs_manual_preparation
    )
    expected = {"pdf_prep_man"}
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.rev_excluded)
    expected = set()
    actual = rsm.get_valid_transitions()
    assert expected == actual

    rsm = colrev.record.RecordStateModel(state=colrev.record.RecordState.rev_included)
    expected = {"data"}
    actual = rsm.get_valid_transitions()
    assert expected == actual


def test_get_post_x_states() -> None:
    # Go backwards: rev_included > md_prepared (iteratively extending the expected set)
    expected = {
        colrev.record.RecordState.rev_excluded,
        colrev.record.RecordState.rev_included,
        colrev.record.RecordState.rev_synthesized,
    }
    actual = colrev.record.RecordState.get_post_x_states(
        state=colrev.record.RecordState.rev_included
    )
    assert expected == actual

    expected.add(colrev.record.RecordState.pdf_prepared)
    actual = colrev.record.RecordState.get_post_x_states(
        state=colrev.record.RecordState.pdf_prepared
    )
    assert expected == actual

    expected.add(colrev.record.RecordState.rev_prescreen_included)
    expected.add(colrev.record.RecordState.rev_prescreen_excluded)
    expected.add(colrev.record.RecordState.pdf_needs_manual_retrieval)
    expected.add(colrev.record.RecordState.pdf_imported)
    expected.add(colrev.record.RecordState.pdf_not_available)
    expected.add(colrev.record.RecordState.pdf_needs_manual_preparation)
    expected.add(colrev.record.RecordState.pdf_prepared)
    actual = colrev.record.RecordState.get_post_x_states(
        state=colrev.record.RecordState.rev_prescreen_included
    )
    assert expected == actual

    expected.add(colrev.record.RecordState.md_processed)
    actual = colrev.record.RecordState.get_post_x_states(
        state=colrev.record.RecordState.md_processed
    )
    assert expected == actual

    expected.add(colrev.record.RecordState.md_prepared)
    actual = colrev.record.RecordState.get_post_x_states(
        state=colrev.record.RecordState.md_prepared
    )
    assert expected == actual


def test_leq() -> None:
    with pytest.raises(
        NotImplementedError,
    ):
        colrev.record.RecordState.md_retrieved < "string"

    # TODO : create ordered list, remove left element and assert that it is smaller than all remaining elements
    assert (
        colrev.record.RecordState.md_retrieved < colrev.record.RecordState.md_imported
    )
