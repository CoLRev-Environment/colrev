"""Tests for the unknown search-source loaders."""

import logging
from pathlib import Path

from colrev.constants import ENTRYTYPES, Fields
from colrev.packages.unknown_source.src.unknown_source import UnknownSearchSource


def test_load_unknown_source_ris_with_bibliography_io(tmp_path: Path) -> None:
    """Keep RIS mappings and sequential IDs when parsing with bibliography-io."""
    ris_file = tmp_path / "unknown.ris"
    ris_file.write_text(
        "TY  - JOUR\nTI  - A title\nPY  - 2022/01/01\n"
        "PMID  - 12345\nC1  - Affiliation\nER  -\n",
        encoding="utf-8",
    )

    records = UnknownSearchSource._load_ris(  # pylint: disable=protected-access
        filename=ris_file, logger=logging.getLogger(__name__)
    )

    assert list(records) == ["000001"]
    record = records["000001"]
    assert record[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert record[Fields.TITLE] == "A title"
    assert record[Fields.YEAR] == "2022"
    assert record[Fields.PUBMED_ID] == "12345"
    assert "C1" not in record


def test_load_unknown_source_bib_with_bibliography_io(tmp_path: Path) -> None:
    """Preserve BibTeX IDs and CoLRev entrytype handling."""
    bib_file = tmp_path / "unknown.bib"
    bib_file.write_text(
        "@ARTICLE{sample2024, title={A title}, year={2024}}\n",
        encoding="utf-8",
    )

    records = UnknownSearchSource._load_bib(  # pylint: disable=protected-access
        filename=bib_file, logger=logging.getLogger(__name__)
    )

    assert list(records) == ["sample2024"]
    assert records["sample2024"][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert records["sample2024"][Fields.TITLE] == "A title"
