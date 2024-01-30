"""Utility to transform items from semanticscholar into records"""
from __future__ import annotations

from semanticscholar import Paper

import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


# pylint: disable=duplicate-code


def __get_authors(record: dict) -> str:
    """Method to extract authors from item"""
    authors_list = []
    record_authors = record.get("authors")

    if record_authors:
        for author in record_authors:
            if "name" in author:
                authors_list.append(author["name"])
        return " and ".join(authors_list)

    return "n/a"


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


def __items_from_publication_venue(*, record_dict: dict) -> dict:
    """Method to extract data from publication venue"""
    record_dict[Fields.ENTRYTYPE] = record_dict.get("publicationVenue", "n/a")
    if record_dict["publicationVenue"]:
        if isinstance(record_dict[Fields.ENTRYTYPE], dict):
            if "issn" in record_dict[Fields.ENTRYTYPE]:
                record_dict[Fields.ISSN] = record_dict[Fields.ENTRYTYPE]["issn"]
            if "type" in record_dict[Fields.ENTRYTYPE]:
                for key, value in record_dict[Fields.ENTRYTYPE].items():
                    if key == "type":
                        record_dict[Fields.ENTRYTYPE] = __convert_entry_types(
                            entrytype=value.lower().replace(" ", "")
                        )

    if not record_dict[Fields.ENTRYTYPE]:
        record_dict[Fields.ENTRYTYPE] = record_dict.get("publicationTypes")

        if isinstance(record_dict[Fields.ENTRYTYPE], list):
            if len(record_dict[Fields.ENTRYTYPE]) > 0:
                record_dict[Fields.ENTRYTYPE] = (
                    record_dict[Fields.ENTRYTYPE][0].lower().replace(" ", "")
                )
            else:
                record_dict[Fields.ENTRYTYPE] = "n/a"
        record_dict[Fields.ENTRYTYPE] = __convert_entry_types(
            entrytype=str(record_dict.get("ENTRYTYPE"))
        )

    if "book" in record_dict[Fields.ENTRYTYPE]:
        record_dict[Fields.BOOKTITLE] = record_dict.get("journal")
        if record_dict[Fields.BOOKTITLE] and "name" in record_dict[Fields.BOOKTITLE]:
            record_dict[Fields.BOOKTITLE] = record_dict[Fields.BOOKTITLE]["name"]

    return record_dict


def __get_doi(*, record_dict: dict) -> dict:
    """Method to extract DOI from item"""
    record_dict[Fields.DOI] = record_dict.get("externalIds", "n/a")

    if isinstance(record_dict[Fields.DOI], dict):
        if len(record_dict[Fields.DOI]) > 0:
            record_dict[Fields.DOI] = record_dict[Fields.DOI].get("DOI", "n/a")
            if record_dict[Fields.DOI]:
                record_dict[Fields.DOI] = str(record_dict.get(Fields.DOI)).upper()
        else:
            record_dict[Fields.DOI] = "n/a"
    assert isinstance(record_dict.get("doi", ""), str)

    return record_dict


def __get_book_details(*, record_dict: dict) -> dict:
    """Method to extract pages and volume from item"""

    if "journal" in record_dict and isinstance(record_dict.get("journal"), dict):
        if "volume" in record_dict["journal"]:
            record_dict[Fields.VOLUME] = record_dict["journal"]["volume"]
        else:
            record_dict[Fields.VOLUME] = "n/a"

        if "pages" in record_dict["journal"]:
            record_dict[Fields.PAGES] = record_dict["journal"]["pages"]
        else:
            record_dict[Fields.PAGES] = "n/a"
    else:
        record_dict[Fields.VOLUME] = "n/a"
        record_dict[Fields.PAGES] = "n/a"

    return record_dict


def __get_fulltext(*, record_dict: dict) -> dict:
    """Method to extract fulltext from item"""

    record_dict[Fields.FULLTEXT] = record_dict.get("openAccessPdf")

    if isinstance(record_dict[Fields.FULLTEXT], dict):
        if len(record_dict[Fields.FULLTEXT]) > 0:
            record_dict[Fields.FULLTEXT] = record_dict[Fields.FULLTEXT]["url"]
        else:
            record_dict[Fields.FULLTEXT] = "n/a"
    assert isinstance(record_dict.get("FULLTEXT", ""), str)

    return record_dict


def __item_to_record(item: Paper) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""

    record_dict = dict(item)

    record_dict[Fields.COLREV_ID] = record_dict.get("paperId", "n/a")
    record_dict[Fields.ID] = record_dict.get("paperId", "n/a")
    record_dict = __get_doi(record_dict=record_dict)

    record_dict[Fields.URL] = record_dict.get("url", "n/a")
    record_dict[Fields.ISSN] = "n/a"

    record_dict = __items_from_publication_venue(record_dict=record_dict)

    record_dict[Fields.TITLE] = record_dict.get("title")
    record_dict[Fields.AUTHOR] = __get_authors(record=record_dict)
    record_dict[Fields.ABSTRACT] = record_dict.get("abstract")
    record_dict[Fields.YEAR] = record_dict.get("year")

    record_dict = __get_book_details(record_dict=record_dict)

    record_dict[Fields.JOURNAL] = record_dict.get("venue")
    record_dict[Fields.CITED_BY] = record_dict.get("citationCount")

    record_dict = __get_fulltext(record_dict=record_dict)

    return record_dict


def __remove_fields(*, record: dict) -> dict:
    """Method to remove unsupported fields from semanticscholar record"""
    supported_fields = [
        Fields.ID,
        Fields.COLREV_ID,
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
        # TO DO: Implement further functions, especially "remove fields":
        # Use colrev/colrev/ops/built_in/search_sources/utils.py as inspiration!

    except (IndexError, KeyError) as exc:
        raise colrev_exceptions.RecordNotParsableException(
            f"Exception: Record not parsable: {exc}"
        ) from exc

    return record_dict
