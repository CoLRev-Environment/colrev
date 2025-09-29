#! /usr/bin/env python
"""arXiv API helper."""
from __future__ import annotations

import typing

import feedparser
import requests

import colrev.exceptions as colrev_exceptions
from colrev.packages.arxiv.src import record_transformer

if typing.TYPE_CHECKING:
    import colrev.search_file


class ArxivAPIError(Exception):
    """Exception raised when arXiv requests fail."""


class ArxivAPI:
    """Handle HTTP interactions with the arXiv API."""

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        session: typing.Optional[requests.Session] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.search_file = search_file

    def check_availability(self, *, timeout: int) -> None:
        """Check the health endpoint of the arXiv API."""

        try:
            response = self.session.get(
                "https://export.arxiv.org/api/"
                + "query?search_query=all:electron&start=0&max_results=1",
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise ArxivAPIError from exc

    def _get_arxiv_ids(self, query: str, retstart: int) -> typing.List[dict]:
        url = (
            "https://export.arxiv.org/api/query?search_query="
            + f"all:{query}&start={retstart}&max_results=20"
        )
        feed = feedparser.parse(url)
        return feed["entries"]

    def get_arxiv_query_return(self) -> typing.Iterator[dict]:
        """Execute a search query and return the results as records."""
        params = self.search_file.search_parameters
        retstart = 0
        while True:
            try:
                entries = self._get_arxiv_ids(query=params["query"], retstart=retstart)
                if not entries:
                    break
                for entry in entries:
                    yield record_transformer.parse_record(entry)

                retstart += 20
            except requests.exceptions.JSONDecodeError as exc:
                # watch github issue:
                # https://github.com/fabiobatalha/crossrefapi/issues/46
                if "504 Gateway Time-out" in str(exc):
                    raise colrev_exceptions.ServiceNotAvailableException(
                        "Crossref (check https://status.crossref.org/)"
                    )
                raise colrev_exceptions.ServiceNotAvailableException(
                    f"Crossref (check https://status.crossref.org/) ({exc})"
                )

    # def _arxiv_query_id(
    #     self,
    #     *,
    #     arxiv_id: str,
    #     timeout: int = 60,
    # ) -> dict:
    #     """Retrieve records from ArXiv based on a query"""

    #     # Query using ID List prefix ?? - wo hast du das gefunden?
    #     try:
    #         prefix = "id_list"
    #         url = (
    #             "https://export.arxiv.org/api/query?search_query="
    #             + f"list={prefix}:&id={arxiv_id}"
    #         )

    #         headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
    #         session = colrev.utils.get_cached_session()

    #         # self.logger.debug(url)
    #         ret = session.request("GET", url, headers=headers, timeout=timeout)
    #         ret.raise_for_status()
    #         if ret.status_code != 200:
    #             # self.logger.debug(
    #             #     f"crossref_query failed with status {ret.status_code}"
    #             # )
    #             return {"arxiv_id": arxiv_id}

    #         input(str.encode(ret.text))
    #         root = fromstring(str.encode(ret.text))
    #         retrieved_record = self._arxiv_xml_to_record(root=root)
    #         if not retrieved_record:
    #             return {"arxiv_id": arxiv_id}
    #     except requests.exceptions.RequestException:
    #         return {"arxiv_id": arxiv_id}
    #     # pylint: disable=duplicate-code
    #     except OperationalError as exc:
    #         raise colrev_exceptions.ServiceNotAvailableException(
    #             "sqlite, required for requests CachedSession "
    #             "(possibly caused by concurrent operations)"
    #         ) from exc

    #     return retrieved_record
