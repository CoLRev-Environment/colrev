
"""Utility to transform items from semanticscholar into records"""

from __future__ import annotations

import html
import re

import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import ENTRYTYPES
from colrev.constants import FieldValues

#pylint: disable=duplicate-code

def __convert_entry_types(*, entrytype: str) -> ENTRYTYPES:
    """Method to convert semanticscholar entry types to colrev entry types"""
    
    if entrytype == "JournalArticle":
        return ENTRYTYPES.ARTICLE
    elif entrytype == "Book":
        return ENTRYTYPES.BOOK
    elif entrytype == "BookSection":
        return ENTRYTYPES.INBOOK
    elif entrytype == "CaseReport":
        return ENTRYTYPES.TECHREPORT
    else:
        return ENTRYTYPES.MISC


def __item_to_record(*, item) -> dict:
    """Method to convert the different fields and information within item to record dictionary"""
    
    record_dict = dict(item)

    record_dict[Fields.ID] = record_dict.get("paperId")
    record_dict[Fields.DOI] = record_dict.get("externalIds")

    if isinstance(record_dict[Fields.DOI], dict):
        if len(record_dict[Fields.DOI]) > 0:
            record_dict[Fields.DOI] = record_dict[Fields.DOI].get("DOI")
        else:
            record_dict[Fields.DOI] = "n/a"
    assert isinstance(record_dict.get("doi", ""), str)

    record_dict[Fields.ENTRYTYPE] = record_dict.get("publicationTypes")

    if isinstance(record_dict[Fields.ENTRYTYPE], list):
        if len(record_dict[Fields.ENTRYTYPE]) > 0:
            record_dict[Fields.ENTRYTYPE] = record_dict[Fields.ENTRYTYPE][0]
        else:
            record_dict[Fields.ENTRYTYPE] = "n/a"
    assert isinstance(record_dict.get("ENTRYTYPE", ""), str)

    record_dict[Fields.ENTRYTYPE] = __convert_entry_types(entrytype=record_dict.get("ENTRYTYPE"))

    # TO DO: Keep implementing further fields!!

    
    

def __remove_fields(*, record: dict) -> None:
    """Method to remove unsupported fields from semanticscholar record"""

def s2_dict_to_record(*, item: dict) -> dict:
    """Convert a semanticscholar item to a record dict"""

    try:
        record_dict = __item_to_record(item=item)
        __remove_fields(record=record_dict)
        #TO DO: Implement further functions, especially "remove fields": Use colrev/colrev/ops/built_in/search_sources/utils.py as inspiration!
    
    except (IndexError, KeyError) as exc:
        raise colrev_exceptions.RecordNotParsableException(
            f"Exception: Record not parsable: {exc}"
        ) from exc
    
    return record_dict
