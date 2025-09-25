#! /usr/bin/env python
import json
import typing
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.search_file
from colrev.constants import Fields, SearchType
from colrev.packages.dblp.src.dblp import DBLPSearchSource


@pytest.fixture()
def dblp_search_file_factory() -> typing.Callable:
    """Return a factory to build DBLP search files for validation tests."""

    def _build(
        version_marker: typing.Optional[str], include_version_param: bool = True
    ) -> colrev.search_file.ExtendedSearchFile:
        search_file = colrev.search_file.ExtendedSearchFile(
            platform="colrev.dblp",
            search_results_path=Path("data/search/dblp.bib"),
            search_type=SearchType.API,
            search_string="",
            comment="",
            version="0.1.0",
        )

        search_parameters: dict[str, typing.Any] = {
            "url": "https://dblp.org/search/publ/api?q=validation&h=10&format=json",
            "query": "https://dblp.org/search/publ/api?q=validation",
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


def test_dblp_validate_accepts_current_version(
    dblp_search_file_factory: typing.Callable,
) -> None:
    search_file = dblp_search_file_factory("0.1.0")

    DBLPSearchSource(search_file=search_file)


def test_dblp_validate_rejects_missing_version(
    dblp_search_file_factory: typing.Callable,
) -> None:
    search_file = dblp_search_file_factory(
        version_marker=None, include_version_param=False
    )

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        DBLPSearchSource(search_file=search_file)

    assert str(exc_info.value) == "DBLP version should be 0.1.0, found None"


def test_dblp_validate_rejects_mismatched_version(
    dblp_search_file_factory: typing.Callable,
) -> None:
    search_file = dblp_search_file_factory("9.9.9")

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        DBLPSearchSource(search_file=search_file)

    assert str(exc_info.value) == "DBLP version should be 0.1.0, found 9.9.9"


def test_dblp_search_persists_api_results(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run a full DBLP API search and persist the retrieved records."""

    monkeypatch.chdir(tmp_path)
    Path("data/search").mkdir(parents=True)

    search_file = colrev.search_file.ExtendedSearchFile(
        platform="colrev.dblp",
        search_results_path=Path("data/search/dblp.bib"),
        search_type=SearchType.API,
        search_string="",
        comment="",
        version="0.1.0",
    )
    search_file.search_parameters = {
        "url": "https://dblp.org/search/publ/api?q=validation&h=10&format=json",
        "query": "https://dblp.org/search/publ/api?q=validation",
        "version": "0.1.0",
    }

    mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "get_name_mail_from_git",
        return_value=("Test User", "test@example.com"),
    )

    class FakeResponse:
        def __init__(
            self,
            *,
            status_code: int,
            json_data: typing.Optional[typing.Any] = None,
            text: str = "",
        ) -> None:
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

    total_url = "https://dblp.org/search/publ/api?q=validation&format=json"
    search_url = (
        "https://dblp.org/search/publ/api?q=validation&format=json&h=250&f=0"
    )
    venue_url = "https://dblp.org/search/venue/api?q=isr&format=json"

    fake_total_payload = {
        "result": {
            "hits": {"@total": "1"},
        }
    }
    fake_search_payload = {
        "result": {
            "time": {"text": "0.0"},
            "hits": {
                "hit": [
                    {
                        "info": {
                            "title": "Validating Digital Platforms in IS Research",
                            "type": "Journal Articles",
                            "key": "journals/isr/000001",
                            "year": "2021",
                            "doi": "10.4242/DBLP-VALIDATE-2021",
                            "authors": {
                                "author": [
                                    {"text": "Doe, Alex"},
                                    {"text": "Roe, Sam"},
                                ]
                            },
                        }
                    }
                ]
            },
        }
    }
    fake_venue_payload = {
        "result": {
            "hits": {
                "hit": [
                    {
                        "info": {
                            "type": "Journal",
                            "venue": "Information Systems Research",
                            "url": "https://dblp.org/db/journals/isr/index.html",
                        }
                    }
                ]
            }
        }
    }

    def fake_request(
        self,
        method: str,
        url: str,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
        timeout: typing.Optional[int] = None,
    ) -> FakeResponse:
        del self, method, params, headers, timeout
        if url == total_url:
            return FakeResponse(
                status_code=200,
                text=json.dumps(fake_total_payload),
            )
        if url == search_url:
            return FakeResponse(
                status_code=200,
                text=json.dumps(fake_search_payload),
            )
        if url == venue_url:
            return FakeResponse(
                status_code=200,
                text=json.dumps(fake_venue_payload),
            )
        raise AssertionError(f"Unexpected URL called: {url}")

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

    dblp_source = DBLPSearchSource(search_file=search_file)
    dblp_source.search(rerun=True)

    search_results_path = Path(search_file.search_results_path)
    assert search_results_path.is_file()

    saved_records = colrev.loader.load_utils.load(
        filename=search_results_path,
        unique_id_field=Fields.ID,
    )

    assert len(saved_records) == 1
    saved_record = next(iter(saved_records.values()))
    assert saved_record[Fields.ID] == "000001"
    assert saved_record[Fields.TITLE] == "Validating Digital Platforms in IS Research"
    assert saved_record[Fields.AUTHOR] == "Doe, Alex and Roe, Sam"
    assert saved_record[Fields.YEAR] == "2021"
    assert saved_record[Fields.DOI] == "10.4242/DBLP-VALIDATE-2021"
