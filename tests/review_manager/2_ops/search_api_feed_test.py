#!/usr/bin/env python
"""Tests of the CoLRev search feeds"""
from __future__ import annotations

import logging
import typing
from copy import deepcopy
from pathlib import Path

import pytest

import colrev.ops.search_api_feed
import colrev.record.record
import colrev.review_manager
from colrev.constants import DefectCodes
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import SearchType

# flake8: noqa: E501


@pytest.fixture(name="search_feed")
def fixture_search_feed(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> typing.Generator:
    """General search feed"""

    source = colrev.search_file.ExtendedSearchFile(
        platform="colrev.crossref",
        search_results_path=Path("data/search/test.bib"),
        search_type=SearchType.DB,
        search_string="query",
        comment="",
        version="0.1.0",
    )
    base_repo_review_manager.get_search_operation()
    feed = colrev.ops.search_api_feed.SearchAPIFeed(
        source_identifier="doi",
        search_source=source,
        update_only=True,
        logger=base_repo_review_manager.logger,
        verbose_mode=base_repo_review_manager.verbose_mode,
    )

    prev_sources = base_repo_review_manager.settings.sources

    yield feed

    base_repo_review_manager.settings.sources = prev_sources


def test_search_feed_update(  # type: ignore
    base_repo_review_manager,
    search_feed,
) -> None:
    """Test the search feed"""

    # Usual setup: repeated retrieval/updating of feed records
    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )

    # Explitly add to records (usually done by the load operation)
    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    search_feed.save()

    # Second "iteration"
    source = colrev.search_file.ExtendedSearchFile(
        platform="colrev.crossref",
        search_results_path=Path("data/search/test.bib"),
        search_type=SearchType.DB,
        search_string="query",
        comment="",
        version="0.1.0",
    )
    # base_repo_review_manager.get_search_operation()
    search_feed = colrev.ops.search_api_feed.SearchAPIFeed(
        source_identifier="doi",
        search_source=source,
        update_only=True,
        logger=base_repo_review_manager.logger,
        verbose_mode=base_repo_review_manager.verbose_mode,
    )
    assert search_feed._available_ids == {"10.111/2222": "000001"}
    assert search_feed._next_incremental_id == 2

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
    }

    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )

    actual_return = search_feed.get_prev_feed_record(
        colrev.record.record.Record({"doi": "10.111/2222"})
    )
    assert actual_return.data == record_dict


def test_search_feed_update_fields(  # type: ignore
    search_feed,
) -> None:
    """Test the search feed"""
    search_feed.update_only = True
    # Usual setup: repeated retrieval/updating of feed records
    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.CITED_BY: "12",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )

    # Explitly add to records (usually done by the load operation)
    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    record_dict[Fields.CITED_BY] = "13"
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    assert search_feed.feed_records["000001"][Fields.CITED_BY] == "12"
    assert search_feed.records["000001"][Fields.CITED_BY] == "12"

    # Time-variant fields like cited-by should only change if all records are retrieved (update_only=False)
    search_feed.update_only = False
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    assert search_feed.feed_records["000001"][Fields.CITED_BY] == "13"


def test_search_feed_preventing_updates_of_curated_records_from_non_curated_feeds(  # type: ignore
    search_feed,
) -> None:
    """Test the search feed: it should prevent updating curated records from non-curated sources"""
    search_feed.update_only = True
    # Usual setup: repeated retrieval/updating of feed records
    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )

    # Explitly add to records (usually done by the load operation)
    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    main_record[Fields.MD_PROV] = {FieldValues.CURATED: "https:..."}  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    record_dict[Fields.TITLE] = "Analyzing the past to prepare for the future"
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    # The feed record should change
    assert (
        search_feed.feed_records["000001"][Fields.TITLE]
        == "Analyzing the past to prepare for the future"
    )
    # The main record should not change
    assert (
        search_feed.records["000001"][Fields.TITLE]
        == "Analyzing the past to prepare for the future: Writing a literature review"
    )


