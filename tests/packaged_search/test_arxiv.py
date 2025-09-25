#! /usr/bin/env python
import typing
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.search_file
from colrev.constants import Fields, SearchType

try:  # pragma: no cover - compatibility with updated interfaces
    from colrev.packages.arxiv.src.arxiv import ArXivSearchSource
except ImportError:  # pragma: no cover - fallback for legacy class name
    from colrev.packages.arxiv.src.arxiv import ArXivSource as ArXivSearchSource


@pytest.fixture()
def arxiv_search_file_factory() -> typing.Callable:
    """Return a factory to build arXiv search files for validation tests."""

    def _build(
        version_marker: typing.Optional[str], include_version_param: bool = True
    ) -> colrev.search_file.ExtendedSearchFile:
        search_file = colrev.search_file.ExtendedSearchFile(
            platform="colrev.arxiv",
            search_results_path=Path("data/search/arxiv.bib"),
            search_type=SearchType.API,
            search_string="",
            comment="",
            version="0.1.0",
        )

        search_parameters: dict[str, typing.Any] = {
            "url": "https://arxiv.org/search/?query=fitbit&searchtype=all",
            "query": "fitbit",
        }
        if include_version_param and version_marker is not None:
            search_parameters["version"] = version_marker
        search_file.search_parameters = search_parameters

        if version_marker is not None:
            search_file.version = version_marker
        else:
            search_file.version = None

        return search_file

    return _build


def test_arxiv_validate_accepts_current_version(
    arxiv_search_file_factory: typing.Callable,
) -> None:
    search_file = arxiv_search_file_factory("0.1.0")

    ArXivSearchSource(search_file=search_file)


def test_arxiv_validate_rejects_missing_version(
    arxiv_search_file_factory: typing.Callable,
) -> None:
    search_file = arxiv_search_file_factory(
        version_marker=None, include_version_param=False
    )

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        ArXivSearchSource(search_file=search_file)

    assert str(exc_info.value) == "arXiv version should be 0.1.0, found None"


def test_arxiv_validate_rejects_mismatched_version(
    arxiv_search_file_factory: typing.Callable,
) -> None:
    search_file = arxiv_search_file_factory("9.9.9")

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        ArXivSearchSource(search_file=search_file)

    assert str(exc_info.value) == "arXiv version should be 0.1.0, found 9.9.9"


def test_arxiv_search_persists_api_results(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run a full arXiv API search and persist the retrieved records."""

    monkeypatch.chdir(tmp_path)
    Path("data/search").mkdir(parents=True)

    search_file = colrev.search_file.ExtendedSearchFile(
        platform="colrev.arxiv",
        search_results_path=Path("data/search/arxiv.bib"),
        search_type=SearchType.API,
        search_string="",
        comment="",
        version="0.1.0",
    )
    search_file.search_parameters = {
        "url": "https://arxiv.org/search/?query=fitbit&searchtype=all",
        "query": "fitbit",
        "version": "0.1.0",
    }

    mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "get_name_mail_from_git",
        return_value=("Test User", "test@example.com"),
    )

    class FakeResponse:
        def __init__(self, *, status_code: int, json_data: typing.Any = None, text: str = "") -> None:
            self.status_code = status_code
            self._json_data = json_data
            self.text = text

        def json(self) -> typing.Any:
            if self._json_data is None:
                raise ValueError("JSON data was not provided for this response")
            return self._json_data

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP status {self.status_code}")

    def fake_request(
        self,
        method: str,
        url: str,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
        timeout: typing.Optional[int] = None,
    ) -> FakeResponse:
        del self, method, url, params, headers, timeout
        raise AssertionError("Unexpected HTTP request executed")

    mocker.patch(
        "requests.sessions.Session.request",
        autospec=True,
        side_effect=fake_request,
    )
    mocker.patch(
        "requests_cache.session.CachedSession.request",
        autospec=True,
        side_effect=fake_request,
    )

    def fake_feedparser_parse(url: str) -> dict:
        assert url.startswith(
            "https://export.arxiv.org/api/query?search_query=all:fitbit&start=0&max_results=20"
        )
        return {
            "entries": [
                {
                    "id": "http://arxiv.org/abs/000001",
                    "title": "Tracking Fitbit usage for longitudinal studies",
                    "summary": "Example abstract content for Fitbit trials.",
                    "published": "2023-01-01T00:00:00Z",
                    "authors": [
                        {"name": "Doe, Alex"},
                        {"name": "Roe, Sam"},
                    ],
                    "arxiv_doi": "10.1000/FITBIT-TRIALS",
                }
            ]
        }

    mocker.patch("feedparser.parse", side_effect=fake_feedparser_parse)

    arxiv_source = ArXivSearchSource(search_file=search_file)
    arxiv_source.search(rerun=True)

    search_results_path = Path(search_file.search_results_path)
    assert search_results_path.is_file()

    saved_records = colrev.loader.load_utils.load(
        filename=search_results_path,
        unique_id_field=Fields.ID,
    )

    assert len(saved_records) == 1
    saved_record = next(iter(saved_records.values()))
    assert saved_record[Fields.ID] == "000001"
    assert saved_record[Fields.TITLE] == "Tracking Fitbit usage for longitudinal studies"
    assert saved_record[Fields.AUTHOR] == "Doe, Alex and Roe, Sam"
    assert saved_record[Fields.YEAR] == "2023"
    assert saved_record[Fields.DOI] == "10.1000/FITBIT-TRIALS"
