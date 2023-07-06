#! /usr/bin/env python
"""Connector to website (API)"""
from __future__ import annotations

import json
import re
from multiprocessing import Lock
from typing import Optional
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import requests

import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# Note: not implemented as a full search_source
# (including SearchSourcePackageEndpointInterface, packages_endpoints.json)


# pylint: disable=too-few-public-methods


class WebsiteConnector:
    """Connector for the Zotero translator for websites"""

    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.todo
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/website.py"
    )
    __requests_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36"
    }

    # pylint: disable=unused-argument

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        settings: Optional[dict] = None,
    ) -> None:
        self.zotero_lock = Lock()
        self.review_manager = review_manager

    def __set_url(
        self,
        *,
        record: colrev.record.Record,
        item: dict,
    ) -> None:
        if "url" not in item:
            return
        host = urlparse(item["url"]).hostname
        if host and host.endswith("doi.org"):
            record.data["doi"] = item["url"].replace("https://doi.org/", "")
            dummy_record = colrev.record.PrepRecord(data={"doi": record.data["doi"]})
            doi_connector.DOIConnector.get_link_from_doi(
                record=dummy_record,
                review_manager=self.review_manager,
            )
            if "https://doi.org/" not in dummy_record.data["url"]:
                record.data["url"] = dummy_record.data["url"]
        else:
            record.data["url"] = item["url"]

    def __set_keywords(self, *, record: colrev.record.Record, item: dict) -> None:
        if "tags" not in item or len(item["tags"]) == 0:
            return
        keywords = ", ".join([k["tag"] for k in item["tags"]])
        record.data["keywords"] = keywords

    def __set_author(self, *, record: colrev.record.Record, item: dict) -> None:
        if "creators" not in item:
            return
        author_str = ""
        for creator in item["creators"]:
            author_str += (
                " and "
                + creator.get("lastName", "")
                + ", "
                + creator.get("firstName", "")
            )
        author_str = author_str[5:]  # drop the first " and "
        record.data["author"] = author_str

    def __set_entrytype(self, *, record: colrev.record.Record, item: dict) -> None:
        record.data["ENTRYTYPE"] = "article"  # default
        if item.get("itemType", "") == "journalArticle":
            record.data["ENTRYTYPE"] = "article"
            if "publicationTitle" in item:
                record.data["journal"] = item["publicationTitle"]
            if "volume" in item:
                record.data["volume"] = item["volume"]
            if "issue" in item:
                record.data["number"] = item["issue"]
        if item.get("itemType", "") == "conferencePaper":
            record.data["ENTRYTYPE"] = "inproceedings"
            if "proceedingsTitle" in item:
                record.data["booktitle"] = item["proceedingsTitle"]

    def __set_title(self, *, record: colrev.record.Record, item: dict) -> None:
        if "title" not in item:
            return
        record.data["title"] = item["title"]

    def __set_doi(self, *, record: colrev.record.Record, item: dict) -> None:
        if "doi" not in item:
            return
        record.data["doi"] = item["doi"].upper()

    def __set_date(self, *, record: colrev.record.Record, item: dict) -> None:
        if "date" not in item:
            return
        year = re.search(r"\d{4}", item["date"])
        if year:
            record.data["year"] = year.group(0)

    def __set_pages(self, *, record: colrev.record.Record, item: dict) -> None:
        if "pages" not in item:
            return
        record.data["pages"] = item["pages"]

    def __update_record(
        self,
        record: colrev.record.Record,
        item: dict,
    ) -> None:
        record.data["ID"] = item["key"]
        self.__set_entrytype(record=record, item=item)
        self.__set_author(record=record, item=item)
        self.__set_title(record=record, item=item)
        self.__set_doi(record=record, item=item)
        self.__set_date(record=record, item=item)
        self.__set_pages(record=record, item=item)
        self.__set_url(record=record, item=item)
        self.__set_keywords(record=record, item=item)

    def retrieve_md_from_website(self, *, record: colrev.record.Record) -> None:
        """Retrieve the metadata the associated website (url) based on Zotero"""

        self.zotero_lock.acquire(timeout=60)

        zotero_translation_service = (
            self.review_manager.get_zotero_translation_service()
        )
        zotero_translation_service.start()
        try:
            content_type_header = {"Content-type": "text/plain"}
            headers = {**self.__requests_headers, **content_type_header}
            export = requests.post(
                "http://127.0.0.1:1969/web",
                headers=headers,
                data=record.data["url"],
                timeout=60,
            )

            if export.status_code != 200:
                self.zotero_lock.release()
                return

            items = json.loads(export.content.decode())
            if len(items) == 0:
                self.zotero_lock.release()
                return
            item = items[0]
            if item["title"] == "Shibboleth Authentication Request":
                self.zotero_lock.release()
                return

            self.__update_record(record=record, item=item)

        except (
            json.decoder.JSONDecodeError,
            UnicodeEncodeError,
            requests.exceptions.RequestException,
            KeyError,
        ):
            pass

        self.zotero_lock.release()
