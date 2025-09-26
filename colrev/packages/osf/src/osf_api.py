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
        return string: Results from API"""

        response = requests.get(url, headers=self.headers, timeout=60)
        return response.text

    # pylint: disable=broad-exception-caught
    def _resolve_authors(self, record: dict) -> None:
        """Resolve OSF authors for a single record (in place).

        Replaces record[Fields.AUTHOR] (contributors URL) with a BibTeX-style string
        'Family, Given and Family, Given'. Guarantees the URL is not kept:
        - prefer unregistered_contributor
        - otherwise fetch user by id (relationships.users.data.id)
        - fallback: user id string
        - if nothing at all is found, drop the AUTHOR field
        """
        href = record.get(Fields.AUTHOR)
        if not href or not isinstance(href, str):
            return

        def _name_from_attrs(uattr: dict) -> str:
            given = (uattr.get("given_name") or "").strip()
            family = (uattr.get("family_name") or "").strip()
            full = (uattr.get("full_name") or "").strip()
            if family and given:
                return f"{family}, {given}"
            return full or (given or family) or ""

        def _fetch_user_attrs(uid: str) -> dict:
            if not uid:
                return {}
            if uid in self._user_cache:
                return self._user_cache[uid]
            url = f"https://api.osf.io/v2/users/{uid}/"
            try:
                # keep it simple; no fields filter to avoid oddities
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

        try:
            # Pull only bibliographic contributors
            sep = "&" if "?" in href else "?"
            url = f"{href}{sep}filter[bibliographic]=true"

            names: list[str] = []
            id_fallbacks: list[str] = []

            while url:
                js = json.loads(self._query_api(url))
                for item in js.get("data", []):
                    attr = item.get("attributes") or {}
                    if attr.get("bibliographic") is False:
                        continue

                    # 1) unregistered contributor name (verbatim)
                    name = (attr.get("unregistered_contributor") or "").strip()

                    # 2) registered user via id
                    if not name:
                        rel = (item.get("relationships") or {}).get("users") or {}
                        rel_data = rel.get("data") or {}
                        uid = rel_data.get("id") if isinstance(rel_data, dict) else None
                        if uid:
                            uattrs = _fetch_user_attrs(uid)
                            name = _name_from_attrs(uattrs)
                            if not name:
                                # keep uid as a safe fallback
                                id_fallbacks.append(uid)

                    if name:
                        names.append(name)

                # paginate
                links = js.get("links") or {}
                url = links.get("next", "")

            # Always overwrite AUTHOR (never keep the URL):
            if names:
                record[Fields.AUTHOR] = " and ".join(names)
            elif id_fallbacks:
                record[Fields.AUTHOR] = " and ".join(id_fallbacks)
            else:
                # nothing found—drop the field to avoid leaving a URL around
                record.pop(Fields.AUTHOR, None)

        except Exception:
            # On hard failures, fall back to user ids if we can extract them without extra calls
            try:
                # last-chance: fetch once without filters and try to read ids
                js = json.loads(self._query_api(href))
                ids = []
                for item in js.get("data", []):
                    if (item.get("attributes") or {}).get("bibliographic") is False:
                        continue
                    rel = (item.get("relationships") or {}).get("users") or {}
                    rel_data = rel.get("data") or {}
                    uid = rel_data.get("id") if isinstance(rel_data, dict) else None
                    if uid:
                        ids.append(uid)
                if ids:
                    record[Fields.AUTHOR] = " and ".join(ids)
                else:
                    record.pop(Fields.AUTHOR, None)
            except Exception:
                record.pop(Fields.AUTHOR, None)

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
        """Check if all pages have been completed"""
        return self.next_url is None
