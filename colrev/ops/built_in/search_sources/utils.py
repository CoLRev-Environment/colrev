#! /usr/bin/env python
"""Utility to transform crossref/doi.org items to records"""
from __future__ import annotations

import html
import re

# pylint: disable=duplicate-code


def __get_year(*, item: dict) -> str:
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


def __get_authors(*, item: dict) -> str:
    authors_strings = []
    for author in item.get("author", "NA"):
        a_string = ""
        if "family" in author:
            a_string += author["family"]
            if "given" in author:
                a_string += f", {author['given']}"
            authors_strings.append(a_string)
    return " and ".join(authors_strings)


def __get_number(*, item: dict) -> str:
    if "journal-issue" in item:
        if "issue" in item["journal-issue"]:
            item["issue"] = item["journal-issue"]["issue"]
    return str(item.get("issue", ""))


def __get_fulltext(*, item: dict) -> str:
    fulltext_link = ""
    # Note : better use the doi-link resolution
    fulltext_link_l = [
        u["URL"] for u in item.get("link", []) if "pdf" in u["content-type"]
    ]
    if len(fulltext_link_l) == 1:
        fulltext_link = fulltext_link_l.pop()
    return fulltext_link


def __item_to_record(*, item: dict) -> dict:
    # Note: the format differst between crossref and doi.org

    if isinstance(item["title"], list):
        item["title"] = str(item["title"][0])
    assert isinstance(item["title"], str)

    if isinstance(item.get("container-title", ""), list):
        item["container-title"] = item["container-title"][0]
    assert isinstance(item.get("container-title", ""), str)

    item["ENTRYTYPE"] = "misc"
    if item.get("type", "NA") == "journal-article":
        item.update(ENTRYTYPE="article")
        item.update(journal=item.get("container-title", ""))
    elif item.get("type", "NA") == "proceedings-article":
        item.update(ENTRYTYPE="inproceedings")
        item.update(booktitle=item.get("container-title", ""))
    elif item.get("type", "NA") == "book":
        item.update(ENTRYTYPE="book")
        item.update(series=item.get("container-title", ""))

    item.update(author=__get_authors(item=item))
    item.update(year=__get_year(item=item))
    item.update(volume=str(item.get("volume", "")))
    item.update(number=__get_number(item=item))
    item.update(pages=item.get("page", "").replace("-", "--"))
    item.update(cited_by=item.get("is-referenced-by-count", ""))
    item.update(doi=item.get("DOI", "").upper())
    item.update(fulltext=__get_fulltext(item=item))

    return item


def __flag_retracts(*, record_dict: dict) -> dict:
    if "update-to" in record_dict:
        for update_item in record_dict["update-to"]:
            if update_item["type"] == "retraction":
                record_dict["warning"] = "retracted"
    if "(retracted)" in record_dict.get("title", "").lower():
        record_dict["warning"] = "retracted"
    return record_dict


def __format_fields(*, record_dict: dict) -> dict:
    for key, value in record_dict.items():
        record_dict[key] = str(value).replace("{", "").replace("}", "")
        if key in ["colrev_masterdata_provenance", "colrev_data_provenance", "doi"]:
            continue
        # Note : some dois (and their provenance) contain html entities
        if not isinstance(value, str):
            continue
        value = value.replace("<scp>", "{")
        value = value.replace("</scp>", "}")
        record_dict[key] = html.unescape(str(value))
        value = value.replace("\n", " ")
        value = re.sub(r"<\/?[^>]*>", " ", value)
        value = re.sub(r"<\/?jats\:[^>]*>", " ", value)
        value = re.sub(r"\s+", " ", value).rstrip().lstrip()
        record_dict[key] = value

    return record_dict


def __set_forthcoming(*, record_dict: dict) -> dict:
    if (
        not any(x in record_dict for x in ["published-print", "published"])
        and "year" in record_dict
    ):
        record_dict.update(published_online=record_dict["year"])
        record_dict.update(year="forthcoming")
    return record_dict


def __remove_fields(*, record_dict: dict) -> dict:
    # Drop empty and non-supported fields
    supported_fields = [
        "ENTRYTYPE",
        "ID",
        "title",
        "author",
        "year",
        "journal",
        "booktitle",
        "volume",
        "number",
        "pages",
        "doi",
        "fulltext",
        "abstract",
        "warning",
        "language",
    ]
    record_dict = {
        k: v for k, v in record_dict.items() if k in supported_fields and v != ""
    }

    return record_dict


def json_to_record(*, item: dict) -> dict:
    """Convert a crossref item to a record dict"""

    record_dict = __item_to_record(item=item)
    record_dict = __set_forthcoming(record_dict=record_dict)
    record_dict = __flag_retracts(record_dict=record_dict)
    record_dict = __format_fields(record_dict=record_dict)
    record_dict = __remove_fields(record_dict=record_dict)

    return record_dict


if __name__ == "__main__":
    pass
