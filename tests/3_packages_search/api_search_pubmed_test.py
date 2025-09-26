#! /usr/bin/env python
import typing
from pathlib import Path
from typing import Optional

import pytest
from pytest_mock import MockerFixture
from typing_extensions import Protocol

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.search_file
from colrev.constants import Fields
from colrev.constants import SearchType
from colrev.packages.pubmed.src.pubmed import PubMedSearchSource


class BuildFactory(Protocol):
    def __call__(
        self, version_marker: Optional[str], include_version_param: bool = ...
    ) -> colrev.search_file.ExtendedSearchFile: ...


@pytest.fixture()
def pubmed_search_file_factory() -> BuildFactory:
    """Return a factory to build PubMed search files for validation tests."""

    def _build(
        version_marker: Optional[str], include_version_param: bool = True
    ) -> colrev.search_file.ExtendedSearchFile:
        search_file = colrev.search_file.ExtendedSearchFile(
            platform="colrev.pubmed",
            search_results_path=Path("data/search/test_pubmed.bib"),
            search_type=SearchType.API,
            search_string="",
            comment="",
            version="0.1.0",
        )

        search_parameters: dict[str, typing.Any] = {
            "url": "https://pubmed.ncbi.nlm.nih.gov/?term=validation",
        }
        if include_version_param and version_marker is not None:
            search_parameters["version"] = version_marker
        search_file.search_parameters = search_parameters

        # Explicitly set version attribute to mirror persisted search files
        if version_marker is not None:
            search_file.version = version_marker
        else:
            search_file.version = None

        return search_file

    return _build


def test_pubmed_validate_accepts_current_version(
    pubmed_search_file_factory: BuildFactory,
) -> None:
    search_file = pubmed_search_file_factory("0.1.0")
    PubMedSearchSource(search_file=search_file)


def test_pubmed_validate_rejects_missing_version(
    pubmed_search_file_factory: BuildFactory,
) -> None:
    search_file = pubmed_search_file_factory(
        version_marker=None, include_version_param=False
    )

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        PubMedSearchSource(search_file=search_file)

    assert str(exc_info.value) == "PubMed version should be 0.1.0, found None"


def test_pubmed_validate_rejects_mismatched_version(
    pubmed_search_file_factory: BuildFactory,
) -> None:
    search_file = pubmed_search_file_factory("9.9.9")

    with pytest.raises(colrev_exceptions.InvalidQueryException) as exc_info:
        PubMedSearchSource(search_file=search_file)

    assert str(exc_info.value) == "PubMed version should be 0.1.0, found 9.9.9"


def test_pubmed_search_persists_api_results(
    tmp_path: Path,
    mocker: MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run a full PubMed API search and persist the retrieved records."""

    monkeypatch.chdir(tmp_path)
    Path("data/search").mkdir(parents=True)

    search_file = colrev.search_file.ExtendedSearchFile(
        platform="colrev.pubmed",
        search_results_path=Path("data/search/pubmed.bib"),
        search_type=SearchType.API,
        search_string="",
        comment="",
        version="0.1.0",
    )
    search_file.search_parameters = {
        "url": "https://pubmed.ncbi.nlm.nih.gov/?term=fitbit",
    }

    mocker.patch.object(
        colrev.env.environment_manager.EnvironmentManager,
        "get_name_mail_from_git",
        return_value=("Test User", "test@example.com"),
    )

    fake_esearch_response: dict[str, typing.Any] = {
        "esearchresult": {
            "count": "1",
            "idlist": ["37000000"],
        }
    }
    fake_esearch_empty_response: dict[str, typing.Any] = {
        "esearchresult": {
            "count": "1",
            "idlist": [],
        }
    }
    fake_efetch_xml = """
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <Article>
        <ArticleTitle>Tracking Fitbit usage for longitudinal studies</ArticleTitle>
        <Journal>
          <JournalIssue>
            <Volume>42</Volume>
            <Issue>7</Issue>
            <PubDate>
              <Year>2023</Year>
            </PubDate>
          </JournalIssue>
          <ISOAbbreviation>J Fitbit Res</ISOAbbreviation>
        </Journal>
        <AuthorList>
          <Author>
            <LastName>Doe</LastName>
            <ForeName>Alex</ForeName>
          </Author>
          <Author>
            <LastName>Roe</LastName>
            <ForeName>Sam</ForeName>
          </Author>
        </AuthorList>
        <Abstract>
          <AbstractText>Example abstract content for Fitbit trials.</AbstractText>
        </Abstract>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">37000000</ArticleId>
        <ArticleId IdType="doi">10.1000/FITBIT-TRIALS</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
""".strip()

    class FakeResponse:
        def __init__(
            self,
            *,
            status_code: int,
            json_data: Optional[dict[str, typing.Any]] = None,
            text: str = "",
        ) -> None:
            self.status_code = status_code
            self._json_data = json_data
            self.text = text

        def json(self) -> dict[str, typing.Any]:
            if self._json_data is None:
                raise ValueError("JSON data was not provided for this response")
            return self._json_data

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP status {self.status_code}")

    esearch_url = "https://pubmed.ncbi.nlm.nih.gov/?term=fitbit"

    def fake_request(
        self: typing.Any,
        method: str,
        url: str,
        params: Optional[dict[str, typing.Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> "FakeResponse":
        del self  # unused
        if url == esearch_url:
            retstart = int((params or {}).get("retstart", 0))
            if retstart == 0:
                return FakeResponse(status_code=200, json_data=fake_esearch_response)
            return FakeResponse(status_code=200, json_data=fake_esearch_empty_response)

        if url.startswith("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"):
            return FakeResponse(status_code=200, text=fake_efetch_xml)

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

    pubmed_source = PubMedSearchSource(search_file=search_file)
    pubmed_source.search(rerun=True)

    search_results_path = Path(search_file.search_results_path)
    assert search_results_path.is_file()

    saved_records = colrev.loader.load_utils.load(
        filename=search_results_path,
        unique_id_field=Fields.ID,
    )

    assert len(saved_records) == 1
    saved_record = next(iter(saved_records.values()))
    assert saved_record[Fields.ID] == "000001"
    assert (
        saved_record[Fields.TITLE] == "Tracking Fitbit usage for longitudinal studies"
    )
    assert saved_record[Fields.AUTHOR] == "Doe, Alex and Roe, Sam"
    assert saved_record["pubmedid"] == "37000000"
    assert saved_record[Fields.DOI] == "10.1000/FITBIT-TRIALS"
