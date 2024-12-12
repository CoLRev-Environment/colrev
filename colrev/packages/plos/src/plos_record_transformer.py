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


def _get_author(*, item: dict) -> str:
    authors_display_list = item.get("author_display", [])
    
    if not authors_display_list:
        return ""

    if len(authors_display_list) == 1:
        return authors_display_list[0]

    return ", ".join(authors_display_list[:-1]) + " and " + authors_display_list[-1]



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