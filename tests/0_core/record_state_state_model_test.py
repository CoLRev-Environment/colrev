#!/usr/bin/env python
"""Tests for the RecordState model"""
import pytest

from colrev.constants import RecordState
from colrev.record.record_state_model import RecordStateModel


def test_record_state_model() -> None:
    """Test the RecordState model"""
    expected = {
        RecordState.md_retrieved,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.md_imported)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
    }
    actual = RecordStateModel.get_preceding_states(
        state=RecordState.md_needs_manual_preparation
    )
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.md_prepared)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.md_processed)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
    }
    actual = RecordStateModel.get_preceding_states(
        state=RecordState.rev_prescreen_included
    )
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.rev_prescreen_included,
    }
    actual = RecordStateModel.get_preceding_states(
        state=RecordState.pdf_needs_manual_retrieval
    )
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.rev_prescreen_included,
        RecordState.pdf_needs_manual_retrieval,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.pdf_imported)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.rev_prescreen_included,
        RecordState.pdf_needs_manual_retrieval,
        RecordState.pdf_imported,
    }
    actual = RecordStateModel.get_preceding_states(
        state=RecordState.pdf_needs_manual_preparation
    )
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.rev_prescreen_included,
        RecordState.pdf_needs_manual_retrieval,
        RecordState.pdf_imported,
        RecordState.pdf_needs_manual_preparation,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.pdf_prepared)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.pdf_needs_manual_retrieval,
        RecordState.pdf_imported,
        RecordState.pdf_prepared,
        RecordState.pdf_needs_manual_preparation,
        RecordState.rev_prescreen_included,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.rev_included)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.pdf_needs_manual_retrieval,
        RecordState.pdf_imported,
        RecordState.pdf_prepared,
        RecordState.pdf_needs_manual_preparation,
        RecordState.rev_prescreen_included,
        RecordState.rev_included,
    }
    actual = RecordStateModel.get_preceding_states(state=RecordState.rev_synthesized)
    assert expected == actual


def test_get_valid_transitions() -> None:
    """Test get_valid_transitions"""

    expected = {"load"}
    actual = RecordStateModel.get_valid_transitions(state=RecordState.md_retrieved)
    assert expected == actual

    expected = {"prep"}
    actual = RecordStateModel.get_valid_transitions(state=RecordState.md_imported)
    assert expected == actual

    expected = {"prep_man"}
    actual = RecordStateModel.get_valid_transitions(
        state=RecordState.md_needs_manual_preparation
    )
    assert expected == actual

    expected = {"dedupe"}
    actual = RecordStateModel.get_valid_transitions(state=RecordState.md_prepared)
    assert expected == actual

    expected = set()
    actual = RecordStateModel.get_valid_transitions(
        state=RecordState.rev_prescreen_excluded
    )
    assert expected == actual

    expected = {"pdf_get"}
    actual = RecordStateModel.get_valid_transitions(
        state=RecordState.rev_prescreen_included
    )
    assert expected == actual

    expected = {"pdf_prep"}
    actual = RecordStateModel.get_valid_transitions(state=RecordState.pdf_imported)
    assert expected == actual

    expected = {"pdf_get_man"}
    actual = RecordStateModel.get_valid_transitions(
        state=RecordState.pdf_needs_manual_retrieval
    )
    assert expected == actual

    expected = {"screen"}
    actual = RecordStateModel.get_valid_transitions(state=RecordState.pdf_prepared)
    assert expected == actual

    expected = {"pdf_prep_man"}
    actual = RecordStateModel.get_valid_transitions(
        state=RecordState.pdf_needs_manual_preparation
    )
    assert expected == actual

    expected = set()
    actual = RecordStateModel.get_valid_transitions(state=RecordState.rev_excluded)
    assert expected == actual

    expected = {"data"}
    actual = RecordStateModel.get_valid_transitions(state=RecordState.rev_included)
    assert expected == actual


def test_get_post_x_states() -> None:
    """Test get_post_x_states"""

    # Go backwards: rev_included > md_prepared (iteratively extending the expected set)
    expected = {
        RecordState.rev_excluded,
        RecordState.rev_included,
        RecordState.rev_synthesized,
    }
    actual = RecordState.get_post_x_states(state=RecordState.rev_included)
    assert expected == actual

    expected.add(RecordState.pdf_prepared)
    actual = RecordState.get_post_x_states(state=RecordState.pdf_prepared)
    assert expected == actual

    expected.add(RecordState.rev_prescreen_included)
    expected.add(RecordState.rev_prescreen_excluded)
    expected.add(RecordState.pdf_needs_manual_retrieval)
    expected.add(RecordState.pdf_imported)
    expected.add(RecordState.pdf_not_available)
    expected.add(RecordState.pdf_needs_manual_preparation)
    expected.add(RecordState.pdf_prepared)
    actual = RecordState.get_post_x_states(state=RecordState.rev_prescreen_included)
    assert expected == actual

    expected.add(RecordState.md_processed)
    actual = RecordState.get_post_x_states(state=RecordState.md_processed)
    assert expected == actual

    expected.add(RecordState.md_prepared)
    actual = RecordState.get_post_x_states(state=RecordState.md_prepared)
    assert expected == actual

    with pytest.raises(ValueError):
        RecordState.get_post_x_states(state=RecordState.md_needs_manual_preparation)


def test_leq() -> None:
    """Test leq"""

    with pytest.raises(
        NotImplementedError,
    ):
        if RecordState.md_retrieved < "string":
            print("Error")

    # TODO : create ordered list, remove left element and
    # assert that it is smaller than all remaining elements
    assert RecordState.md_retrieved < RecordState.md_imported
