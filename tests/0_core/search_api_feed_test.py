#!/usr/bin/env python
"""Tests of the CoLRev search feeds"""
from __future__ import annotations

import logging
import typing
from copy import deepcopy
from pathlib import Path

import pytest

import colrev.record
import colrev.review_manager
import colrev.settings
from colrev.constants import Fields

# flake8: noqa: E501


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


def test_search_feed_NotFeedIdentifiableException(search_feed):  # type: ignore
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


def test_search_feed_update(  # type: ignore
    search_feed,
) -> None:
    """Test the search feed"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )
    search_feed.save()

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
    }

    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )

    actual_return = search_feed.get_prev_feed_record(
        colrev.record.Record(data={"doi": "10.111/2222"})
    )
    assert actual_return.data == record_dict


def test_search_feed_published_forthcoming(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with info on forthcoming publication"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "forthcoming",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )
    search_feed.save()

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.YEAR: "2002",
    }

    search_feed.review_manager.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.Record(data=record_dict)
        )
        assert "Update published forthcoming paper" in caplog.text


def test_search_feed_substantial_change(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with warnings on substantial change"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2002",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.Record(data=record_dict)
    )

    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    search_feed.save()

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Working with empirical methods",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.YEAR: "2002",
    }

    search_feed.review_manager.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.Record(data=record_dict)
        )
        assert "leads to substantial changes" in caplog.text
        # TODO ( need to capture print statement for the following:)
        assert (
            "[('change', 'title', ('Working with empirical methods', 'Analyzing the past to prepare for the future: Writing a literature review'))]"
            in caplog.text
        )

    # actual_return = search_feed.get_prev_feed_record(
    #     colrev.record.Record(data={"doi": "10.111/2222"})
    # )

    # assert actual_return.data == {
    #     "ENTRYTYPE": "article",
    #     "ID": "000001",
    #     "author": "Webster, J and Watoson, R",
    #     "title": "Analyzing the past to prepare for the future: Writing a literature review",
    #     "year": "2002",
    #     "doi": "10.111/2222",
    # }

    # record_dict[Fields.CITED_BY] = "12"
    # search_feed.add_update_record(
    #     retrieved_record=colrev.record.Record(data=record_dict)
    # )
    # assert len(search_feed.feed_records) == 1

    # search_feed.save()
    # # base_repo_review_manager.dataset.create_commit(msg="test")

    # source = colrev.settings.SearchSource(
    #     endpoint="colrev.crossref",
    #     filename=Path("data/search/test.bib"),
    #     search_type=colrev.settings.SearchType.DB,
    #     search_parameters={"query": "query"},
    #     comment="",
    # )

    # feed = source.get_api_feed(
    #     review_manager=base_repo_review_manager,
    #     source_identifier="doi",
    #     update_only=True,
    #     update_time_variant_fields=False,
    # )
    # deepcopy(record_dict)
    # record_dict[Fields.TITLE] = (
    #     "Analyzing the past to prepare for the future: Writing a literature review"
    # )
    # feed.add_update_record(colrev.record.Record(data=record_dict))
    # feed.add_update_record(colrev.record.Record(data=record_dict))

    # record_dict["crossmark"] = True  # type: ignore

    # feed.add_update_record(colrev.record.Record(data=record_dict))
