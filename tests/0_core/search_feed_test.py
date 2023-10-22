#!/usr/bin/env python
"""Tests of the CoLRev search feeds"""
import pytest

import colrev.review_manager
import colrev.settings
from colrev.constants import Fields


def test_search_feed(  # type: ignore
    base_repo_review_manager: colrev.review_manager.ReviewManager,
    search_feed,
) -> None:
    """Test the search feed"""

    record_dict = {Fields.ID: "0001", Fields.ENTRYTYPE: "article"}
    with pytest.raises(
        colrev.exceptions.NotFeedIdentifiableException,
    ):
        search_feed.set_id(record_dict=record_dict)

    record_dict[Fields.DOI] = "10.111/2222"
    search_feed.set_id(record_dict=record_dict)
    search_feed.set_id(record_dict=record_dict)

    search_feed.add_record(record=colrev.record.Record(data=record_dict))
    record_dict[Fields.MD_PROV] = {}  # type: ignore
    record_dict[Fields.D_PROV] = {}  # type: ignore
    record_dict[Fields.STATUS] = "content"
    record_dict[Fields.CITED_BY] = 10  # type: ignore
    search_feed.add_record(record=colrev.record.Record(data=record_dict))
    record_dict[Fields.CITED_BY] = 12  # type: ignore
    search_feed.add_record(record=colrev.record.Record(data=record_dict))
    assert len(search_feed.feed_records) == 1

    search_feed.print_post_run_search_infos(records={})
    search_feed.save_feed_file()
    base_repo_review_manager.create_commit(msg="test")

    # TODO : integrate crossref_feed.nr_added += 1 into feed (including update_existing_record())
