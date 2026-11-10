"""Tests for the Google Scholar search source."""

import json
from pathlib import Path

import pytest

import colrev.search_file
from colrev.constants import Fields, SearchType
from colrev.packages.google_scholar.src.google_scholar import GoogleScholarSearchSource


def test_json_load_assigns_zero_padded_incremental_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Google Scholar JSON IDs keep the original six-digit format."""
    monkeypatch.chdir(tmp_path)
    search_path = Path("data/search/google_scholar.json")
    search_path.parent.mkdir(parents=True)
    search_path.write_text(
        json.dumps(
            [
                {"title": "First record", "uid": "GS:first"},
                {"title": "Second record", "uid": "GS:second", "ID": "custom"},
            ]
        ),
        encoding="utf-8",
    )
    search_source = colrev.search_file.ExtendedSearchFile(
        search_string="",
        platform="colrev.google_scholar",
        search_results_path=search_path,
        search_type=SearchType.DB,
        version="0.1.0",
    )

    records = GoogleScholarSearchSource(search_file=search_source).load()

    assert list(records) == ["000001", "000002"]
    assert records["000001"][Fields.ID] == "000001"
    assert records["000002"][Fields.ID] == "000002"
