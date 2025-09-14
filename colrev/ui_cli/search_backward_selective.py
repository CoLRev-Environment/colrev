#!/usr/bin/env python3
"""Scripts to run a selective backward search."""
from __future__ import annotations

import typing
from pathlib import Path

import colrev.env.tei_parser
import colrev.record.record
import colrev.settings
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

    search_source = colrev.settings.SearchSource(
        endpoint="colrev.unknown_source",
        filename=Path("data/search/complementary_backward_search.bib"),
        search_type=SearchType.OTHER,
        search_parameters={},
        comment="",
    )
    feed = search_source.get_api_feed(
        review_manager=search_operation.review_manager,
        source_identifier="bws_id",
        update_only=False,
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
