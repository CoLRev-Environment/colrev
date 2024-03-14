#!/usr/bin/env python
"""Tests of the CoLRev search feeds"""
from __future__ import annotations

import typing
from copy import deepcopy
from pathlib import Path

import pytest

import colrev.record
import colrev.review_manager
import colrev.settings
from colrev.constants import Fields


@pytest.fixture(name="search_feed")
def fixture_search_feed(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> typing.Generator:
    """General search feed"""

    source = colrev.settings.SearchSource(
        endpoint="colrev.crossref",
        filename=Path("data/search/test.bib"),
        search_type=colrev.settings.SearchType.DB,
        search_parameters={"query": "query"},
        comment="",
    )
    base_repo_review_manager.get_search_operation()
    feed = source.get_api_feed(
        review_manager=base_repo_review_manager,
        source_identifier="doi",
        update_only=True,
        update_time_variant_fields=False,
    )

    prev_sources = base_repo_review_manager.settings.sources

    yield feed

    base_repo_review_manager.settings.sources = prev_sources


def test_search_feed(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    search_feed,
) -> None:
    """Test the search feed"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
    }
    with pytest.raises(
        colrev.exceptions.NotFeedIdentifiableException,
    ):
        search_feed.add_update_record(
            retrieved_record=colrev.record.Record(data=record_dict)
        )

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.CITED_BY: "10",
    }

    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )
    record_dict[Fields.CITED_BY] = "12"
    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )
    assert len(search_feed.feed_records) == 1

    search_feed.save()
    base_repo_review_manager.dataset.create_commit(msg="test")

    source = colrev.settings.SearchSource(
        endpoint="colrev.crossref",
        filename=Path("data/search/test.bib"),
        search_type=colrev.settings.SearchType.DB,
        search_parameters={"query": "query"},
        comment="",
    )

    feed = source.get_api_feed(
        review_manager=base_repo_review_manager,
        source_identifier="doi",
        update_only=True,
        update_time_variant_fields=False,
    )
    deepcopy(record_dict)
    record_dict[Fields.TITLE] = (
        "Analyzing the past to prepare for the future: Writing a literature review"
    )
    feed.add_update_record(retrieved_record=colrev.record.Record(data=record_dict))

    feed.add_update_record(retrieved_record=colrev.record.Record(data=record_dict))

    record_dict["crossmark"] = True  # type: ignore

    feed.add_update_record(retrieved_record=colrev.record.Record(data=record_dict))
