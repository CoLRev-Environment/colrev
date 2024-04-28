#!/usr/bin/env python
"""Utility to transform items from semanticscholar into records"""
from __future__ import annotations

import re

from semanticscholar import Paper

import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

# https://api.semanticscholar.org/api-docs

PUB_TYPE_ENTRYTYPE_MAP = {
    "Review": ENTRYTYPES.ARTICLE,
    "JournalArticle": ENTRYTYPES.ARTICLE,
    "CaseReport": ENTRYTYPES.TECHREPORT,
    "ClinicalTrial": ENTRYTYPES.MISC,
    "Dataset": ENTRYTYPES.MISC,
    "Editorial": ENTRYTYPES.MISC,
    "LettersAndComments": ENTRYTYPES.MISC,
    "MetaAnalysis": ENTRYTYPES.ARTICLE,
    "News": ENTRYTYPES.MISC,
    "Study": ENTRYTYPES.MISC,
    "Book": ENTRYTYPES.BOOK,
    "BookSection": ENTRYTYPES.INBOOK,
    "Conference": ENTRYTYPES.INPROCEEDINGS,
}

SUPPORTED_FIELDS = [
    Fields.ID,
    Fields.SEMANTIC_SCHOLAR_ID,
    Fields.DBLP_KEY,
    Fields.DOI,
    Fields.ENTRYTYPE,
    Fields.ISSN,
    Fields.JOURNAL,
    Fields.BOOKTITLE,
    Fields.VOLUME,
    Fields.PAGES,
    Fields.TITLE,
    Fields.AUTHOR,
    Fields.YEAR,
    Fields.CITED_BY,
    Fields.ABSTRACT,
    Fields.FULLTEXT,
]


def _assign_entrytype(*, record_dict: dict) -> None:
    """Method to assign the ENTRYTYPE"""

    publication_types = record_dict.get("publicationTypes")
    if publication_types is not None and len(publication_types) > 0:
        entrytype = publication_types[0]
    else:
        entrytype = ENTRYTYPES.MISC

    record_dict[Fields.ENTRYTYPE] = PUB_TYPE_ENTRYTYPE_MAP.get(
        entrytype, ENTRYTYPES.MISC
    )
    if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.MISC and "journal" in record_dict:
        record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE


def _assign_authors(*, record_dict: dict) -> None:
    """Method to assign authors from item"""

    authors = [
        author["name"] for author in record_dict.get("authors", []) if "name" in author
    ]
    record_dict[Fields.AUTHOR] = (
        colrev.record.record_prep.PrepRecord.format_author_field(" and ".join(authors))
    )


def _assign_issn(*, record_dict: dict) -> None:
    """Method to assign the issn"""

    issn = (record_dict.get("publicationVenue", {}) or {}).get("issn")
    if issn:
        record_dict[Fields.ISSN] = issn


def _assign_ids(*, record_dict: dict) -> None:
    """Method to assign external IDs from item"""
    ext_ids = record_dict.get("externalIds", {})

    if "DOI" in ext_ids:
        record_dict[Fields.DOI] = ext_ids["DOI"].upper()
    if "DBLP" in ext_ids:
        record_dict[Fields.DBLP_KEY] = str(ext_ids["DBLP"])


def _assign_abstract(*, record_dict: dict) -> None:
    """Method to assign external IDs from item"""
    abstract = record_dict.get("abstract", "")
    if abstract is not None:
        record_dict[Fields.ABSTRACT] = abstract.replace("\n", " ").lstrip().rstrip()
    else:
        record_dict[Fields.ABSTRACT] = ""


def _assign_article_fields(*, record_dict: dict) -> None:
    """Method to assign pages and volume from item"""

    if record_dict.get("journal") is None:
        return

    if "volume" in record_dict["journal"]:
        record_dict[Fields.VOLUME] = record_dict["journal"]["volume"]
    if "pages" in record_dict["journal"]:
        pages = record_dict["journal"]["pages"]
        if "-" in pages:
            try:
                pages = re.sub(r"\s+|[a-zA-Z]+", "", pages)
                pages_list = pages.split("-")
                page_a = int(pages_list[0])
                page_b = int(pages_list[1])
                if page_a > page_b:
                    pages = str(page_b) + "--" + str(page_a)
                elif page_a == page_b:
                    pages = str(page_a)
                else:
                    pages = str(page_a) + "--" + str(page_b)
            except ValueError:
                pass

        record_dict[Fields.PAGES] = pages

    record_dict[Fields.JOURNAL] = record_dict.get("venue", "")


def _assign_book_fields(*, record_dict: dict) -> None:
    """Method to assign book specific details from item"""
    book_title = record_dict.get("journal", {}).get("name")
    title = record_dict.get(Fields.TITLE, "")

    if book_title and title:
        if (book_title in title) or (title in book_title):
            record_dict[Fields.TITLE] = max(book_title, title, key=len)
        else:
            record_dict[Fields.BOOKTITLE] = book_title


def _assign_inproc_fields(*, record_dict: dict) -> None:
    """Method to assign inproceedings specific details from item"""

    if "journal" in record_dict:
        del record_dict["journal"]

    venue = record_dict.get("venue", "")
    if venue:
        record_dict[Fields.BOOKTITLE] = venue


def _assign_fulltext(*, record_dict: dict) -> None:
    """Method to assign fulltext from item."""
    fulltext_url = (record_dict.get("openAccessPdf") or {}).get("url", "")
    if fulltext_url:
        record_dict[Fields.FULLTEXT] = fulltext_url


def _item_to_record(item: Paper) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""

    record_dict = dict(item)

    record_dict[Fields.SEMANTIC_SCHOLAR_ID] = record_dict["paperId"]
    record_dict[Fields.TITLE] = record_dict.get("title", "")
    _assign_authors(record_dict=record_dict)
    _assign_fulltext(record_dict=record_dict)
    _assign_issn(record_dict=record_dict)
    _assign_ids(record_dict=record_dict)
    _assign_abstract(record_dict=record_dict)
    record_dict[Fields.YEAR] = record_dict.get("year", "")
    record_dict[Fields.CITED_BY] = record_dict.get("citationCount", "")

    _assign_entrytype(record_dict=record_dict)
    if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
        _assign_article_fields(record_dict=record_dict)

    elif record_dict[Fields.ENTRYTYPE] in [ENTRYTYPES.BOOK, ENTRYTYPES.INBOOK]:
        _assign_book_fields(record_dict=record_dict)

    elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
        _assign_inproc_fields(record_dict=record_dict)

    return record_dict


def _remove_fields(*, record: dict) -> dict:
    """Method to remove unsupported fields from semanticscholar record"""

    record_dict = {k: v for k, v in record.items() if k in SUPPORTED_FIELDS and v != ""}

    return record_dict


def s2_dict_to_record(*, item: dict) -> dict:
    """Convert a semanticscholar item to a record dict"""

    try:
        record_dict = _item_to_record(item=item)
        record_dict = _remove_fields(record=record_dict)

    except (IndexError, KeyError) as exc:
        raise colrev_exceptions.RecordNotParsableException(
            f"Exception: Record not parsable: {exc}"
        ) from exc

    return record_dict
