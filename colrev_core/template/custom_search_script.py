#! /usr/bin/env python
from pathlib import Path

import zope.interface

from colrev_core.process import SearchEndpoint
from colrev_core.search import InvalidQueryException


@zope.interface.implementer(SearchEndpoint)
class CustomSearch:

    source_identifier = "https://api.crossref.org/works/{{doi}}"
    mode = "all"

    @classmethod
    def run_search(cls, REVIEW_MANAGER, params: dict, feed_file: Path) -> None:
        from colrev_core.review_dataset import ReviewDataset

        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
                    load_str=bibtex_file.read()
                )

            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )

        # Add new records to the dictionary:
        records[max_id] = {
            "ID": max_id,
            "ENTRYTYPE": "article",
            "author": "Smith, M.",
            "title": "Editorial",
            "journal": "nature",
            "year": "2020",
        }

        feed_file.parents[0].mkdir(parents=True, exist_ok=True)
        ReviewDataset.save_records_dict_to_file(records=records, save_path=feed_file)
        return

    @classmethod
    def validate_params(cls, query: str) -> None:
        if " SCOPE " not in query:
            raise InvalidQueryException("CROSSREF queries require a SCOPE section")

        scope = query[query.find(" SCOPE ") :]
        if "journal_issn" not in scope:
            raise InvalidQueryException(
                "CROSSREF queries require a journal_issn field in the SCOPE section"
            )
        pass
