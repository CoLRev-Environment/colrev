"""arXiv API helper."""
from __future__ import annotations

from typing import Optional

import requests


class ArxivAPIError(Exception):
    """Exception raised when arXiv requests fail."""


class ArxivAPI:
    """Handle HTTP interactions with the arXiv API."""

    def __init__(self, *, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

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
