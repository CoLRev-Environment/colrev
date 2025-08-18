#!/usr/bin/env python
"""Test the add_journal_ranking prep package"""
import warnings
from pathlib import Path

import pytest

import colrev.env.local_index_builder
import colrev.ops.prep
import colrev.packages.add_journal_ranking.src.add_journal_ranking
from colrev.constants import Fields


@pytest.fixture(scope="package", name="ajr_instance")
def elp(  # type: ignore
    prep_operation: colrev.ops.prep.Prep, session_mocker
) -> colrev.packages.add_journal_ranking.src.add_journal_ranking.AddJournalRanking:
    """Fixture returning an AddJournalRanking instance"""
    settings = {"endpoint": "colrev.add_journal_ranking"}
    ajr_instance = (
        colrev.packages.add_journal_ranking.src.add_journal_ranking.AddJournalRanking(
            prep_operation=prep_operation, settings=settings
        )
    )
    temp_sqlite = prep_operation.review_manager.path.parent / Path(
        "sqlite_index_test.db"
    )

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=".*pathlib\\.Path\\.__enter__.*",
            category=DeprecationWarning,
        )
        with session_mocker.patch.object(
            colrev.constants.Filepaths, "LOCAL_INDEX_SQLITE_FILE", temp_sqlite
        ):
            local_index_builder = colrev.env.local_index_builder.LocalIndexBuilder(
                verbose_mode=True
            )
    local_index_builder.index_journal_rankings()

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
                Fields.MD_PROV: {},
                Fields.JOURNAL: "MIS Quarterly",
                "journal_ranking": "Senior Scholar's List of Premier Journals,FT-50",
            },
        )
    ],
)
def test_prep_exclude_languages(
    ajr_instance: colrev.packages.add_journal_ranking.src.add_journal_ranking.AddJournalRanking,
    input_value: dict,
    expected: dict,
) -> None:
    """Test the add_journal_ranking"""
    record = colrev.record.record_prep.PrepRecord(input_value)
    returned_record = ajr_instance.prepare(record=record)
    actual = returned_record.data
    assert expected == actual
