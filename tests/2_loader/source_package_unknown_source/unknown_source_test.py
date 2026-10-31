"""Integration tests for the unknown-source search package."""

from pathlib import Path

import pytest

import colrev.search_file
from bibliography_io.exceptions import DuplicateRecordIDError
from bibliography_io.exceptions import MissingRecordIDError
from colrev.constants import SearchType
from colrev.packages.unknown_source.src.unknown_source import UnknownSearchSource


def _unknown_source(path: Path) -> UnknownSearchSource:
    search_file = colrev.search_file.ExtendedSearchFile(
        search_string="",
        platform="colrev.unknown_source",
        search_results_path=path,
        search_type=SearchType.OTHER,
        version="source-version-test",
    )
    return UnknownSearchSource(search_file=search_file)


def test_load_unknown_source_missing_file_returns_empty_dict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing source file is treated as an empty search result."""
    monkeypatch.chdir(tmp_path)
    assert _unknown_source(Path("data/search/missing.bib")).load() == {}


def test_load_unknown_source_indexes_records_from_library(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The endpoint returns library-loaded records indexed by their IDs."""
    monkeypatch.chdir(tmp_path)
    bib_file = Path("data/search/results.bib")
    bib_file.parent.mkdir(parents=True)
    bib_file.write_text(
        "@article{sample2024, title={A title}, year={2024}}\n", encoding="utf-8"
    )

    records = _unknown_source(bib_file).load()

    assert list(records) == ["sample2024"]
    assert records["sample2024"]["title"] == "A title"


@pytest.mark.parametrize(
    ("record", "error"),
    [({}, MissingRecordIDError), ({"ID": " "}, MissingRecordIDError)],
)
def test_load_unknown_source_rejects_missing_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record: dict,
    error: type[Exception],
) -> None:
    """The CoLRev indexing contract rejects missing and blank IDs."""
    monkeypatch.chdir(tmp_path)
    source_file = Path("data/search/results.bib")
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    monkeypatch.setattr(
        "colrev.packages.unknown_source.src.unknown_source.bibliography_io_load",
        lambda path: [record],
    )

    with pytest.raises(error):
        _unknown_source(source_file).load()


def test_load_unknown_source_rejects_duplicate_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CoLRev indexing contract rejects duplicate IDs."""
    monkeypatch.chdir(tmp_path)
    source_file = Path("data/search/results.bib")
    source_file.parent.mkdir(parents=True)
    source_file.touch()
    monkeypatch.setattr(
        "colrev.packages.unknown_source.src.unknown_source.bibliography_io_load",
        lambda path: [{"ID": "same"}, {"ID": "same"}],
    )

    with pytest.raises(DuplicateRecordIDError):
        _unknown_source(source_file).load()
