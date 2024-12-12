#! /usr/bin/env python
"""Utility to transform plos/doi.org items to records"""

from __future__ import annotations

import html
import re
from copy import deepcopy

import colrev.exceptions as colrev_exceptions
import colrev.record.record

import colrev.record.record_prep
from colrev.constants import Fields
from colrev.constants import FieldValues


TAG_RE = re.compile(r"<[a-z/][^<>]{0,12}>")


def _get_year(*, item: dict) -> str:
    year = "-1"

    if "publication_date" in "item":
        date = ([item]["publication_date"]).split("-")[0]

    
    else:
        return ""


def _get_authors(*, item: dict) -> str:
    authors_display_list = item.get("author_display", [])
    
    if not authors_display_list:
        return ""

    if len(authors_display_list) == 1:
        return authors_display_list[0]

    return ", ".join(authors_display_list[:-1]) + " and " + authors_display_list[-1]

def _item_to_record(*, item: dict) -> dict:
    #Equivalent to "title" in Crossref
    if "title_display" in item:
        item[Fields.TITLE] = str(item["title_display"])
    assert isinstance(item[Fields.TITLE], str)

    #Equivalent to "container-title" in Crossref
    # As in PLOS we do not have list for this field, we only
    # check if the field exists
    if "journal" not in item:
        item["journal"] = ""
    assert isinstance(item.get("container-title", ""), str)

    #Equivalent to "type" in Crossref
    item[Fields.TITLE] = "misc"
    if item.get("article_type", "NA") == "Research Article":
        item[Fields.ENTRYTYPE] = "article"
        item[Fields.JOURNAL] = item.get("journal", "")
    
    item[Fields.AUTHOR] = _get_authors(item=item) #To do
    item[Fields.YEAR] = _get_year(item=item) #To do
    item[Fields.VOLUME] = str(item.get[Fields.VOLUME], "")
    item[Fields.NUMBER] = _get_number(item=item) #To do
    item[Fields.DOI] = item.get("id", "").upper()
    item[Fields.FULLTEXT] = _get_fulltext(item=item) #To do

    return item

def _set_forthcoming(*, record_dict: dict) -> dict:
    if not "publication_date" in record_dict or not any(
        x in record_dict for x in [Fields.VOLUME, Fields.NUMBER]
    ):
        record_dict.update(year="forthcoming")

        #CHECK THIS FOR COLREV
        if Fields.YEAR in record_dict:
            record_dict.update(published_online=record_dict[Fields.YEAR])
    return record_dict

def _flag_retracts(*, record_dict: dict) -> dict:
    if "update-to" in record_dict:
        for update_item in record_dict["update-to"]:
            if update_item["type"] == "retraction":
                record_dict[Fields.RETRACTED] = FieldValues.RETRACTED
    if "(retracted)" in record_dict.get(Fields.TITLE, "").lower():
        record_dict[Fields.RETRACTED] = FieldValues.RETRACTED
    return record_dict

def _remove_fields(*, record_dict: dict) -> dict:
    supported_fields = [
        Fields.ENTRYTYPE,
        Fields.ID,
        Fields.TITLE,
        Fields.AUTHOR,
        Fields.YEAR,
        Fields.JOURNAL,
        Fields.BOOKTITLE,
        Fields.VOLUME,
        Fields.NUMBER,
        Fields.PAGES,
        Fields.DOI,
        Fields.FULLTEXT,
        Fields.ABSTRACT,
        "warning",
        Fields.LANGUAGE,
    ]

    record_dict = {k: v for k, v in record_dict.items() 
        if k in supported_fields and v != ""}

    if( record_dict.get(Fields.ABSTRACT, "")
     == "No abstract is available for this articled."):
        del record_dict[Fields.ABSTRACT]

    return record_dict
