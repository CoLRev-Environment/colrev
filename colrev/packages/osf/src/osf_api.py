#!/usr/bin/env python3
"""OSF API Query class for querying the OSF API."""

import json
import typing

import requests

from colrev.constants import Fields

# pylint: disable=colrev-missed-constant-usage


class OSFApiQuery:
    """Class for querying the OSF API."""

    base_url = "https://api.osf.io/v2/nodes/?"
    fields = ["id", "type", "title", "year", "description", "tags", "date_created"]

    def __init__(self, *, parameters: dict, api_key: str) -> None:
        """Initialize the instance."""
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {self.api_key}"}
        self.params: typing.Dict[str, str] = {}
        self.next_url = None
        self.params = {
            key: value for key, value in parameters.items() if key in self.fields
        }

        # tiny cache for user lookups
        self._user_cache: dict = {}

    def _create_record_dict(self, item: dict) -> dict:
        attributes = item["attributes"]
        year = attributes["date_created"]
        url = item["links"]
        relationships = item["relationships"]
        contributors = relationships["contributors"]
        links = contributors["links"]
        related = links["related"]
        record_dict = {
            Fields.ID: item["id"],
            Fields.ENTRYTYPE: "misc",
            Fields.AUTHOR: related["href"],
            Fields.TITLE: attributes["title"],
            Fields.ABSTRACT: attributes["description"],
            Fields.KEYWORDS: ", ".join(attributes["tags"]),
            Fields.YEAR: year[:4],
            Fields.URL: url["self"],
        }
        # Drop empty fields
        record_dict = {k: v for k, v in record_dict.items() if v}
        return record_dict

    def _query_api(self, url: str) -> str:
        """Creates the URL for the API call
        string url  Full URL to pass to API
        return string: Results from API.
        """
        response = requests.get(url, headers=self.headers, timeout=60)
        return response.text

    def _resolve_authors(self, record: dict) -> None:
        """Resolve OSF authors for a single record (in place)."""
        href = record.get(Fields.AUTHOR)
        if not href or not isinstance(href, str):
            return

        names, id_fallbacks = self._resolve_contributor_authors(href)
        if names:
            record[Fields.AUTHOR] = " and ".join(names)
            return
        if id_fallbacks:
            record[Fields.AUTHOR] = " and ".join(id_fallbacks)
            return

        record.pop(Fields.AUTHOR, None)

    def _resolve_contributor_authors(self, href: str) -> tuple[list[str], list[str]]:
        sep = "&" if "?" in href else "?"
        url = f"{href}{sep}filter[bibliographic]=true"
        names: list[str] = []
        id_fallbacks: list[str] = []

        try:
            while url:
                js = json.loads(self._query_api(url))
                page_names, page_ids = self._extract_page_author_data(js)
                names.extend(page_names)
                id_fallbacks.extend(page_ids)
                links = js.get("links") or {}
                url = links.get("next", "")
        except Exception:
            return [], self._resolve_fallback_ids(href)

        return names, id_fallbacks

    def _extract_page_author_data(self, js: dict) -> tuple[list[str], list[str]]:
        names: list[str] = []
        id_fallbacks: list[str] = []
        for item in js.get("data", []):
            attr = item.get("attributes") or {}
            if attr.get("bibliographic") is False:
                continue

            name = (attr.get("unregistered_contributor") or "").strip()
            if not name:
                uid = self._get_contributor_user_id(item)
                if uid:
                    name = self._name_from_attrs(self._fetch_user_attrs(uid))
                    if not name:
                        id_fallbacks.append(uid)

            if name:
                names.append(name)

        return names, id_fallbacks

    def _get_contributor_user_id(self, item: dict) -> typing.Optional[str]:
        rel = (item.get("relationships") or {}).get("users") or {}
        rel_data = rel.get("data") or {}
        return rel_data.get("id") if isinstance(rel_data, dict) else None

    def _name_from_attrs(self, uattr: dict) -> str:
        given = (uattr.get("given_name") or "").strip()
        family = (uattr.get("family_name") or "").strip()
        full = (uattr.get("full_name") or "").strip()
        if family and given:
            return f"{family}, {given}"
        return full or (given or family) or ""

    # pylint: disable=broad-exception-caught
    def _fetch_user_attrs(self, uid: str) -> dict:
        if not uid:
            return {}
        if uid in self._user_cache:
            return self._user_cache[uid]
        url = f"https://api.osf.io/v2/users/{uid}/"
        try:
            js = json.loads(self._query_api(url))
            data = js.get("data", {})
            if isinstance(data, list):
                data = data[0] if data else {}
            attrs = (data.get("attributes") or {}) if isinstance(data, dict) else {}
            if attrs:
                self._user_cache[uid] = attrs
            return attrs
        except Exception:
            return {}

    # pylint: disable=broad-exception-caught
    def _resolve_fallback_ids(self, href: str) -> list[str]:
        try:
            js = json.loads(self._query_api(href))
            ids = []
            for item in js.get("data", []):
                if (item.get("attributes") or {}).get("bibliographic") is False:
                    continue
                uid = self._get_contributor_user_id(item)
                if uid:
                    ids.append(uid)
            return ids
        except Exception:
            return []

    def retrieve_records(self) -> typing.Generator:
        """Call the API with the query parameters and return the results."""
        if self.next_url is None:
            url = self._build_query()
        else:
            url = self.next_url

        data = self._query_api(url)
        response = json.loads(data)

        # Set the next URL for the next query
        links = response["links"]
        self.next_url = links["next"]

        articles = response.get("data", [])
        for article in articles:
            record = self._create_record_dict(article)
            self._resolve_authors(record)
            yield record

    def overall(self) -> int:
        """Return the overall number of records."""
        url = self._build_query()
        data = self._query_api(url)
        response = json.loads(data)

        links = response["links"]
        return links["meta"]["total"]

    def _build_query(self) -> str:
        """Creates the URL for querying the API with support for nested filter parameters."""
        filters = []
        # Add in filters with the correct formatting
        for key, value in self.params.items():
            filters.append(f"filter[{key}]={value}")

        url = self.base_url + "&".join(filters)

        return url

    def pages_completed(self) -> bool:
        """Check if all pages have been completed."""
        return self.next_url is None
