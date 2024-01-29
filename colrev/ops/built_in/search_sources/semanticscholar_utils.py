"""Utility to transform items from semanticscholar into records"""
from __future__ import annotations

import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


# pylint: disable=duplicate-code


def __get_authors(*, record: dict) -> str:
    authors_list = []
    for author in record.get("authors"):
        if "name" in author:
            authors_list.append(author["name"])
    return " and ".join(authors_list)


def __convert_entry_types(*, entrytype: str) -> ENTRYTYPES:
    """Method to convert semanticscholar entry types to colrev entry types"""

    if entrytype == "journalarticle" or entrytype == "journal":
        return ENTRYTYPES.ARTICLE
    elif entrytype == "book":
        return ENTRYTYPES.BOOK
    elif entrytype == "booksection":
        return ENTRYTYPES.INBOOK
    elif entrytype == "casereport":
        return ENTRYTYPES.TECHREPORT
    elif entrytype == "conference":
        return ENTRYTYPES.INPROCEEDINGS
    else:
        return ENTRYTYPES.MISC


def __item_to_record(*, item) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""

    record_dict = dict(item)
    is_book = False

    record_dict[Fields.ID] = record_dict.get("paperId", "n/a")
    record_dict[Fields.DOI] = record_dict.get("externalIds", "n/a")

    if isinstance(record_dict[Fields.DOI], dict):
        if len(record_dict[Fields.DOI]) > 0:
            record_dict[Fields.DOI] = record_dict[Fields.DOI].get("DOI", "n/a")
        else:
            record_dict[Fields.DOI] = "n/a"
    assert isinstance(record_dict.get("doi", ""), str)

    record_dict[Fields.URL] = record_dict.get("url", "n/a")
    record_dict[Fields.ENTRYTYPE] = record_dict.get("publicationVenue", "n/a")
    record_dict[Fields.ISSN] = "n/a"

    if record_dict[Fields.ENTRYTYPE] and record_dict[Fields.ENTRYTYPE] != "n/a":
        if isinstance(record_dict[Fields.ENTRYTYPE], dict):
            if "issn" in record_dict[Fields.ENTRYTYPE]:
                record_dict[Fields.ISSN] = record_dict[Fields.ENTRYTYPE]["issn"]

            if "type" in record_dict[Fields.ENTRYTYPE]:
                for key, value in record_dict.get("ENTRYTYPE").items():
                    if key == "Book":
                        is_book = True

                    if key == "type":
                        record_dict[Fields.ENTRYTYPE] = __convert_entry_types(
                            entrytype=value.lower().replace(" ", "")
                        )

    if record_dict[Fields.ENTRYTYPE] != ENTRYTYPES.INPROCEEDINGS:
        record_dict[Fields.ENTRYTYPE] = record_dict.get("publicationTypes")
        if record_dict[Fields.ENTRYTYPE] and "Book" in record_dict[Fields.ENTRYTYPE]:
            is_book = True

        if isinstance(record_dict[Fields.ENTRYTYPE], list):
            if len(record_dict[Fields.ENTRYTYPE]) > 0:
                record_dict[Fields.ENTRYTYPE] = (
                    record_dict[Fields.ENTRYTYPE][0].lower().replace(" ", "")
                )
            else:
                record_dict[Fields.ENTRYTYPE] = "n/a"
        record_dict[Fields.ENTRYTYPE] = __convert_entry_types(
            entrytype=record_dict.get("ENTRYTYPE")
        )

    record_dict[Fields.TITLE] = record_dict.get("title")
    record_dict[Fields.AUTHOR] = __get_authors(record=record_dict)
    record_dict[Fields.ABSTRACT] = record_dict.get("abstract")
    record_dict[Fields.YEAR] = record_dict.get("year")

    if is_book:
        record_dict[Fields.BOOKTITLE] = record_dict.get("journal")
        if record_dict[Fields.BOOKTITLE] and "name" in record_dict[Fields.BOOKTITLE]:
            record_dict[Fields.BOOKTITLE] = record_dict[Fields.BOOKTITLE].get("name")

    if "journal" in record_dict and isinstance(record_dict.get("journal"), dict):
        if "volume" in record_dict.get("journal"):
            record_dict[Fields.VOLUME] = record_dict.get("journal")["volume"]
        else:
            record_dict[Fields.VOLUME] = "n/a"

        if "pages" in record_dict.get("journal"):
            record_dict[Fields.PAGES] = record_dict.get("journal")["pages"]
        else:
            record_dict[Fields.PAGES] = "n/a"
    else:
        record_dict[Fields.VOLUME] = "n/a"
        record_dict[Fields.PAGES] = "n/a"

    record_dict[Fields.JOURNAL] = record_dict.get("venue")
    record_dict[Fields.CITED_BY] = record_dict.get("citationCount")

    record_dict[Fields.FULLTEXT] = record_dict.get("openAccessPdf")
    if isinstance(record_dict[Fields.FULLTEXT], dict):
        if len(record_dict[Fields.FULLTEXT]) > 0:
            record_dict[Fields.FULLTEXT] = record_dict[Fields.FULLTEXT]["url"]
        else:
            record_dict[Fields.FULLTEXT] = "n/a"
    assert isinstance(record_dict.get("FULLTEXT", ""), str)

    return record_dict


def __remove_fields(*, record: dict) -> dict:
    """Method to remove unsupported fields from semanticscholar record"""
    supported_fields = [
        Fields.ID,
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
