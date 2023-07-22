#!/usr/bin/env python3
"""Scripts to run a selective backward search."""
from __future__ import annotations

from pathlib import Path

import colrev.record


def main(*, search_operation: colrev.ops.search.Search, bws: str) -> None:
    """Run a selective backward search (interactively on the cli)"""

    items = search_operation.review_manager.dataset.read_next_record(
        conditions=[{"ID": bws}]
    )
    record_dict = list(items)[0]
    record = colrev.record.Record(data=record_dict)

    if not record.data.get("file", "NA").endswith(".pdf"):
        return
    if not record.get_tei_filename().is_file():
        search_operation.review_manager.logger.debug(
            f" creating tei: {record.data['ID']}"
        )
    tei = search_operation.review_manager.get_tei(
        pdf_path=Path(record.data["file"]),
        tei_path=record.get_tei_filename(),
    )

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/complementary_backward_search.bib"),
        search_type=colrev.settings.SearchType.OTHER,
        search_parameters={},
        comment="",
    )
    feed = search_source.get_feed(
        review_manager=search_operation.review_manager,
        source_identifier="bws_id",
        update_only=False,
    )

    # print list
    tei_recs = tei.get_bibliography(min_intext_citations=0)
    for i, tei_rec_dict in enumerate(tei_recs):
        tei_rec = colrev.record.Record(data=tei_rec_dict)
        print(f"{i}  : {tei_rec.format_bib_style()}")

    # import as record
    selection = ""
    while selection == "" or selection.isdigit():
        selection = input("Select record to import")
        if selection.isdigit() and 0 <= int(selection) < len(tei_recs) + 1:
            selected_record = tei_recs[int(selection)]
            selected_record["bws_id"] = f"{bws}/#{selection}"
            print(selected_record)
            feed.set_id(record_dict=selected_record)
            feed.add_record(record=colrev.record.Record(data=selected_record))

        feed.save_feed_file()
