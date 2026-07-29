#!/usr/bin/env python
"""Tests of the load utils for ris files"""

import os
import logging
from pathlib import Path

import pytest

import colrev.loader.load_utils
import colrev.loader.ris
from colrev.packages.unknown_source.src.unknown_source import UnknownSearchSource
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

NESTED_KNOWLEDGE_TITLES = [
    "Activation of peroxisome-proliferator-receptor alpha and gamma mediates "
    "remote ischemic preconditioning against myocardial infarction",
    "Myocardial Protection from Surgical Ischemic-Reperfusion Injury. Proceedings "
    "and abstracts of the 3rd International Symposium. Asheville North Carolina "
    "USA. June 2-6 2002",
    "Ischemic preconditioning reduces caspase-related intestinal apoptosis",
]


def _load_ris_string(ris: str) -> dict:
    """Load a single realistic RIS record with the public string API."""
    return next(
        iter(
            colrev.loader.load_utils.loads(
                ris, implementation="ris", unique_id_field="ID"
            ).values()
        )
    )


@pytest.mark.parametrize(
    ("ris_type", "expected"),
    [
        (" JOUR ", ENTRYTYPES.ARTICLE),
        ("CONF", ENTRYTYPES.INPROCEEDINGS),
        ("UNLISTED", ENTRYTYPES.MISC),
        (None, ENTRYTYPES.MISC),
    ],
)
def test_default_ris_entrytypes(ris_type: str | None, expected: str) -> None:
    """Map known, unknown, and missing RIS types using core defaults."""
    type_line = f"TY  - {ris_type}\n" if ris_type is not None else ""
    record = _load_ris_string(f"{type_line}ID  - test\nTI  - A title\nER  -\n")

    assert record[Fields.ENTRYTYPE] == expected
    assert "TY" not in record


@pytest.mark.parametrize(
    ("date_tag", "date_value"),
    [("PY", "2011"), ("PY", "2011-01-01"), ("Y1", "2011/01/01"), ("DA", "2011/02/03")],
)
def test_default_ris_common_fields(date_tag: str, date_value: str) -> None:
    """Map common fields, repeated values, dates, and page ranges."""
    record = _load_ris_string(
        "TY  - JOUR\nID  - test\nTI  - Main title\nT1  - Other title\n"
        f"{date_tag}  - {date_value}\nAU  - Doe, Jane\nAU  - Roe, John\n"
        "JO  - Main Journal\nJF  - Other Journal\nDO  - 10.1000/test\n"
        "SP  - 10\nEP  - 20\nER  -\n"
    )

    assert record[Fields.TITLE] == "Main title"
    assert record[Fields.YEAR] == "2011"
    assert record[Fields.AUTHOR] == "Doe, Jane and Roe, John"
    assert record[Fields.JOURNAL] == "Main Journal"
    assert record[Fields.DOI] == "10.1000/test"
    assert record[Fields.PAGES] == "10--20"


def test_default_ris_fallbacks_and_start_page() -> None:
    """Use title/date/author/journal fallbacks and retain a lone start page."""
    record = _load_ris_string(
        "TY  - JOUR\nID  - test\nT1  - Fallback title\nDA  - 2020-05-04\n"
        "A1  - Doe, Jane\nT2  - Fallback Journal\nSP  - 7\nER  -\n"
    )

    assert record[Fields.TITLE] == "Fallback title"
    assert record[Fields.YEAR] == "2020"
    assert record[Fields.AUTHOR] == "Doe, Jane"
    assert record[Fields.JOURNAL] == "Fallback Journal"
    assert record[Fields.PAGES] == "7"


@pytest.mark.parametrize("journal_tag", ["JO", "JF", "JA", "T2"])
def test_default_ris_journal_fallbacks(journal_tag: str) -> None:
    """Accept each documented article journal tag."""
    record = _load_ris_string(
        f"TY  - JOUR\nID  - test\nTI  - Title\n{journal_tag}  - Journal\nER  -\n"
    )
    assert record[Fields.JOURNAL] == "Journal"


