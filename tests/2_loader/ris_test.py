#!/usr/bin/env python
"""Tests of normalized RIS loading."""

from pathlib import Path

import pytest
from bibliography_io import get_nr_records, load, loads
from bibliography_io.exceptions import UnsupportedFormatError

from colrev.constants import ENTRYTYPES, Fields

NESTED_KNOWLEDGE_TITLES = [
    (
        "Activation of peroxisome-proliferator-receptor alpha and gamma mediates "
        "remote ischemic preconditioning against myocardial infarction"
    ),
    (
        "Myocardial Protection from Surgical Ischemic-Reperfusion Injury. Proceedings "
        "and abstracts of the 3rd International Symposium. Asheville North Carolina "
        "USA. June 2-6 2002"
    ),
    "Ischemic preconditioning reduces caspase-related intestinal apoptosis",
]


@pytest.mark.parametrize(
    ("ris_type", "expected"),
    [
        ("JOUR", ENTRYTYPES.ARTICLE),
        ("CONF", ENTRYTYPES.INPROCEEDINGS),
        ("UNLISTED", ENTRYTYPES.MISC),
        (None, ENTRYTYPES.MISC),
    ],
)
def test_default_ris_entrytypes(ris_type: str | None, expected: str) -> None:
    """Normalize known, unknown, and missing RIS reference types."""
    type_line = f"TY  - {ris_type}\n" if ris_type is not None else ""
    records = loads(f"{type_line}ID  - test\nTI  - A title\nER  -\n", format="ris")

    assert records[0][Fields.ENTRYTYPE] == expected
    assert records[0][Fields.TITLE] == "A title"


@pytest.mark.parametrize(
    ("date_tag", "date_value"),
    [("PY", "2011"), ("PY", "2011-01-01"), ("Y1", "2011/01/01"), ("DA", "2011/02/03")],
)
def test_default_ris_common_fields(date_tag: str, date_value: str) -> None:
    """Normalize common RIS fields, repeated values, and page ranges."""
    records = loads(
        "TY  - JOUR\nID  - test\nTI  - Main title\nT1  - Other title\n"
        f"{date_tag}  - {date_value}\nAU  - Doe, Jane\nAU  - Roe, John\n"
        "JO  - Main Journal\nDO  - 10.1000/test\n"
        "SP  - 10\nEP  - 20\nER  -\n",
        format="ris",
    )
    record = records[0]

    assert record[Fields.TITLE] == "Main title"
    assert record[Fields.YEAR] == "2011"
    assert record[Fields.AUTHOR] == "Doe, Jane and Roe, John"
    assert record[Fields.JOURNAL] == "Main Journal"
    assert record[Fields.DOI] == "10.1000/test"
    assert record[Fields.PAGES] == "10--20"


def test_default_ris_fallbacks_and_start_page() -> None:
    """Normalize fallback title, date, author, journal, and a lone start page."""
    records = loads(
        "TY  - JOUR\nID  - test\nT1  - Fallback title\nDA  - 2020-05-04\n"
        "A1  - Doe, Jane\nT2  - Fallback Journal\nSP  - 7\nER  -\n",
        format="ris",
    )
    record = records[0]

    assert record[Fields.TITLE] == "Fallback title"
    assert record[Fields.AUTHOR] == "Doe, Jane"
    assert record[Fields.JOURNAL] == "Fallback Journal"
    assert record[Fields.PAGES] == "7"


def test_default_ris_normalization_handles_legacy_provider_fields() -> None:
    """Apply generic RIS normalization to common provider-specific fields."""
    records = loads(
        "TY  - JOUR\nTI  - Shared mapping\nPY  - 2022/01/01\n"
        "PMID  - 12345\nC1  - Affiliation\nER  -\n",
        format="ris",
    )

    assert len(records) == 1
    assert records[0][Fields.ID] == "000001"
    assert records[0][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert records[0][Fields.TITLE] == "Shared mapping"
    assert records[0][Fields.YEAR] == "2022"
    assert records[0]["pubmed_id"] == "12345"
    assert "C1" not in records[0]


def test_load_nested_knowledge_numbered_records() -> None:
    """Load numbered RIS references through generic normalization."""
    fixture = (
        Path(__file__).parents[1] / "data/ris/nestedknowledge_numbered_records.ris"
    )
    records = load(fixture)

    assert len(records) == 3
    assert [record[Fields.ID] for record in records] == ["000001", "000002", "000003"]
    assert [record[Fields.TITLE] for record in records] == NESTED_KNOWLEDGE_TITLES
    assert records[0][Fields.DOI] == "10.1258/ebm.2010.011f01"
    assert Fields.DOI not in records[1]
    assert records[2][Fields.DOI] == "10.1007/s00595-004-2918-y"
    assert records[2][Fields.ABSTRACT].startswith("PURPOSE: To investigate")
    assert records[2][Fields.AUTHOR] == "M., Aban N.Cinel L.Tamer L.Aktas A.Aban"


def test_load_ris_file() -> None:
    """Load and normalize RIS files through the generic bibliography-io path."""
    fixture = Path(__file__).parent / "data" / "ris_data.ris"
    records = load(fixture)

    assert len(records) == 2
    assert records[0][Fields.ENTRYTYPE] == ENTRYTYPES.INPROCEEDINGS
    assert records[0][Fields.TITLE] == "Title of a conference paper"
    assert records[0][Fields.AUTHOR].startswith("A. Author-One and B. Author-Two")
    assert records[0][Fields.PAGES] == "183--186"
    assert records[0][Fields.DOI] == "10.1234/Random-name55555.2020.00050"
    assert records[1][Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert records[1][Fields.TITLE] == "Title of a journal paper"
    assert records[1][Fields.NUMBER] == "3"
    assert records[1][Fields.VOLUME] == "50"
    assert get_nr_records(fixture) == 2
    with pytest.raises(FileNotFoundError):
        load(fixture.parent / "missing.ris")
    with pytest.raises(UnsupportedFormatError):
        load(fixture.with_suffix(".unknown"))
