"""Tests for loading search results through the unknown-source endpoint."""

from pathlib import Path

import pytest
from openpyxl import Workbook

import colrev.search_file
from colrev.constants import ENTRYTYPES, Fields, SearchType
from colrev.packages.unknown_source.src.unknown_source import UnknownSearchSource


def _load_unknown_source(path: Path) -> dict[str, dict]:
    search_file = colrev.search_file.ExtendedSearchFile(
        search_string="",
        platform="colrev.unknown_source",
        search_results_path=path,
        search_type=SearchType.OTHER,
        version="source-version-test",
    )
    return UnknownSearchSource(search_file=search_file).load()


def test_load_unknown_source_bib(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parse a BibTeX search result in unknown-source mode."""
    monkeypatch.chdir(tmp_path)
    bib_file = Path("data/search/unknown.bib")
    bib_file.parent.mkdir(parents=True)
    bib_file.write_text(
        """\
@ARTICLE{sample2024,
  title = {A title},
  year = {2024},
}
""",
        encoding="utf-8",
    )

    records = _load_unknown_source(bib_file)

    assert list(records) == ["sample2024"]
    assert records["sample2024"][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert records["sample2024"][Fields.TITLE] == "A title"
    assert records["sample2024"][Fields.YEAR] == "2024"


def test_load_unknown_source_ris(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parse RIS fields and entry type in unknown-source mode."""
    monkeypatch.chdir(tmp_path)
    ris_file = Path("data/search/unknown.ris")
    ris_file.parent.mkdir(parents=True)
    ris_file.write_text(
        """\
TY  - JOUR
ID  - record-1
TI  - A title
PY  - 2022
ER  -
""",
        encoding="utf-8",
    )

    records = _load_unknown_source(ris_file)

    assert list(records) == ["000001"]
    assert records["000001"][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert records["000001"][Fields.TITLE] == "A title"
    assert records["000001"][Fields.YEAR] == "2022"


def test_load_unknown_source_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parse CSV table records in unknown-source mode."""
    monkeypatch.chdir(tmp_path)
    csv_file = Path("data/search/unknown.csv")
    csv_file.parent.mkdir(parents=True)
    csv_file.write_text(
        """\
        PMID,ENTRYTYPE,Title,Publication Year
        11223344,article,Paper title,2021
""",
        encoding="utf-8",
    )

    records = _load_unknown_source(csv_file)

    assert "000001" in records
    assert records["000001"][Fields.TITLE] == "Paper title"
    assert records["000001"][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE


def test_load_unknown_source_xlsx(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parse spreadsheet records in unknown-source mode."""
    monkeypatch.chdir(tmp_path)
    xlsx_file = Path("data/search/unknown.xlsx")
    xlsx_file.parent.mkdir(parents=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append([Fields.ID, Fields.ENTRYTYPE, Fields.TITLE, Fields.YEAR])
    worksheet.append(["spreadsheet-1", ENTRYTYPES.ARTICLE, "A title", 2023])
    workbook.save(xlsx_file)

    records = _load_unknown_source(xlsx_file)

    assert list(records) == ["spreadsheet-1"]
    assert records["spreadsheet-1"][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert records["spreadsheet-1"][Fields.TITLE] == "A title"
    assert records["spreadsheet-1"][Fields.YEAR] == "2023"


# TODO: Add Markdown coverage when unknown-source Markdown parsing is tested here.
