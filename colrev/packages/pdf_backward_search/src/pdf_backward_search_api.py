#!/usr/bin/env python3
"""OpenCitations API client for backward PDF searches."""
from __future__ import annotations

import typing

import requests

# pylint: disable=too-few-public-methods


class PDFBackwardSearchAPIError(Exception):
    """Exception raised when OpenCitations requests fail."""


class PDFBackwardSearchAPI:
    """Handle HTTP interactions required by the backward search package."""

    def __init__(
        self,
        *,
        session: typing.Optional[requests.Session] = None,
        headers: typing.Optional[typing.Dict[str, str]] = None,
    ) -> None:
        self.session = session or requests.Session()
        self.headers = headers or {}

    def get(self, url: str, *, timeout: int) -> requests.Response:
        """Execute a GET request and raise a custom exception on failure."""

        try:
            response = self.session.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            raise PDFBackwardSearchAPIError from exc