def _item_to_record(*, item: dict) -> dict:
    #Equivalent to "title" in Crossref
    if "title_display" in item:
        item[Fields.TITLE] = str(item["title_display"])
    assert isinstance(item[Fields.TITLE], str)

    #Equivalent to "container-title" in Crossref
    # As in PLOS we do not have list for this field, we only
    # check if the field exists
    if "journal" not in item:
        item["journal"] = ""
    assert isinstance(item.get("container-title", ""), str)

    #Equivalent to "type" in Crossref
    item[Fields.TITLE] = "misc"
    if item.get("article_type", "NA") == "Research Article":
        item[Fields.ENTRYTYPE] = "article"
        item[Fields.JOURNAL] = item.get("journal", "")
    
    item[Fields.AUTHOR] = _get_authors(item=item) #To do
    item[Fields.YEAR] = _get_year(item=item) #To do
    #item[Fields.VOLUME] = str(item.get[Fields.VOLUME], "")
    item[Fields.NUMBER] = item.get("eissn","")
    item[Fields.DOI] = item.get("id", "").upper()
    #item[Fields.FULLTEXT] = _get_fulltext(item=item) #To do

    return item

def _set_forthcoming(*, record_dict: dict) -> dict:
    if not "publication_date" in record_dict or not any(
        x in record_dict for x in [Fields.VOLUME, Fields.NUMBER]
    ):
        record_dict.update(year="forthcoming")

        #CHECK THIS FOR COLREV
        if Fields.YEAR in record_dict:
            record_dict.update(published_online=record_dict[Fields.YEAR])
    return record_dict

def _flag_retracts(*, record_dict: dict) -> dict:
    if "update-to" in record_dict:
        for update_item in record_dict["update-to"]:
            if update_item["type"] == "retraction":
                record_dict[Fields.RETRACTED] = FieldValues.RETRACTED
    if "(retracted)" in record_dict.get(Fields.TITLE, "").lower():
        record_dict[Fields.RETRACTED] = FieldValues.RETRACTED
    return record_dict

def _remove_fields(*, record_dict: dict) -> dict:
    supported_fields = [
        Fields.ENTRYTYPE,
        Fields.ID,
        Fields.TITLE,
        Fields.AUTHOR,
        Fields.YEAR,
        Fields.JOURNAL,
        Fields.BOOKTITLE,
        Fields.VOLUME,
        Fields.NUMBER,
        Fields.PAGES,
        Fields.DOI,
        Fields.FULLTEXT,
        Fields.ABSTRACT,
        "warning",
        Fields.LANGUAGE,
    ]

    record_dict = {k: v for k, v in record_dict.items() 
        if k in supported_fields and v != ""}

    if( record_dict.get(Fields.ABSTRACT, "")
     == "No abstract is available for this articled."):
        del record_dict[Fields.ABSTRACT]

    return record_dict



def _format_fields(*, record_dict: dict) -> dict:
    for key, value in record_dict.items():
        record_dict[key] = str(value).replace("{", "").replace("}", "")
        # Note : some dois (and their provenance) contain html entities
        if key not in [
            Fields.AUTHOR,
            Fields.TITLE,
            Fields.JOURNAL,
            Fields.ABSTRACT,
        ]:
            continue
        if not isinstance(value, str):
            continue
        value = value.replace("<scp>", "{")
        value = value.replace("</scp>", "}")
        value = html.unescape(value)
        value = re.sub(TAG_RE, " ", value)
        value = value.replace("\n", " ")
        value = re.sub(r"\s+", " ", value).rstrip().lstrip("▪ ")
        if key == Fields.ABSTRACT:
            if value.startswith("Abstract "):
                value = value[8:]
        record_dict[key] = value.lstrip().rstrip()

    return record_dict

def json_to_record(*, item: dict) -> colrev.record.record_prep.PrepRecord:
    "Coonvert a PLOS item to a record dict"

    try:
        record_dict = _item_to_record(item=deepcopy(item))
        record_dict = _set_forthcoming(record_dict=record_dict)
        record_dict = _flag_retracts(record_dict=record_dict)
        record_dict = _format_fields(record_dict=record_dict) #To do OLGA
        record_dict = _remove_fields(record_dict=record_dict)
    except(IndexError, KeyError) as exc:
        raise colrev.exceptions.RecordNotParsableException(
            f"RecordNotParseableExcception: {exc}"
        ) from exc

    return colrev.record.record_prep.PrepRecord(record_dict)