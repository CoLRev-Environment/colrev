"""OpenLibrary API client."""
from __future__ import annotations

from typing import Optional

import requests


class OpenLibraryAPIError(Exception):
    """Exception raised for OpenLibrary API errors."""


class OpenLibraryAPI:
    """Helper around OpenLibrary HTTP interactions."""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        headers: Optional[dict] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.headers = headers or {}

    def get(self, url: str, *, timeout: int) -> requests.Response:
        """Perform a GET request and raise a custom error on failure."""

        try:
            response = self.session.request(
                "GET", url, headers=self.headers, timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            raise OpenLibraryAPIError from exc
