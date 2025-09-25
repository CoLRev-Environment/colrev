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

try:  # pragma: no cover - compatibility with previous module names
    from colrev.packages.ais_library.src.ais_library import AISLibrarySearchSource
except ImportError:  # pragma: no cover - fallback for legacy structure
    from colrev.packages.ais_library.src.aisel import (
        AISeLibrarySearchSource as AISLibrarySearchSource,
    )


@pytest.fixture()
def ais_library_search_file_factory() -> typing.Callable:
    """Return a factory to build AIS Library search files for validation tests."""

    def _build(
        version_marker: typing.Optional[str], include_version_param: bool = True
    ) -> colrev.search_file.ExtendedSearchFile:
        search_file = colrev.search_file.ExtendedSearchFile(
            platform="colrev.ais_library",
            search_results_path=Path("data/search/ais_library.bib"),
            search_type=SearchType.API,
            search_string="",
            comment="",
            version="0.1.0",
        )

        search_parameters: dict[str, typing.Any] = {
            "url": "https://aisel.aisnet.org/do/search/?q=validation",
            "query": [
                {"operator": "", "term": "validation", "field": "All fields"},
            ],
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


def test_ais_library_validate_accepts_current_version(
    ais_library_search_file_factory: typing.Callable,
) -> None:
    search_file = ais_library_search_file_factory("0.1.0")

    AISLibrarySearchSource(search_file=search_file)


def test_ais_library_validate_rejects_missing_version(
    ais_library_search_file_factory: typing.Callable,
) -> None:
    search_file = ais_library_search_file_factory(
        version_marker=None, include_version_param=False
    )

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        AISLibrarySearchSource(search_file=search_file)

    assert str(exc_info.value) == "AISLibrary version should be 0.1.0, found None"


def test_ais_library_validate_rejects_mismatched_version(
    ais_library_search_file_factory: typing.Callable,
) -> None:
    search_file = ais_library_search_file_factory("9.9.9")

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        AISLibrarySearchSource(search_file=search_file)

    assert str(exc_info.value) == "AISLibrary version should be 0.1.0, found 9.9.9"


def test_ais_library_search_persists_api_results(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run a full AIS Library API search and persist the retrieved records."""

    monkeypatch.chdir(tmp_path)
    Path("data/search").mkdir(parents=True)

    search_file = colrev.search_file.ExtendedSearchFile(
        platform="colrev.ais_library",
        search_results_path=Path("data/search/ais_library.bib"),
        search_type=SearchType.API,
        search_string="",
        comment="",
        version="0.1.0",
    )
    search_file.search_parameters = {
        "url": "https://aisel.aisnet.org/do/search/?q=validation",
        "query": [
            {"operator": "", "term": "validation", "field": "All fields"},
        ],
        "version": "0.1.0",
    }

    mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "get_name_mail_from_git",
        return_value=("Test User", "test@example.com"),
    )

    fake_enl = """
%T Validating Digital Platforms in IS Research
%0 Journal Article
%A Doe, Alex
%A Roe, Sam
%D 2022
%U https://aisel.aisnet.org/validating_digital_platforms
%R 10.5555/AIS-VALIDATE-2022
""".strip()

    class FakeResponse:
        def __init__(self, *, status_code: int, text: str = "") -> None:
            self.status_code = status_code
            self.text = text

        def json(self) -> typing.Any:
            raise ValueError("JSON data was not provided for this response")

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP status {self.status_code}")

    ais_results_prefix = "https://aisel.aisnet.org/do/search/results/refer?"

    def fake_request(
        self,
        method: str,
        url: str,
        params: typing.Optional[dict] = None,
        headers: typing.Optional[dict] = None,
        timeout: typing.Optional[int] = None,
    ) -> FakeResponse:
        del self, method, params, headers, timeout
        if url.startswith(ais_results_prefix):
            return FakeResponse(status_code=200, text=fake_enl)
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

    ais_source = AISLibrarySearchSource(search_file=search_file)
    ais_source.search(rerun=True)

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
    assert saved_record[Fields.YEAR] == "2022"
    assert saved_record[Fields.DOI] == "10.5555/AIS-VALIDATE-2022"