def test_ris_custom_callbacks_override_defaults() -> None:
    """Keep caller-provided RIS interpretation authoritative."""
    record = next(
        iter(
            colrev.loader.load_utils.loads(
                "TY  - JOUR\nID  - test\nTI  - Raw title\nER  -\n",
                implementation="ris",
                unique_id_field="ID",
                entrytype_setter=lambda item: item.update({Fields.ENTRYTYPE: "book"}),
                field_mapper=lambda item: item.update({Fields.TITLE: "Custom title"}),
            ).values()
        )
    )

    assert record[Fields.ENTRYTYPE] == ENTRYTYPES.BOOK
    assert record[Fields.TITLE] == "Custom title"


def test_unknown_source_reuses_default_ris_mapping(tmp_path: Path) -> None:
    """Keep unknown-source RIS loading compatible with the shared defaults."""
    ris_file = tmp_path / "unknown.ris"
    ris_file.write_text(
        "TY  - JOUR\nTI  - Shared mapping\nPY  - 2022/01/01\n" "PMID  - 12345\nER  -\n",
        encoding="utf-8",
    )

    record = next(
        iter(
            UnknownSearchSource._load_ris(  # pylint: disable=protected-access
                filename=ris_file, logger=logging.getLogger(__name__)
            ).values()
        )
    )

    assert record[Fields.ENTRYTYPE] == ENTRYTYPES.ARTICLE
    assert record[Fields.TITLE] == "Shared mapping"
    assert record[Fields.YEAR] == "2022"
    assert record[Fields.PUBMED_ID] == "12345"


def test_clean_ris_numbered_record_prefixes(tmp_path: Path) -> None:
    """Remove only standalone numbered-record markers while cleaning RIS text."""
    loader = colrev.loader.ris.RISLoader(
        filename=tmp_path / "records.ris",
        unique_id_field="ID",
    )

    cleaned = loader._clean_text(  # pylint: disable=protected-access
        "  12.  \nTY  - JOUR\nTI  - Chapter 12. Introduction\nER  -\n"
    )

    assert "12." not in cleaned.splitlines()
    assert "TI  - Chapter 12. Introduction" in cleaned.splitlines()


def test_load_nested_knowledge_numbered_records() -> None:
    """Load numbered Nested Knowledge RIS records through the public loader."""

    def entrytype_setter(record_dict: dict) -> None:
        record_dict[Fields.ENTRYTYPE] = {"JOUR": "article"}.get(
            record_dict.pop("TY"), "misc"
        )

    def field_mapper(record_dict: dict) -> None:
        key_map = {
            "AB": Fields.ABSTRACT,
            "AU": Fields.AUTHOR,
            "DO": Fields.DOI,
            "JO": Fields.JOURNAL,
            "PY": Fields.YEAR,
            "TI": Fields.TITLE,
        }
        for ris_key, colrev_key in key_map.items():
            if ris_key in record_dict:
                record_dict[colrev_key] = record_dict.pop(ris_key)

    fixture = (
        Path(__file__).parents[1] / "data/ris/nestedknowledge_numbered_records.ris"
    )
    records = colrev.loader.load_utils.load(
        filename=fixture,
        unique_id_field="ID",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )

    assert len(records) == 3
    assert list(records) == ["1", "2", "3"]
    assert [record[Fields.ENTRYTYPE] for record in records.values()] == [
        "article",
        "article",
        "article",
    ]
    assert [record[Fields.TITLE] for record in records.values()] == (
        NESTED_KNOWLEDGE_TITLES
    )
    assert [record[Fields.YEAR] for record in records.values()] == [
        "2011",
        "2003",
        "2005",
    ]
    assert records["1"][Fields.DOI] == "10.1258/ebm.2010.011f01"
    assert Fields.DOI not in records["2"]
    assert records["3"][Fields.DOI] == "10.1007/s00595-004-2918-y"
    assert records["3"][Fields.ABSTRACT].startswith("PURPOSE: To investigate")
    assert records["3"][Fields.AUTHOR] == "M., Aban N.Cinel L.Tamer L.Aktas A.Aban"

    parsed_values = {
        value
        for record in records.values()
        for value in record.values()
        if isinstance(value, str)
    }
    assert not {"1.", "2.", "3."} & parsed_values


