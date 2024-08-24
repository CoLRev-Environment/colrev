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

# pylint: disable=duplicate-code

TAG_RE = re.compile(r"<[a-z/][^<>]{0,12}>")


def _get_year(*, item: dict) -> str:
    year = "-1"
    try:
        if "published-print" in item:
            date_parts = item["published-print"]["date-parts"]
        elif "published" in item:
            date_parts = item["published"]["date-parts"]
        elif "published-online" in item:
            date_parts = item["published-online"]["date-parts"]
        else:
            return ""
        year = str(date_parts[0][0])
    except KeyError:
        pass
    return year


# pylint: disable=colrev-missed-constant-usage
def _get_authors(*, item: dict) -> str:
    authors_strings = []
    for author in item.get("author", "NA"):
        a_string = ""
        if "family" in author:
            a_string += author["family"]
            if "given" in author:
                a_string += f", {author['given']}"
            authors_strings.append(a_string)
    return " and ".join(authors_strings).replace(",,", ",")


def _get_number(*, item: dict) -> str:
    if "journal-issue" in item:
        if "issue" in item["journal-issue"]:
            item["issue"] = item["journal-issue"]["issue"]
    return str(item.get("issue", ""))


def _get_fulltext(*, item: dict) -> str:
    fulltext_link = ""
    # Note : better use the doi-link resolution
    fulltext_link_l = [
        u["URL"] for u in item.get("link", []) if "pdf" in u["content-type"]
    ]
    if len(fulltext_link_l) == 1:
        fulltext_link = fulltext_link_l.pop()
    return fulltext_link


# pylint: disable=colrev-missed-constant-usage
def _item_to_record(*, item: dict) -> dict:
    # Note: the format differst between crossref and doi.org

    if isinstance(item["title"], list):
        item[Fields.TITLE] = str(item["title"][0])
    assert isinstance(item[Fields.TITLE], str)

    if isinstance(item.get("container-title", ""), list):
        if len(item["container-title"]) > 0:
            item["container-title"] = item["container-title"][0]
        else:
            item["container-title"] = ""
    assert isinstance(item.get("container-title", ""), str)

    item[Fields.ENTRYTYPE] = "misc"
    if item.get("type", "NA") == "journal-article":
        item[Fields.ENTRYTYPE] = "article"
        item[Fields.JOURNAL] = item.get("container-title", "")
    elif item.get("type", "NA") == "proceedings-article":
        item[Fields.ENTRYTYPE] = "inproceedings"
        item[Fields.BOOKTITLE] = item.get("container-title", "")
    elif item.get("type", "NA") == "book":
        item[Fields.BOOKTITLE] = "book"
        item[Fields.SERIES] = item.get("container-title", "")

    item[Fields.AUTHOR] = _get_authors(item=item)
    item[Fields.YEAR] = _get_year(item=item)
    item[Fields.VOLUME] = str(item.get(Fields.VOLUME, ""))
    item[Fields.NUMBER] = _get_number(item=item)
    item[Fields.PAGES] = item.get("page", "").replace("-", "--")
    item[Fields.CITED_BY] = item.get("is-referenced-by-count", "")
    item[Fields.DOI] = item.get("DOI", "").upper()
    item[Fields.FULLTEXT] = _get_fulltext(item=item)

    return item


def _flag_retracts(*, record_dict: dict) -> dict:
    if "update-to" in record_dict:
        for update_item in record_dict["update-to"]:
            if update_item["type"] == "retraction":
                record_dict[Fields.RETRACTED] = FieldValues.RETRACTED
    if "(retracted)" in record_dict.get(Fields.TITLE, "").lower():
        record_dict[Fields.RETRACTED] = FieldValues.RETRACTED
    return record_dict


def _format_fields(*, record_dict: dict) -> dict:
    for key, value in record_dict.items():
        record_dict[key] = str(value).replace("{", "").replace("}", "")
        # Note : some dois (and their provenance) contain html entities
        if key not in [
            Fields.AUTHOR,
            Fields.TITLE,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
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


def _set_forthcoming(*, record_dict: dict) -> dict:
    if not any(x in record_dict for x in ["published-print", "published"]) or not any(
        x in record_dict for x in [Fields.VOLUME, Fields.NUMBER]
    ):
        record_dict.update(year="forthcoming")
        if Fields.YEAR in record_dict:
            record_dict.update(published_online=record_dict[Fields.YEAR])
    return record_dict


def _remove_fields(*, record_dict: dict) -> dict:
    # Drop empty and non-supported fields
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
        == "No abstract is available for this article."
    ):
        del record_dict[Fields.ABSTRACT]

    return record_dict


def json_to_record(*, item: dict) -> colrev.record.record_prep.PrepRecord:
    """Convert a crossref item to a record dict"""

    try:
        record_dict = _item_to_record(item=deepcopy(item))
        record_dict = _set_forthcoming(record_dict=record_dict)
        record_dict = _flag_retracts(record_dict=record_dict)
        record_dict = _format_fields(record_dict=record_dict)
        record_dict = _remove_fields(record_dict=record_dict)
    except (IndexError, KeyError) as exc:
        raise colrev_exceptions.RecordNotParsableException(
            f"RecordNotParsableException: {exc}"
        ) from exc

    return colrev.record.record_prep.PrepRecord(record_dict)
