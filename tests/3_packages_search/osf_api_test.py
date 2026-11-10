"""Tests for OSF contributor resolution fallback behavior."""

# pylint: disable=protected-access

from unittest.mock import Mock

import pytest
import requests

from colrev.packages.osf.src.osf_api import OSFApiQuery


@pytest.mark.parametrize(
    "response_or_error",
    [requests.ConnectionError("offline"), "not json", '{"data": "invalid"}'],
)
def test_contributor_resolution_falls_back_on_api_or_response_errors(
    response_or_error: object,
) -> None:
    """Expected API and malformed-response failures use contributor ID fallback."""
    api = OSFApiQuery(parameters={}, api_key="test")
    if isinstance(response_or_error, Exception):
        api._query_api = Mock(side_effect=response_or_error)  # type: ignore[method-assign]
    else:
        api._query_api = Mock(return_value=response_or_error)  # type: ignore[method-assign]
    api._resolve_fallback_ids = Mock(return_value=["contributor-id"])  # type: ignore[method-assign]

    assert api._resolve_contributor_authors("https://api.osf.io/contributors") == (
        [],
        ["contributor-id"],
    )
    api._resolve_fallback_ids.assert_called_once_with("https://api.osf.io/contributors")


def test_contributor_resolution_does_not_hide_unexpected_errors() -> None:
    """Unexpected programming errors propagate rather than invoking fallback."""
    api = OSFApiQuery(parameters={}, api_key="test")
    api._query_api = Mock(side_effect=RuntimeError("unexpected"))  # type: ignore[method-assign]
    api._resolve_fallback_ids = Mock(return_value=[])  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="unexpected"):
        api._resolve_contributor_authors("https://api.osf.io/contributors")

    api._resolve_fallback_ids.assert_not_called()


def test_fallback_returns_empty_for_malformed_osf_response() -> None:
    """Malformed fallback payloads produce no IDs instead of raising."""
    api = OSFApiQuery(parameters={}, api_key="test")
    api._query_api = Mock(return_value='{"data": "invalid"}')  # type: ignore[method-assign]

    assert api._resolve_fallback_ids("https://api.osf.io/contributors") == []
