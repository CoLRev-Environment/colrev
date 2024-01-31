"""Utility to transform items from semanticscholar into records"""
from __future__ import annotations

import re

from semanticscholar import Paper

import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.record import PrepRecord as prep_record

# pylint: disable=duplicate-code


def __get_authors(record: dict) -> str:
    """Method to extract authors from item"""
    authors_list = []
    author_string = ""
    record_authors = record.get("authors")

    if record_authors:
        for author in record_authors:
            if "name" in author:
                authors_list.append(author["name"])
        author_string = " and ".join(authors_list)
        author_string = prep_record.format_author_field(input_string=author_string)

    return author_string


def __convert_entry_types(*, entrytype: str) -> str:
    """Method to convert semanticscholar entry types to colrev entry types"""

    if entrytype in ("journalarticle", "journal"):
        return ENTRYTYPES.ARTICLE
    if entrytype == "book":
        return ENTRYTYPES.BOOK
    if entrytype == "booksection":
        return ENTRYTYPES.INBOOK
    if entrytype == "casereport":
        return ENTRYTYPES.TECHREPORT
    if entrytype == "conference":
        return ENTRYTYPES.INPROCEEDINGS
    return ENTRYTYPES.MISC


def __get_entrytype_and_issn(*, record_dict: dict) -> dict:
    """Method to extract data from publication venue"""
    record_dict[Fields.ENTRYTYPE] = ""
    entrytype_dict = record_dict.get("publicationVenue", "")
    if entrytype_dict:
        if isinstance(entrytype_dict, dict):
            if "issn" in entrytype_dict:
                record_dict[Fields.ISSN] = entrytype_dict["issn"]
            if "type" in entrytype_dict:
                for key, value in entrytype_dict.items():
                    if key == "type":
                        record_dict[Fields.ENTRYTYPE] = __convert_entry_types(
                            entrytype=value.lower().replace(" ", "")
                        )

    if not record_dict[Fields.ENTRYTYPE]:
        entrytype_list = record_dict.get("publicationTypes", "")

        if isinstance(entrytype_list, list):
            if len(entrytype_list) > 0:
                entrytype_list = entrytype_list[0].lower().replace(" ", "")
            else:
                entrytype_list = [""]
        record_dict[Fields.ENTRYTYPE] = __convert_entry_types(
            entrytype=str(entrytype_list)
        )

    return record_dict


def __get_doi(*, record_dict: dict) -> dict:
    """Method to extract DOI from item"""
    record_dict[Fields.DOI] = record_dict.get("externalIds", "")

    if isinstance(record_dict[Fields.DOI], dict):
        if len(record_dict[Fields.DOI]) > 0:
            record_dict[Fields.DOI] = record_dict[Fields.DOI].get("DOI", "")
            if record_dict[Fields.DOI]:
                record_dict[Fields.DOI] = str(record_dict.get(Fields.DOI)).upper()
        else:
            record_dict[Fields.DOI] = ""
    assert isinstance(record_dict.get("doi", ""), str)

    return record_dict


def ___get_volume_and_pages(*, record_dict: dict) -> dict:
    """Method to extract pages and volume from item"""

    if "journal" in record_dict and isinstance(record_dict.get("journal"), dict):
        if "volume" in record_dict["journal"]:
            record_dict[Fields.VOLUME] = record_dict["journal"]["volume"]
        if "pages" in record_dict["journal"]:
            pages = record_dict["journal"]["pages"]
            if "-" in pages:
                pages = re.sub(r"\s+|[a-zA-Z]+", "", pages)
                pages_list = pages.split("-")
                a = int(pages_list[0])
                b = int(pages_list[1])
                if a > b:
                    pages = str(b) + "-" + str(a)
                elif a == b:
                    pages = str(a)

            record_dict[Fields.PAGES] = pages

    return record_dict


def __get_book_details(*, record_dict: dict) -> dict:
    """Method to extract book specific details from item"""

    book_title = record_dict.get("journal", "")
    if book_title:
        if "name" in book_title:
            book_title = book_title["name"]
            title = record_dict[Fields.TITLE]

            if book_title and title:
                if (book_title in title) or (title in book_title):
                    if len(title) < len(book_title):
                        record_dict[Fields.TITLE] = book_title
                else:
                    record_dict[Fields.BOOKTITLE] = book_title

    return record_dict


def __get_fulltext(*, record_dict: dict) -> dict:
    """Method to extract fulltext from item"""

    record_dict[Fields.FULLTEXT] = record_dict.get("openAccessPdf")

    if isinstance(record_dict[Fields.FULLTEXT], dict):
        if len(record_dict[Fields.FULLTEXT]) > 0:
            record_dict[Fields.FULLTEXT] = record_dict[Fields.FULLTEXT]["url"]
        else:
            record_dict[Fields.FULLTEXT] = ""
    assert isinstance(record_dict.get("FULLTEXT", ""), str)

    return record_dict


def __item_to_record(item: Paper) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""

    record_dict = dict(item)

    record_dict = __get_entrytype_and_issn(record_dict=record_dict)
    record_dict[Fields.TITLE] = record_dict.get("title", "")
    record_dict = ___get_volume_and_pages(record_dict=record_dict)

    if "book" in record_dict[Fields.ENTRYTYPE]:
        record_dict = __get_book_details(record_dict=record_dict)
        record_dict[Fields.JOURNAL] = ""
    else:
        record_dict[Fields.JOURNAL] = record_dict.get("venue", "")

    abstract = record_dict.get("abstract", "")
    if not abstract:
        record_dict[Fields.ABSTRACT] = ""
    else:
        record_dict[Fields.ABSTRACT] = abstract

    record_dict[Fields.AUTHOR] = __get_authors(record=record_dict)
    record_dict[Fields.YEAR] = record_dict.get("year", "")
    record_dict[Fields.CITED_BY] = record_dict.get("citationCount", "")
    record_dict = __get_fulltext(record_dict=record_dict)
    record_dict = __get_doi(record_dict=record_dict)
    record_dict[Fields.SEMANTIC_SCHOLAR_ID] = record_dict.get("paperId", "")
    record_dict[Fields.URL] = record_dict.get("url", "")

    return record_dict


def __remove_fields(*, record: dict) -> dict:
    """Method to remove unsupported fields from semanticscholar record"""
    supported_fields = [
        Fields.ID,
        Fields.SEMANTIC_SCHOLAR_ID,
        Fields.DOI,
        Fields.URL,
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

    record_dict = {k: v for k, v in record.items() if k in supported_fields and v != ""}

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
