#!/usr/bin/env python
"""Utility to transform items from semanticscholar into records"""
from __future__ import annotations

import re

from semanticscholar import Paper

import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.record import PrepRecord as prep_record

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


def __assign_entrytype(*, record_dict: dict) -> None:
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


def __assign_authors(*, record_dict: dict) -> None:
    """Method to assign authors from item"""

    authors = [
        author["name"] for author in record_dict.get("authors", []) if "name" in author
    ]
    record_dict[Fields.AUTHOR] = prep_record.format_author_field(
        input_string=" and ".join(authors)
    )


def __assign_issn(*, record_dict: dict) -> None:
    """Method to assign the issn"""

    issn = (record_dict.get("publicationVenue", {}) or {}).get("issn")
    if issn:
        record_dict[Fields.ISSN] = issn


def __assign_ids(*, record_dict: dict) -> None:
    """Method to assign external IDs from item"""
    ext_ids = record_dict.get("externalIds", {})

    if "DOI" in ext_ids:
        record_dict[Fields.DOI] = ext_ids["DOI"].upper()
    if "DBLP" in ext_ids:
        record_dict[Fields.DBLP_KEY] = str(ext_ids["DBLP"])


def __assign_abstract(*, record_dict: dict) -> None:
    """Method to assign external IDs from item"""
    abstract = record_dict.get("abstract", "")
    if abstract is not None:
        record_dict[Fields.ABSTRACT] = abstract.replace("\n", " ").lstrip().rstrip()
    else:
        record_dict[Fields.ABSTRACT] = ""


def __assign_article_fields(*, record_dict: dict) -> None:
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
                a = int(pages_list[0])
                b = int(pages_list[1])
                if a > b:
                    pages = str(b) + "--" + str(a)
                elif a == b:
                    pages = str(a)
                else:
                    pages = str(a) + "--" + str(b)
            except ValueError:
                pass

        record_dict[Fields.PAGES] = pages

    record_dict[Fields.JOURNAL] = record_dict.get("venue", "")


def __assign_book_fields(*, record_dict: dict) -> None:
    """Method to assign book specific details from item"""
    book_title = record_dict.get("journal", {}).get("name")
    title = record_dict.get(Fields.TITLE, "")

    if book_title and title:
        if (book_title in title) or (title in book_title):
            record_dict[Fields.TITLE] = max(book_title, title, key=len)
        else:
            record_dict[Fields.BOOKTITLE] = book_title


def __assign_inproc_fields(*, record_dict: dict) -> None:
    """Method to assign inproceedings specific details from item"""

    if "journal" in record_dict:
        del record_dict["journal"]

    venue = record_dict.get("venue", "")
    if venue:
        record_dict[Fields.BOOKTITLE] = venue


def __assign_fulltext(*, record_dict: dict) -> None:
    """Method to assign fulltext from item."""
    fulltext_url = (record_dict.get("openAccessPdf") or {}).get("url", "")
    if fulltext_url:
        record_dict[Fields.FULLTEXT] = fulltext_url


def __item_to_record(item: Paper) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""

    record_dict = dict(item)

    record_dict[Fields.SEMANTIC_SCHOLAR_ID] = record_dict["paperId"]
    record_dict[Fields.TITLE] = record_dict.get("title", "")
    __assign_authors(record_dict=record_dict)
    __assign_fulltext(record_dict=record_dict)
    __assign_issn(record_dict=record_dict)
    __assign_ids(record_dict=record_dict)
    __assign_abstract(record_dict=record_dict)
    record_dict[Fields.YEAR] = record_dict.get("year", "")
    record_dict[Fields.CITED_BY] = record_dict.get("citationCount", "")

    __assign_entrytype(record_dict=record_dict)
    if record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE:
        __assign_article_fields(record_dict=record_dict)

    elif record_dict[Fields.ENTRYTYPE] in [ENTRYTYPES.BOOK, ENTRYTYPES.INBOOK]:
        __assign_book_fields(record_dict=record_dict)

    elif record_dict[Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS:
        __assign_inproc_fields(record_dict=record_dict)

    return record_dict


def __remove_fields(*, record: dict) -> dict:
    """Method to remove unsupported fields from semanticscholar record"""

    record_dict = {k: v for k, v in record.items() if k in SUPPORTED_FIELDS and v != ""}

    return record_dict


def s2_dict_to_record(*, item: dict) -> dict:
    """Convert a semanticscholar item to a record dict"""

    try:
        record_dict = __item_to_record(item=item)
        record_dict = __remove_fields(record=record_dict)

    except (IndexError, KeyError) as exc:
        raise colrev_exceptions.RecordNotParsableException(
            f"Exception: Record not parsable: {exc}"
        ) from exc

    return record_dict
