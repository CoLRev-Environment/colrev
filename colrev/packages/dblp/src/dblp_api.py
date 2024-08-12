#! /usr/bin/env python
"""DBLP API"""
import html
import json
import re
import typing
from sqlite3 import OperationalError

import requests

import colrev.exceptions as colrev_exceptions
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


# pylint: disable=too-few-public-methods


class DBLPAPI:
    """Connector for the DBLP API"""

    # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json
    _api_url_venues = "https://dblp.org/search/venue/api?q="
    _api_url = "https://dblp.org/search/publ/api?q="

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        email: str,
        session: requests.Session,
        query: typing.Optional[str] = None,
        url: typing.Optional[str] = None,
        timeout: int = 60,
    ):
        self.email = email
        self.session = session
        self._timeout = timeout

        assert query is not None or url is not None
        if query:
            self.set_url_from_query(query)

        elif url is not None and not url.startswith("http"):
            url = f"https://dblp.org/search/publ/api?q={url}"

        self.url = url

    def set_url_from_query(self, query: str) -> None:
        """Set the URL from a query"""
        query = re.sub(r"[\W]+", " ", query.replace(" ", "_").replace("-", "_"))
        self.url = self._api_url + query.replace(" ", "+") + "&format=json"

    def _get_dblp_venue(
        self,
        venue_string: str,
        *,
        venue_type: str,
    ) -> str:
        # Note : venue_string should be like "behaviourIT"
        # Note : journals that have been renamed seem to return the latest
        # journal name. Example:
        # https://dblp.org/db/journals/jasis/index.html
        venue = venue_string
        url = self._api_url_venues + venue_string.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
        try:
            ret = self.session.request(
                "GET", url, headers=headers, timeout=self._timeout
            )
            ret.raise_for_status()
            data = json.loads(ret.text)
            if "hit" not in data["result"]["hits"]:
                return ""
            hits = data["result"]["hits"]["hit"]
            for hit in hits:
                if hit["info"]["type"] != venue_type:
                    continue
                # pylint: disable=colrev-missed-constant-usage
                if f"/{venue_string.lower()}/" in hit["info"]["url"].lower():
                    venue = hit["info"]["venue"]
                    break

            venue = re.sub(r" \(.*?\)", "", venue)
        except requests.exceptions.RequestException:
            pass
        return venue

    def _dblp_json_set_type(self, *, item: dict) -> None:
        lpos = item["key"].find("/") + 1
        rpos = item["key"].rfind("/")
        ven_key = item["key"][lpos:rpos]

        if "corr" == ven_key:
            item[Fields.ENTRYTYPE] = ENTRYTYPES.TECHREPORT

        elif item["type"] == "Withdrawn Items":
            if item["key"][:8] == "journals":
                item["type"] = "Journal Articles"
            if item["key"][:4] == "conf":
                item["type"] = "Conference and Workshop Papers"
            item["colrev.dblp.warning"] = "Withdrawn (according to DBLP)"
        elif item["type"] == "Journal Articles":
            item[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
            item[Fields.JOURNAL] = self._get_dblp_venue(
                ven_key,
                venue_type="Journal",
            )
        elif item["type"] == "Conference and Workshop Papers":
            item[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
            item[Fields.BOOKTITLE] = self._get_dblp_venue(
                ven_key,
                venue_type="Conference or Workshop",
            )
        elif item["type"] == "Informal and Other Publications":
            item[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
            item[Fields.BOOKTITLE] = item["venue"]
        elif item["type"] == "Parts in Books or Collections":
            item[Fields.ENTRYTYPE] = ENTRYTYPES.INBOOK
            item[Fields.BOOKTITLE] = item["venue"]
        else:
            item[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
            if item["type"] != "Editorship":
                print("DBLP: Unknown type: %s", item)

    def _dblp_json_to_dict(
        self,
        *,
        item: dict,
    ) -> dict:
        # pylint: disable=too-many-branches
        # To test in browser:
        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        self._dblp_json_set_type(item=item)
        if "title" in item:
            item[Fields.TITLE] = item["title"].rstrip(".").rstrip().replace("\n", " ")
            item[Fields.TITLE] = re.sub(r"\s+", " ", item[Fields.TITLE])
        # Note : DBLP provides number-of-pages (instead of pages start-end)
        # if "pages" in item:
        #     item[Fields.PAGES] = item[Fields.PAGES].replace("-", "--")
        if "authors" in item:
            if Fields.AUTHOR in item["authors"]:
                if isinstance(item["authors"][Fields.AUTHOR], dict):
                    author_string = item["authors"][Fields.AUTHOR]["text"]
                else:
                    authors_nodes = [
                        author
                        for author in item["authors"][Fields.AUTHOR]
                        if isinstance(author, dict)
                    ]
                    authors = [x["text"] for x in authors_nodes if "text" in x]
                    author_string = " and ".join(authors)
                author_string = (
                    colrev.record.record_prep.PrepRecord.format_author_field(
                        author_string
                    )
                )
                item[Fields.AUTHOR] = author_string

        if "key" in item:
            item["dblp_key"] = "https://dblp.org/rec/" + item["key"]

        if Fields.DOI in item:
            item[Fields.DOI] = item[Fields.DOI].upper()
        if "ee" in item:
            if not any(
                x in item["ee"] for x in ["https://doi.org", "https://dblp.org"]
            ):
                item[Fields.URL] = item["ee"]
        if Fields.URL in item:
            if "https://dblp.org" in item[Fields.URL]:
                del item[Fields.URL]

        item = {
            k: v
            for k, v in item.items()
            if k not in ["venue", "type", "access", "key", "ee", "authors"]
        }
        for key, value in item.items():
            item[key] = html.unescape(value).replace("{", "").replace("}", "")

        return item

    def retrieve_records(self) -> list:
        """Retrieve records from DBLP"""

        try:
            headers = {"user-agent": f"{__name__}  (mailto:{self.email})"}
            # review_manager.logger.debug(url)
            ret = self.session.request(
                "GET", self.url, headers=headers, timeout=self._timeout  # type: ignore
            )
            ret.raise_for_status()
            if ret.status_code == 500:
                return []

            data = json.loads(ret.text)
            if "hits" not in data["result"]:
                return []
            if "hit" not in data["result"]["hits"]:
                return []
            hits = data["result"]["hits"]["hit"]
            items = [hit["info"] for hit in hits]

            dblp_dicts = [
                self._dblp_json_to_dict(
                    item=item,
                )
                for item in items
            ]
            retrieved_records = [
                colrev.record.record_prep.PrepRecord(dblp_dict)
                for dblp_dict in dblp_dicts
            ]

            for retrieved_record in retrieved_records:
                retrieved_record.add_provenance_all(
                    source=retrieved_record.data["dblp_key"]
                )

        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc
        except (requests.exceptions.ReadTimeout, requests.exceptions.HTTPError) as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "requests timed out "
                "(possibly because the DBLP service is temporarily not available)"
            ) from exc

        return retrieved_records
