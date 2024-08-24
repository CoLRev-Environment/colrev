#!/usr/bin/env python
"""Utility to transform items from arXiv into records"""
from __future__ import annotations

from colrev.constants import Fields

# pylint: disable=too-many-branches
# pylint: disable=colrev-missed-constant-usage

FIELDS_TO_REMOVE = [
    "links",
    "href",
    "guidislink",
    "summary_detail",
    "title_detail",
    "updated",
    "updated_parsed",
    "author_detail",
    "published_parsed",
    "arxiv_primary_category",
    "tags",
]


def parse_record(entry: dict) -> dict:
    """Transform an arXiv item into a record"""

    entry[Fields.ENTRYTYPE] = "techreport"
    entry["arxivid"] = entry.pop("id").replace("http://arxiv.org/abs/", "")
    entry[Fields.AUTHOR] = " and ".join([a["name"] for a in entry.pop("authors")])
    entry[Fields.YEAR] = entry.pop("published")[:4]
    entry[Fields.ABSTRACT] = entry.pop("summary")
    entry[Fields.ABSTRACT] = (
        entry[Fields.ABSTRACT].replace("\n", " ").replace("\r", " ")
    )
    if "arxiv_journal_ref" in entry:
        entry["arxiv_journal_ref"] = (
            entry["arxiv_journal_ref"].replace("\n", " ").replace("\r", " ")
        )
    entry[Fields.TITLE] = entry["title"].replace("\n ", "")
    if "arxiv_doi" in entry:
        entry[Fields.DOI] = entry.pop("arxiv_doi")
    if "links" in entry:
        for link in entry["links"]:
            if link["type"] == "application/pdf":
                entry[Fields.FULLTEXT] = link["href"]
            else:
                entry[Fields.URL] = link["href"]
    if "link" in entry:
        if "url" in entry:
            del entry["link"]
        else:
            entry[Fields.URL] = entry.pop("link")
    if "arxiv_comment" in entry:
        entry[Fields.KEYWORDS] = (
            entry.pop("arxiv_comment").replace("Key words: ", "").replace("\n", "")
        )

    for field_to_remove in FIELDS_TO_REMOVE:
        if field_to_remove in entry:
            del entry[field_to_remove]

    if "keywords" in entry and "pages" in entry["keywords"]:
        del entry["keywords"]
    return entry
