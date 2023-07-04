#!/usr/bin/env python
"""Tests of the CoLRev search feeds"""
import pytest

import colrev.review_manager
import colrev.settings


def test_search_feed(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    search_feed,
) -> None:
    """Test the search feed"""

    record_dict = {"ID": "0001", "ENTRYTYPE": "article"}
    with pytest.raises(
        colrev.exceptions.NotFeedIdentifiableException,
    ):
        search_feed.set_id(record_dict=record_dict)

    record_dict["doi"] = "10.111/2222"
    search_feed.set_id(record_dict=record_dict)
    search_feed.set_id(record_dict=record_dict)

    search_feed.add_record(record=colrev.record.Record(data=record_dict))
    record_dict["colrev_masterdata_provenance"] = {}  # type: ignore
    record_dict["colrev_data_provenance"] = {}  # type: ignore
    record_dict["colrev_status"] = "content"
    record_dict["cited_by"] = 10  # type: ignore
    search_feed.add_record(record=colrev.record.Record(data=record_dict))
    record_dict["cited_by"] = 12  # type: ignore
    search_feed.add_record(record=colrev.record.Record(data=record_dict))
    assert len(search_feed.feed_records) == 1

    search_feed.print_post_run_search_infos(records={})
    search_feed.save_feed_file()
    base_repo_review_manager.create_commit(msg="test")

    # TODO : integrate crossref_feed.nr_added += 1 into feed (including update_existing_record())
