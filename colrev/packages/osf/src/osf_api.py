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

    def retrieve_records(self) -> typing.List[dict]:
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
        return [self._create_record_dict(article) for article in articles]

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
