#! /usr/bin/env python
"""Utility to transform plos/doi.org items to records"""
from __future__ import annotations

import html
import re
from copy import deepcopy
from datetime import datetime

import colrev.record.record
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues


TAG_RE = re.compile(r"<[a-z/][^<>]{0,12}>")


def _get_year(*, item: dict) -> str:

    if "publication_date" in item:
        return (item["publication_date"]).split("-")[0]

    return ""


def format_author(author: str) -> str:
    """Convert authors to colrev format"""
    particles = {"de", "del", "la", "van", "von", "der", "di", "da", "le"}

    if author.startswith("{{") and author.endswith("}}"):
        return author

    parts = author.split()
    if len(parts) < 2:
        return author

    last_name = parts[-1]

    first_names = " ".join(parts[:-1])

    if len(parts) > 2 and parts[-2].lower() in particles:
        last_name = f"{{{' '.join(parts[-2:])}}}"
        first_names = " ".join(parts[:-2])

    return f"{last_name}, {first_names}"


def _get_authors(*, item: dict) -> str:
    authors_display_list = item.get("author_display", [])

    if not authors_display_list:
        return ""

    formatted_authors = [format_author(author) for author in authors_display_list]

    return " and ".join(formatted_authors)


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
    record_dict = {
        k: v for k, v in record_dict.items() if k in supported_fields and v != ""
    }

    if (
        record_dict.get(Fields.ABSTRACT, "")
        == "No abstract is available for this articled."
    ):
        del record_dict[Fields.ABSTRACT]

    if not record_dict.get(Fields.VOLUME, ""):
        del record_dict[Fields.VOLUME]

    if not record_dict.get(Fields.NUMBER, ""):

        del record_dict[Fields.NUMBER]

    return record_dict


def _item_to_record(*, item: dict) -> dict:

    assert isinstance(item, dict), "The received objet is not a dictionary"

    if isinstance(item["title_display"], str):
        item[Fields.TITLE] = str(item["title_display"])
    assert isinstance(item.get("title_display"), str)

    item[Fields.JOURNAL] = item.get("journal", "")
    assert isinstance(item["journal"], str)

    item[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
    item[Fields.AUTHOR] = _get_authors(item=item)
    item[Fields.YEAR] = _get_year(item=item)
    item[Fields.VOLUME] = str(item.get(Fields.VOLUME, ""))
    item[Fields.NUMBER] = item.get("issue", "")
    item[Fields.DOI] = item.get("id", "").upper()
    item[Fields.JOURNAL] = item.get("journal", "")
    item[Fields.ABSTRACT] = item.get("abstract", "")[0]
    # item[Fields.FULLTEXT] = _get_fulltext(item=item)

    return item


def _set_forthcoming(*, record_dict: dict) -> dict:
    current_date = datetime.now().year
    if not any(
        date_key in record_dict
        for date_key in ["publication_date", "received_date", "accepted_date"]
    ):
        record_dict.update(year="unknown")
        return record_dict

    year_value = int(record_dict.get("year", -1))

    if year_value > current_date:
        record_dict.update(year="forthcoming")

    if "publication_date" not in record_dict and "accepted_date" in record_dict:
        record_dict.update(year="forthcoming")
        return record_dict

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
            value = value.replace("\\", "").replace("\n", "")

        record_dict[key] = value.lstrip().rstrip()

    return record_dict


def json_to_record(*, item: dict) -> colrev.record.record_prep.PrepRecord:
    "Convert a PLOS item to a record dict"
    try:
        record_dict = _item_to_record(item=deepcopy(item))
        record_dict = _set_forthcoming(record_dict=record_dict)
        record_dict = _flag_retracts(record_dict=record_dict)
        record_dict = _format_fields(record_dict=record_dict)
        record_dict = _remove_fields(record_dict=record_dict)
    except (IndexError, KeyError) as exc:
        raise colrev.exceptions.RecordNotParsableException(
            f"RecordNotParseableExcception: {exc}"
        ) from exc
    return colrev.record.record_prep.PrepRecord(record_dict)
