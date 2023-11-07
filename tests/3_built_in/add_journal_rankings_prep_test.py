#!/usr/bin/env python
"""Test the add_journal_ranking prep package"""
from pathlib import Path

import pytest

import colrev.ops.built_in.prep.add_journal_ranking
import colrev.ops.prep
from colrev.constants import Fields


@pytest.fixture(scope="package", name="ajr_instance")
def elp(  # type: ignore
    prep_operation: colrev.ops.prep.Prep, session_mocker
) -> colrev.ops.built_in.prep.add_journal_ranking.AddJournalRanking:
    """Fixture returning an AddJournalRanking instance"""
    settings = {"endpoint": "colrev.add_journal_ranking"}
    ajr_instance = colrev.ops.built_in.prep.add_journal_ranking.AddJournalRanking(
        prep_operation=prep_operation, settings=settings
    )
    temp_sqlite = prep_operation.review_manager.path.parent / Path(
        "sqlite_index_test.db"
    )
    with session_mocker.patch.object(
        colrev.env.local_index.LocalIndex, "SQLITE_PATH", temp_sqlite
    ):
        local_index = colrev.env.local_index.LocalIndex(verbose_mode=True)
    local_index.load_journal_rankings()

    return ajr_instance


@pytest.mark.parametrize(
    "input_value, expected",
    [
        (
            {
                Fields.JOURNAL: "MIS Quarterly",
            },
            {
                Fields.D_PROV: {
                    "journal_ranking": {"note": "", "source": "add_journal_ranking"}
                },
                Fields.JOURNAL: "MIS Quarterly",
                "journal_ranking": "Senior Scholar's List of Premier Journals,FT-50",
            },
        )
    ],
)
def test_prep_exclude_languages(
    ajr_instance: colrev.ops.built_in.prep.add_journal_ranking.AddJournalRanking,
    input_value: dict,
    expected: dict,
) -> None:
    """Test the add_journal_ranking"""
    record = colrev.record.PrepRecord(data=input_value)
    returned_record = ajr_instance.prepare(record=record)
    actual = returned_record.data
    assert expected == actual
