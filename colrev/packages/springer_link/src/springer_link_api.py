#! /usr/bin/env python
"""Springer Link API helper."""
from __future__ import annotations

import typing

import requests


class SpringerLinkAPIError(Exception):
    """Exception raised when Springer Link requests fail."""


class SpringerLinkAPI:
    """Handle HTTP interactions with the Springer Link API."""

    def __init__(self, *, session: typing.Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()

    def get_json(self, url: str, *, timeout: int) -> dict:
        """Return JSON content from the API."""

        response = self._get(url=url, timeout=timeout)
        return response.json()

    def validate_api_key(self, url: str, *, timeout: int) -> None:
        """Validate the API key by performing a test request."""

        self._get(url=url, timeout=timeout)

    def _get(self, *, url: str, timeout: int) -> requests.Response:
        try:
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            raise SpringerLinkAPIError from exc
