"""Tests for files-directory search behavior."""

import logging
from pathlib import Path

import pytest

import colrev.search_file
from colrev.constants import SearchType
from colrev.ops.pdf_get import relink_pdfs_in_source


def test_relink_pdfs_in_source_missing_search_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A files-dir source may not have a results file before its first search."""
    monkeypatch.chdir(tmp_path)
    search_results_path = Path("data/search/files.bib")
    source = colrev.search_file.ExtendedSearchFile(
        platform="colrev.files_dir",
        search_results_path=search_results_path,
        search_type=SearchType.FILES,
        search_string="",
        search_parameters={"scope": {"path": "data/pdfs"}},
        comment="",
        version="0.1.0",
    )

    relink_pdfs_in_source(
        source=source,
        records={},
        pdf_dir=Path("data/pdfs"),
        logger=logging.getLogger(__name__),
    )

    assert not search_results_path.exists()
