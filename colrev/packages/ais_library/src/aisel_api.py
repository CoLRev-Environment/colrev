#! /usr/bin/env python
"""AISeL API client."""
from __future__ import annotations

import typing
import urllib.parse

import requests

import colrev.loader.load_utils
import colrev.search_file
from colrev.packages.ais_library.src import ais_load_utils


class AISeLAPIError(Exception):
    """Exception raised when AISeL requests fail."""


# pylint: disable=too-few-public-methods
class AISeLAPI:
    """Handle HTTP interactions with the AISeL platform."""

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        session: typing.Optional[requests.Session] = None,
        headers: typing.Optional[typing.Dict[str, str]] = None,
    ) -> None:
        self.search_file = search_file
        self.session = session or requests.Session()
        self.headers = headers or {}

    def _get(self, url: str, *, timeout: int) -> requests.Response:
        """Execute a GET request and raise a custom exception on failure."""

        try:
            response = self.session.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            raise AISeLAPIError from exc

    def get_ais_query_return(self) -> list:
        """Execute a search query and return the results as records."""

        def query_from_params(params: dict) -> str:

            final = ""
            if isinstance(params["query"], str):
                final = params["query"]
            else:
                for i in params["query"]:
                    final = f"{final} {i['operator']} {i['field']}:{i['term']}".strip()
                    final = final.replace("All fields:", "")

            if "start_date" in params["query"]:
                final = f"{final}&start_date={params['query']['start_date']}"

            if "end_date" in params["query"]:
                final = f"{final}&end_date={params['query']['end_date']}"

            if "peer_reviewed" in params["query"]:
                final = f"{final}&peer_reviewed=true"

            return urllib.parse.quote(final)

        final_q = query_from_params(self.search_file.search_parameters)

        query_string = (
            "https://aisel.aisnet.org/do/search/results/refer?"
            + "start=0&context=509156&sort=score&facet=&dlt=Export122204"
        )
        query_string = f"{query_string}&q={final_q}"

        response = self._get(query_string, timeout=300)

        # Note: the following writes the enl to the feed file (bib).
        # This file is replaced by ais_feed.save()

        records = colrev.loader.load_utils.loads(
            response.text,
            implementation="enl",
            id_labeler=ais_load_utils.enl_id_labeler,
            entrytype_setter=ais_load_utils.enl_entrytype_setter,
            field_mapper=ais_load_utils.enl_field_mapper,
            # logger=self.logger,
        )

        return list(records.values())