def test_search_feed_update_fields_prov_removal(  # type: ignore
    search_feed,
) -> None:
    """Test the search feed"""
    search_feed.update_only = True
    # Usual setup: repeated retrieval/updating of feed records
    record_dict = {
        Fields.MD_PROV: {},
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.CITED_BY: "12",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )

    assert Fields.MD_PROV not in search_feed.feed_records["000001"]


def test_search_feed_save(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed save"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2022",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    search_feed.save()

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.save()
        assert "No additional records retrieved" in caplog.text


def test_search_feed_published_forthcoming_1(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with info on forthcoming publication"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "forthcoming",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )

    # Explitly add to records (usually done by the load operation)
    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    search_feed.save()

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.YEAR: "2002",
    }

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.record.Record(record_dict)
        )
        assert "Update published forthcoming paper" in caplog.text

    assert search_feed.records["000001"][Fields.YEAR] == "2002"
    assert search_feed.feed_records["000001"][Fields.YEAR] == "2002"


def test_search_feed_published_forthcoming_2(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with info on forthcoming publication"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2002",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    search_feed.save()

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.YEAR: "2002",
        Fields.VOLUME: "12",
        Fields.NUMBER: "2",
    }

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.record.Record(record_dict)
        )
        assert "Update published forthcoming paper" in caplog.text


def test_search_feed_minor_change(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with a minor change"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2002",
        Fields.VOLUME: "12",
        Fields.NUMBER: "2",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    search_feed.save()

    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature reviews",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2002",
        Fields.VOLUME: "12",
        Fields.NUMBER: "2",
    }

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.record.Record(record_dict)
        )
        assert "check/update" in caplog.text


def test_search_feed_retracted(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with retracted publication"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2002",
    }
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    search_feed.save()

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.YEAR: "2002",
        "crossmark": "True",  # type: ignore
    }

    main_record = deepcopy(record_dict)
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.record.Record(record_dict)
        )
        assert "Found paper retract" in caplog.text


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
        retrieved_record=colrev.record.record.Record(record_dict)
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

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.record.Record(record_dict)
        )
        assert "leads to substantial changes" in caplog.text
        # TODO ( need to capture print statement for the following:)
        assert (
            "[('change', 'title', ('Working with empirical methods', 'Analyzing the past to prepare for the future: Writing a literature review'))]"
            in caplog.text
        )


def test_search_feed_missing_ignored_fields(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed with retracted publication"""

    record_dict = {
        Fields.MD_PROV: {
            Fields.VOLUME: {
                "source": "colrev_curation.masterdata_restrictions",
                "note": f"IGNORE:{DefectCodes.MISSING}",
            }
        },
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.AUTHOR: "Webster, J and Watoson, R",
        Fields.YEAR: "2002",
    }
    main_record = deepcopy(record_dict)

    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    main_record[Fields.ORIGIN] = ["test.bib/000001"]  # type: ignore
    search_feed.records = {main_record[Fields.ID]: main_record}
    search_feed.save()

    record_dict = {
        Fields.ID: "000001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2002",
        Fields.VOLUME: "12",
    }

    search_feed.logger.propagate = True
    with caplog.at_level(logging.INFO):
        search_feed.add_update_record(
            retrieved_record=colrev.record.record.Record(record_dict)
        )
        assert Fields.VOLUME not in search_feed.records["0001"]


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
            retrieved_record=colrev.record.record.Record(record_dict)
        )


def test_search_feed_prep_mode(search_feed, caplog) -> None:  # type: ignore
    """Test the search feed save"""

    record_dict = {
        Fields.ID: "0001",
        Fields.ENTRYTYPE: "article",
        Fields.TITLE: "Analyzing the past to prepare for the future: Writing a literature review",
        Fields.DOI: "10.111/2222",
        Fields.YEAR: "2022",
    }
    search_feed.prep_mode = True
    search_feed.add_update_record(
        retrieved_record=colrev.record.record.Record(record_dict)
    )
    assert record_dict[Fields.ORIGIN] == ["test.bib/000001"]
    search_feed.prep_mode = False
