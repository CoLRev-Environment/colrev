#!/usr/bin/env python
"""Tests for the process model"""
import pytest

from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.process.model import ProcessModel


def test_model() -> None:
    """Test the process model"""
    expected = {
        RecordState.md_retrieved,
    }
    actual = ProcessModel.get_preceding_states(state=RecordState.md_imported)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
    }
    actual = ProcessModel.get_preceding_states(
        state=RecordState.md_needs_manual_preparation
    )
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
    }
    actual = ProcessModel.get_preceding_states(state=RecordState.md_prepared)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
    }
    actual = ProcessModel.get_preceding_states(state=RecordState.md_processed)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
    }
    actual = ProcessModel.get_preceding_states(state=RecordState.rev_prescreen_included)
    assert expected == actual

    expected = {
        RecordState.md_retrieved,
        RecordState.md_imported,
        RecordState.md_needs_manual_preparation,
        RecordState.md_prepared,
        RecordState.md_processed,
        RecordState.rev_prescreen_included,
    }
    actual = ProcessModel.get_preceding_states(
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
    actual = ProcessModel.get_preceding_states(state=RecordState.pdf_imported)
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
    actual = ProcessModel.get_preceding_states(
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
    actual = ProcessModel.get_preceding_states(state=RecordState.pdf_prepared)
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
    actual = ProcessModel.get_preceding_states(state=RecordState.rev_included)
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
    actual = ProcessModel.get_preceding_states(state=RecordState.rev_synthesized)
    assert expected == actual


def test_get_valid_transitions() -> None:
    """Test get_valid_transitions"""

    expected = {OperationsType.load}
    actual = ProcessModel.get_valid_transitions(state=RecordState.md_retrieved)
    assert expected == actual

    expected = {OperationsType.prep}
    actual = ProcessModel.get_valid_transitions(state=RecordState.md_imported)
    assert expected == actual

    expected = {OperationsType.prep_man}
    actual = ProcessModel.get_valid_transitions(
        state=RecordState.md_needs_manual_preparation
    )
    assert expected == actual

    expected = {OperationsType.dedupe}
    actual = ProcessModel.get_valid_transitions(state=RecordState.md_prepared)
    assert expected == actual

    expected = set()
    actual = ProcessModel.get_valid_transitions(
        state=RecordState.rev_prescreen_excluded
    )
    assert expected == actual

    expected = {OperationsType.pdf_get}
    actual = ProcessModel.get_valid_transitions(
        state=RecordState.rev_prescreen_included
    )
    assert expected == actual

    expected = {OperationsType.pdf_prep}
    actual = ProcessModel.get_valid_transitions(state=RecordState.pdf_imported)
    assert expected == actual

    expected = {OperationsType.pdf_get_man}
    actual = ProcessModel.get_valid_transitions(
        state=RecordState.pdf_needs_manual_retrieval
    )
    assert expected == actual

    expected = {OperationsType.screen}
    actual = ProcessModel.get_valid_transitions(state=RecordState.pdf_prepared)
    assert expected == actual

    expected = {OperationsType.pdf_prep_man}
    actual = ProcessModel.get_valid_transitions(
        state=RecordState.pdf_needs_manual_preparation
    )
    assert expected == actual

    expected = set()
    actual = ProcessModel.get_valid_transitions(state=RecordState.rev_excluded)
    assert expected == actual

    expected = {OperationsType.data}
    actual = ProcessModel.get_valid_transitions(state=RecordState.rev_included)
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