def test_load_ris_entries(tmp_path, helpers):  # type: ignore
    os.chdir(tmp_path)

    def entrytype_setter(record_dict: dict) -> None:
        record_dict[Fields.ENTRYTYPE] = "article"

    def field_mapper(record_dict: dict) -> None:
        record_dict[Fields.TITLE] = record_dict.pop("TI", "")
        record_dict[Fields.AUTHOR] = " and ".join(record_dict.pop("AU", ""))
        record_dict[Fields.YEAR] = record_dict.pop("PY", "")
        record_dict[Fields.JOURNAL] = record_dict.pop("T2", "")
        record_dict[Fields.DOI] = record_dict.pop("DO", "")
        record_dict[Fields.NUMBER] = record_dict.pop("IS", "")
        record_dict[Fields.VOLUME] = record_dict.pop("VL", "")
        record_dict[Fields.ISSN] = record_dict.pop("SN", "")
        if "SP" in record_dict and "EP" in record_dict:
            record_dict[Fields.PAGES] = (
                f"{record_dict.pop('SP')}--{record_dict.pop('EP')}"
            )
        for key, value in record_dict.items():
            record_dict[key] = str(value)

    # only supports ris
    with pytest.raises(NotImplementedError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/table.ptvc").touch()
        try:
            colrev.loader.load_utils.load(
                filename=Path("data/search/table.ptvc"),
            )
        finally:
            Path("data/search/table.ptvc").unlink()

    # file must exist
    with pytest.raises(FileNotFoundError):
        colrev.loader.load_utils.load(
            filename=Path("non-existent.ris"),
            unique_id_field="doi",
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            empty_if_file_not_exists=False,
        )

    helpers.retrieve_test_file(
        source=Path("2_loader/data/ris_data.ris"),
        target=Path("ris_data.ris"),
    )

    entries = colrev.loader.load_utils.load(
        filename=Path("ris_data.ris"),
        unique_id_field="DO",
        entrytype_setter=entrytype_setter,
        field_mapper=field_mapper,
    )

    assert len(entries) == 2
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.TITLE]
        == "Title of a conference paper"
    )
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.AUTHOR]
        == "A. Author-One and B. Author-Two and C. Author-Three and D. Author-Four and E. Author-Five"
    )
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.JOURNAL]
        == "Secondary Title (booktitle title, if applicable)"
    )
    assert entries["10.1234/Random-name55555.2020.00050"][Fields.PAGES] == "183--186"
    assert entries["10.1234/Random-name55555.2020.00050"][Fields.YEAR] == "2020"
    assert (
        entries["10.1234/Random-name55555.2020.00050"][Fields.DOI]
        == "10.1234/Random-name55555.2020.00050"
    )
    assert entries["10.1234/Random-name55555.2020.00050"][Fields.ISSN] == "1111-3333"
    assert entries["10.1234/Random-name55555.2020.00050"]["Y1"] == "4-8 Aug. 2020"

    assert entries["10.1111/MC.2017.66"]["TY"] == "JOUR"
    assert entries["10.1111/MC.2017.66"][Fields.TITLE] == "Title of a journal paper"
    assert (
        entries["10.1111/MC.2017.66"][Fields.JOURNAL]
        == "Secondary Title (journal title, if applicable)"
    )
    assert entries["10.1111/MC.2017.66"][Fields.PAGES] == "14--25"
    assert (
        entries["10.1111/MC.2017.66"][Fields.AUTHOR]
        == "A. Author-One and B. Author-Two and C. Author-Three"
    )
    assert entries["10.1111/MC.2017.66"][Fields.YEAR] == "2017"
    assert entries["10.1111/MC.2017.66"][Fields.DOI] == "10.1111/MC.2017.66"
    assert (
        entries["10.1111/MC.2017.66"][Fields.JOURNAL]
        == "Secondary Title (journal title, if applicable)"
    )
    assert entries["10.1111/MC.2017.66"][Fields.NUMBER] == "3"
    assert entries["10.1111/MC.2017.66"][Fields.VOLUME] == "50"
    assert entries["10.1111/MC.2017.66"][Fields.ISSN] == "1111-2222"

    nr_records = colrev.loader.load_utils.get_nr_records(Path("ris_data.ris"))
    assert 2 == nr_records
