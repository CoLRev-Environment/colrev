#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.exceptions as colrev_exceptions
import colrev.process


@zope.interface.implementer(colrev.process.SearchEndpoint)
class CustomSearch:

    source_identifier = "https://api.crossref.org/works/{{doi}}"
    mode = "all"

    def __init__(self, *, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev.process.DefaultSettings, data=SETTINGS
        )

    def run_search(slef, SEARCH, params: dict, feed_file: Path) -> None:
        from colrev.review_dataset import ReviewDataset

        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = SEARCH.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict(
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
            raise colrev_exceptions.InvalidQueryException(
                "CROSSREF queries require a SCOPE section"
            )

        scope = query[query.find(" SCOPE ") :]
        if "journal_issn" not in scope:
            raise colrev_exceptions.InvalidQueryException(
                "CROSSREF queries require a journal_issn field in the SCOPE section"
            )
        pass
