#!/usr/bin/env python
"""Semantic Scholar API wrapper."""
from __future__ import annotations

from typing import Iterable
from typing import Optional

import requests
from semanticscholar import SemanticScholar
from semanticscholar.PaginatedResults import PaginatedResults


class SemanticScholarAPIError(Exception):
    """Exception raised when Semantic Scholar requests fail."""


class SemanticScholarAPI:
    """Light wrapper around the Semantic Scholar client."""

    def __init__(self, *, api_key: Optional[str] = None) -> None:
        self._client = (
            SemanticScholar(api_key=api_key) if api_key else SemanticScholar()
        )

    @property
    def client(self) -> SemanticScholar:
        """Expose the underlying client (mainly for UI interactions)."""

        return self._client

    def get_paper(self, *, paper_id: str) -> dict:
        """Get a paper by its Semantic Scholar ID."""
        try:
            return self._client.get_paper(paper_id=paper_id)
        except requests.exceptions.RequestException as exc:
            raise SemanticScholarAPIError from exc

    # pylint: disable=too-many-arguments
    def search_paper(
        self,
        *,
        query: Optional[str] = None,
        year: Optional[str] = None,
        publication_types: Optional[Iterable[str]] = None,
        venue: Optional[str] = None,
        fields_of_study: Optional[Iterable[str]] = None,
        open_access_pdf: Optional[bool] = None,
    ) -> PaginatedResults:
        """Search for papers matching the given criteria."""
        try:
            return self._client.search_paper(
                query=query,
                year=year,
                publication_types=publication_types,
                venue=venue,
                fields_of_study=fields_of_study,
                open_access_pdf=open_access_pdf,
            )
        except requests.exceptions.RequestException as exc:
            raise SemanticScholarAPIError from exc

    def get_papers(self, paper_ids: Iterable[str]) -> PaginatedResults:
        """Get multiple papers by their Semantic Scholar IDs."""
        try:
            return self._client.get_papers(paper_ids)
        except requests.exceptions.RequestException as exc:
            raise SemanticScholarAPIError from exc

    def get_authors(self, author_ids: Iterable[str]) -> PaginatedResults:
        """Get multiple authors by their Semantic Scholar IDs."""
        try:
            return self._client.get_authors(author_ids)
        except requests.exceptions.RequestException as exc:
            raise SemanticScholarAPIError from exc
