#!/usr/bin/env python3
"""OpenCitations API client for forward searches."""
from __future__ import annotations

import typing

import requests

# pylint: disable=too-few-public-methods


class OpenCitationsAPIError(Exception):
    """Exception raised when OpenCitations requests fail."""


class OpenCitationsAPI:
    """Handle HTTP interactions with the OpenCitations service."""

    def __init__(
        self,
        *,
        session: typing.Optional[requests.Session] = None,
        headers: typing.Optional[typing.Dict[str, str]] = None,
    ) -> None:
        self.session = session or requests.Session()
        # headers = {"authorization": "YOUR-OPENCITATIONS-ACCESS-TOKEN"}
        self.headers: typing.Dict[str, str] = headers or {}

    def get(self, url: str, *, timeout: int) -> requests.Response:
        """Execute a GET request and raise a custom exception on failure."""

        try:
            response = self.session.get(url, headers=self.headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            raise OpenCitationsAPIError from exc
