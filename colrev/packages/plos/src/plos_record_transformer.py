#! /usr/bin/env python
"""Utility to transform crossref/doi.org items to records"""
from __future__ import annotations

import html
import re
from copy import deepcopy

import colrev.exceptions as colrev_exceptions
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import Fields
from colrev.constants import FieldValues
import logging

# pylint: disable=duplicate-code

TAG_RE = re.compile(r"<[a-z/][^<>]{0,12}>")

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


def json_to_record(*, item: dict) -> colrev.record.record_prep.PrepRecord:
    "Coonvert a PLOS item to a record dict"

    try{
        record_dict = _item_to_record(item=deepcopy(item))
        record_dict = _set_forthcoming(record_dict=record_dict)
        record_dict = _flag_retracts(record_dict=record_dict)
        record_dict = _format_fields(record_dict=record_dict)
        record_dict = _remove_fields(record_dict=record_dict)
    }