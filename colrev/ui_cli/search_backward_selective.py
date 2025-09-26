#!/usr/bin/env python3
"""Scripts to run a selective backward search."""
from __future__ import annotations

import typing
from pathlib import Path

import colrev.env.tei_parser
import colrev.ops.search_api_feed
import colrev.record.record
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType

if typing.TYPE_CHECKING:
    import colrev.ops.search


def main(*, search_operation: colrev.ops.search.Search, bws: str) -> None:
    """Run a selective backward search (interactively on the cli)"""

    items = search_operation.review_manager.dataset.read_next_record(
        conditions=[{Fields.ID: bws}]
    )
    record_dict = list(items)[0]
    record = colrev.record.record.Record(record_dict)

    if not record.data.get(Fields.FILE, "NA").endswith(".pdf"):
        return
    if not record.get_tei_filename().is_file():
        search_operation.review_manager.logger.debug(
            f" creating tei: {record.data['ID']}"
        )
    tei = colrev.env.tei_parser.TEIParser(
        pdf_path=Path(record.data[Fields.FILE]),
        tei_path=record.get_tei_filename(),
    )

    search_source = colrev.search_file.ExtendedSearchFile(
        platform="colrev.unknown_source",
        search_results_path=Path("data/search/complementary_backward_search.bib"),
        search_type=SearchType.OTHER,
        search_string="",
        comment="",
        version="0.1.0",
    )
    feed = colrev.ops.search_api_feed.SearchAPIFeed(
        source_identifier="bws_id",
        search_source=search_source,
        update_only=False,
        logger=search_operation.review_manager.logger,
        verbose_mode=search_operation.review_manager.verbose_mode,
    )

    # print list
    tei_recs = tei.get_references()
    for i, tei_rec_dict in enumerate(tei_recs):
        tei_rec = colrev.record.record.Record(tei_rec_dict)
        print(f"{i}  : {tei_rec.format_bib_style()}")

    # import as record
    selection = ""
    while selection == "" or selection.isdigit():
        selection = input("Select record to import")
        if selection.isdigit() and 0 <= int(selection) < len(tei_recs) + 1:
            selected_record = tei_recs[int(selection)]
            selected_record["bws_id"] = f"{bws}/#{selection}"
            print(selected_record)
            feed.add_update_record(
                retrieved_record=colrev.record.record.Record(selected_record)
            )

        feed.save()
