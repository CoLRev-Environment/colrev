#! /usr/bin/env python
"""Connector to doi.org (API)"""
from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep


def json_to_record(*, item: dict) -> dict:
    """Convert a crossref item to a record dict"""

    # pylint: disable=too-many-branches
    # pylint: disable=too-many-statements
    # pylint: disable=too-many-locals

    # Note: the format differst between crossref and doi.org
    record_dict: dict = {}

    # Note : better use the doi-link resolution
    if "link" in item:
        fulltext_link_l = [u["URL"] for u in item["link"] if "pdf" in u["content-type"]]
        if len(fulltext_link_l) == 1:
            record_dict["fulltext"] = fulltext_link_l.pop()
    #     item["link"] = [u for u in item["link"] if "pdf" not in u["content-type"]]
    #     if len(item["link"]) >= 1:
    #         link = item["link"][0]["URL"]
    #         if link != record_dict.get("fulltext", ""):
    #             record_dict["link"] = link

    if "title" in item:
        retrieved_title = ""
        if isinstance(item["title"], list):
            if len(item["title"]) > 0:
                retrieved_title = str(item["title"][0])
        elif isinstance(item["title"], str):
            retrieved_title = item["title"]

        if retrieved_title:
            retrieved_title = retrieved_title.replace("\n", " ")
            retrieved_title = retrieved_title.replace("<scp>", "{")
            retrieved_title = retrieved_title.replace("</scp>", "}")
            retrieved_title = re.sub(r"<\/?[^>]*>", " ", retrieved_title)
            retrieved_title = re.sub(r"\s+", " ", retrieved_title).rstrip().lstrip()
            record_dict.update(title=retrieved_title)

    container_title = ""
    if "container-title" in item:
        if isinstance(item["container-title"], list):
            if len(item["container-title"]) > 0:
                container_title = item["container-title"][0]
        elif isinstance(item["container-title"], str):
            container_title = item["container-title"]

    container_title = container_title.replace("\n", " ")
    container_title = re.sub(r"\s+", " ", container_title)
    if "type" in item:
        if "journal-article" == item.get("type", "NA"):
            record_dict.update(ENTRYTYPE="article")
            if container_title is not None:
                record_dict.update(journal=container_title)
        if "proceedings-article" == item.get("type", "NA"):
            record_dict.update(ENTRYTYPE="inproceedings")
            if container_title is not None:
                record_dict.update(booktitle=container_title)
        if "book" == item.get("type", "NA"):
            record_dict.update(ENTRYTYPE="book")
            if container_title is not None:
                record_dict.update(series=container_title)

    if "DOI" in item:
        record_dict.update(doi=item["DOI"].upper())

    authors_strings = []
    for author in item.get("author", "NA"):
        a_string = ""

        if "family" in author:
            a_string += author["family"]
            if "given" in author:
                a_string += f", {author['given']}"
            authors_strings.append(a_string)
    authors_string = " and ".join(authors_strings)
    authors_string = re.sub(r"\s+", " ", authors_string)

    # authors_string = PrepRecord.format_author_field(authors_string)
    record_dict.update(author=authors_string)

    try:
        if "published-print" in item:
            date_parts = item["published-print"]["date-parts"]
            record_dict.update(year=str(date_parts[0][0]))
        elif "published" in item:
            date_parts = item["published"]["date-parts"]
            record_dict.update(year=str(date_parts[0][0]))
        elif "published-online" in item:
            date_parts = item["published-online"]["date-parts"]
            record_dict.update(year=str(date_parts[0][0]))
    except KeyError:
        pass

    retrieved_pages = item.get("page", "")
    if retrieved_pages:
        # DOI data often has only the first page.
        if (
            not record_dict.get("pages", "no_pages") in retrieved_pages
            and "-" in retrieved_pages
        ):
            record_dict.update(pages=item["page"])
            record = colrev.record.PrepRecord(data=record_dict)
            record.unify_pages_field()
            record_dict = record.get_data()

    retrieved_volume = item.get("volume", "")
    if not retrieved_volume == "":
        record_dict.update(volume=str(retrieved_volume))

    retrieved_number = item.get("issue", "")
    if "journal-issue" in item:
        if "issue" in item["journal-issue"]:
            retrieved_number = item["journal-issue"]["issue"]
    if not retrieved_number == "":
        record_dict.update(number=str(retrieved_number))

    if "abstract" in item:
        retrieved_abstract = item["abstract"]
        if not retrieved_abstract == "":
            retrieved_abstract = re.sub(r"<\/?jats\:[^>]*>", " ", retrieved_abstract)
            retrieved_abstract = re.sub(r"\s+", " ", retrieved_abstract)
            retrieved_abstract = str(retrieved_abstract).replace("\n", "")
            retrieved_abstract = retrieved_abstract.lstrip().rstrip()
            record_dict.update(abstract=retrieved_abstract)

    if "language" in item:
        # Skip errors
        if item["language"] not in ["ng"]:
            record_dict["language"] = item["language"]
            # convert to ISO 639-3
            # gh_issue https://github.com/geritwagner/colrev/issues/64
            # other languages/more systematically
            if "en" == record_dict["language"]:
                record_dict["language"] = record_dict["language"].replace("en", "eng")

    if (
        not any(x in item for x in ["published-print", "published"])
        # and "volume" not in record_dict
        # and "number" not in record_dict
        and "year" in record_dict
    ):
        record_dict.update(published_online=record_dict["year"])
        record_dict.update(year="forthcoming")

    if "is-referenced-by-count" in item:
        record_dict["cited_by"] = item["is-referenced-by-count"]

    if "update-to" in item:
        for update_item in item["update-to"]:
            if update_item["type"] == "retraction":
                record_dict["warning"] = "retracted"

    for key, value in record_dict.items():
        record_dict[key] = str(value).replace("{", "").replace("}", "")
        if key in ["colrev_masterdata_provenance", "colrev_data_provenance", "doi"]:
            continue
        # Note : some dois (and their provenance) contain html entities
        record_dict[key] = html.unescape(str(value))

    if "ENTRYTYPE" not in record_dict:
        record_dict["ENTRYTYPE"] = "misc"

    return record_dict


if __name__ == "__main__":
    pass
