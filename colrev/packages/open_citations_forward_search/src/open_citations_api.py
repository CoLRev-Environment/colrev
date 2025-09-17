"""OpenCitations API client for forward searches."""
from __future__ import annotations

from typing import Dict, Optional

import requests


class OpenCitationsAPIError(Exception):
    """Exception raised when OpenCitations requests fail."""


class OpenCitationsAPI:
    """Handle HTTP interactions with the OpenCitations service."""

    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.headers = headers or {}

    def get(self, url: str, *, timeout: int) -> requests.Response:
        """Execute a GET request and raise a custom exception on failure."""

        try:
            response = self.session.get(
                url, headers=self.headers, timeout=timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            raise OpenCitationsAPIError from exc
