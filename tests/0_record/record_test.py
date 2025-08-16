#!/usr/bin/env python
"""Tests of the Record class"""
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState

# pylint: disable=too-many-lines
# pylint: disable=line-too-long
# flake8: noqa

v1 = {
    Fields.ID: "r1",
    Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
    Fields.MD_PROV: {
        Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
        Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
        Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
        Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
        Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
        Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
        Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
    },
    Fields.D_PROV: {},
    Fields.STATUS: RecordState.md_prepared,
    Fields.ORIGIN: ["import.bib/id_0001"],
    Fields.YEAR: "2020",
    Fields.TITLE: "EDITORIAL",
    Fields.AUTHOR: "Rai, Arun",
    Fields.JOURNAL: "MIS Quarterly",
    Fields.VOLUME: "45",
    Fields.NUMBER: "1",
    Fields.PAGES: "1--3",
}
v2 = {
    Fields.ID: "r1",
    Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
    Fields.MD_PROV: {
        Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
        Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
        Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
        Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
        Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
        Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
        Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
    },
    Fields.D_PROV: {},
    Fields.STATUS: RecordState.md_prepared,
    Fields.ORIGIN: ["import.bib/id_0001"],
    Fields.YEAR: "2020",
    Fields.TITLE: "EDITORIAL",
    Fields.AUTHOR: "Rai, A",
    Fields.JOURNAL: "MISQ",
    Fields.VOLUME: "45",
    Fields.NUMBER: "1",
    Fields.PAGES: "1--3",
}

r1 = colrev.record.record.Record(v1)
r2 = colrev.record.record.Record(v2)


def test_eq() -> None:
    """Test equality of records"""
    # pylint: disable=comparison-with-itself
    assert r1 == r1
    assert r1 != r2


def test_copy() -> None:
    """Test record copies"""
    r1_cop = r1.copy()
    assert r1 == r1_cop


def test_get_data() -> None:
    """Test record.get_data()"""
    expected = v1
    r1.data[Fields.ORIGIN] = "import.bib/id_0001"
    actual = r1.get_data()
    assert expected == actual


def test_update_field() -> None:
    """Test record.update_field()"""
    r2_mod = r2.copy()

    # Test append_edit=True / identifying_field
    r2_mod.update_field(
        key=Fields.JOURNAL, value="Mis Quarterly", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = r2_mod.data[Fields.MD_PROV][Fields.JOURNAL]["source"]
    assert expected == actual

    # Test append_edit=True / non-identifying_field
    r2_mod.update_field(
        key="non_identifying_field", value="nfi_value", source="import.bib/id_0001"
    )
    r2_mod.update_field(
        key="non_identifying_field", value="changed", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = r2_mod.data[Fields.D_PROV]["non_identifying_field"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / identifying field
    del r2_mod.data[Fields.MD_PROV][Fields.JOURNAL]
    r2_mod.update_field(
        key=Fields.JOURNAL,
        value="Mis Quarterly",
        source="test",
        append_edit=True,
        keep_source_if_equal=False,
    )
    expected = "original|test"
    actual = r2_mod.data[Fields.MD_PROV][Fields.JOURNAL]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / non-identifying field
    del r2_mod.data[Fields.D_PROV]["non_identifying_field"]
    r2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    expected = "original|test"
    actual = r2_mod.data[Fields.D_PROV]["non_identifying_field"]["source"]
    assert expected == actual


def test_rename_field() -> None:
    """Test record.rename_field()"""

    r2_mod = r2.copy()

    r2_mod.rename_field(key="xyz", new_key="abc")

    # Identifying field
    r2_mod.rename_field(key=Fields.JOURNAL, new_key=Fields.BOOKTITLE)
    expected = "import.bib/id_0001|rename-from:journal"
    actual = r2_mod.data[Fields.MD_PROV][Fields.BOOKTITLE]["source"]
    assert expected == actual
    assert Fields.JOURNAL not in r2_mod.data
    assert Fields.JOURNAL not in r2_mod.data[Fields.MD_PROV]

    # Non-identifying field
    r2_mod.update_field(
        key="link", value="https://www.test.org", source="import.bib/id_0001"
    )
    r2_mod.rename_field(key="link", new_key=Fields.URL)
    expected = "import.bib/id_0001|rename-from:link"
    actual = r2_mod.data[Fields.D_PROV][Fields.URL]["source"]
    assert expected == actual
    assert "link" not in r2_mod.data
    assert "link" not in r2_mod.data[Fields.D_PROV]

    # Identifying field (missing)
    r2_mod = r2.copy()
    del r2_mod.data[Fields.MD_PROV][Fields.JOURNAL]
    r2_mod.rename_field(key=Fields.JOURNAL, new_key=Fields.BOOKTITLE)
    expected = "|rename-from:journal"
    actual = r2_mod.data[Fields.MD_PROV][Fields.BOOKTITLE]["source"]
    assert expected == actual
    assert Fields.JOURNAL not in r2_mod.data
    assert Fields.JOURNAL not in r2_mod.data[Fields.MD_PROV]

    # Non-identifying field (missing)
    r2_mod = r2.copy()
    r2_mod.update_field(
        key="link", value="https://www.test.org", source="import.bib/id_0001"
    )
    del r2_mod.data[Fields.D_PROV]["link"]
    r2_mod.rename_field(key="link", new_key=Fields.URL)
    expected = "|rename-from:link"
    actual = r2_mod.data[Fields.D_PROV][Fields.URL]["source"]
    assert expected == actual
    assert "link" not in r2_mod.data
    assert "link" not in r2_mod.data[Fields.D_PROV]


def test_remove_field() -> None:
    """Test record.remove_field()"""

    r2_mod = r2.copy()
    del r2_mod.data[Fields.MD_PROV][Fields.NUMBER]
    r2_mod.remove_field(key=Fields.NUMBER, not_missing_note=True, source="test")
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "test", "note": f"IGNORE:{DefectCodes.MISSING}"},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, A",
        Fields.JOURNAL: "MISQ",
        Fields.VOLUME: "45",
        Fields.PAGES: "1--3",
    }

    actual = r2_mod.data
    print(actual)
    assert expected == actual
    r2_mod.data.pop(Fields.MD_PROV, None)
    r2_mod.remove_field(key=Fields.PAGES, not_missing_note=True, source="test")


def test_diff() -> None:
    """Test record.diff()"""

    r2_mod = r2.copy()
    r2_mod.remove_field(key=Fields.PAGES)
    # keep_source_if_equal
    r2_mod.update_field(
        key=Fields.JOURNAL, value="MISQ", source="test", keep_source_if_equal=True
    )

    r2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    r2_mod.update_field(key=Fields.BOOKTITLE, value="ICIS", source="test")
    r2_mod.update_field(key=Fields.PUBLISHER, value="Elsevier", source="test")
    print(r1.get_diff(r2_mod))
    expected = [
        (
            "add",
            "",
            [
                (Fields.BOOKTITLE, {"source": "test", "note": ""}),
                (Fields.PUBLISHER, {"source": "test", "note": ""}),
            ],
        ),
        ("remove", "", [(Fields.PAGES, {"source": "import.bib/id_0001", "note": ""})]),
        ("change", Fields.AUTHOR, ("Rai, Arun", "Rai, A")),
        ("change", Fields.JOURNAL, ("MIS Quarterly", "MISQ")),
        ("add", "", [(Fields.BOOKTITLE, "ICIS"), (Fields.PUBLISHER, "Elsevier")]),
        ("remove", "", [(Fields.PAGES, "1--3")]),
    ]
    actual = r1.get_diff(r2_mod)
    assert expected == actual

    print(r1.get_diff(r2_mod, identifying_fields_only=False))
    expected = [
        (
            "add",
            Fields.MD_PROV,
            [
                (Fields.BOOKTITLE, {"source": "test", "note": ""}),
                (Fields.PUBLISHER, {"source": "test", "note": ""}),
            ],
        ),
        (
            "remove",
            Fields.MD_PROV,
            [(Fields.PAGES, {"source": "import.bib/id_0001", "note": ""})],
        ),
        (
            "add",
            Fields.D_PROV,
            [("non_identifying_field", {"source": "test", "note": ""})],
        ),
        ("change", Fields.AUTHOR, ("Rai, Arun", "Rai, A")),
        ("change", Fields.JOURNAL, ("MIS Quarterly", "MISQ")),
        (
            "add",
            "",
            [
                ("non_identifying_field", "nfi_value"),
                (Fields.BOOKTITLE, "ICIS"),
                (Fields.PUBLISHER, "Elsevier"),
            ],
        ),
        ("remove", "", [(Fields.PAGES, "1--3")]),
    ]
    actual = r1.get_diff(r2_mod, identifying_fields_only=False)
    assert expected == actual


def test_change_entrytype_inproceedings() -> None:
    """Test record.change_entrytype(ENTRYTYPES.INPROCEEDINGS)"""

    r1_mod = r1.copy()
    r1_mod.data[Fields.VOLUME] = "UNKNOWN"
    r1_mod.data[Fields.NUMBER] = "UNKNOWN"
    r1_mod.data[Fields.TITLE] = "Editorial"
    r1_mod.data[Fields.LANGUAGE] = "eng"
    r1_mod.update_field(
        key=Fields.PUBLISHER,
        value="Elsevier",
        source="import.bib/id_0001",
        note="inconsistent-with-entrytype",
    )
    r1_mod.change_entrytype(ENTRYTYPES.INPROCEEDINGS)
    print(r1_mod.data)
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
            Fields.PUBLISHER: {"source": "import.bib/id_0001", "note": ""},
            Fields.BOOKTITLE: {
                "source": "import.bib/id_0001|rename-from:journal",
                "note": "",
            },
        },
        Fields.D_PROV: {"language": {"note": "", "source": "manual"}},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.BOOKTITLE: "MIS Quarterly",
        Fields.YEAR: "2020",
        Fields.TITLE: "Editorial",
        Fields.AUTHOR: "Rai, Arun",
        Fields.PAGES: "1--3",
        Fields.PUBLISHER: "Elsevier",
        Fields.LANGUAGE: "eng",
    }
    actual = r1_mod.data
    assert expected == actual

    r1_mod.change_entrytype(ENTRYTYPES.MASTERSTHESIS)

    with pytest.raises(
        colrev.exceptions.MissingRecordQualityRuleSpecification,
    ):
        r1_mod.change_entrytype("dialoge")


def test_change_entrytype_inproceedings_2() -> None:

    record_dict = {
        Fields.ID: "r2",
        Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
        Fields.MD_PROV: {
            Fields.AUTHOR: {"source": "files.bib/000025", "note": ""},
            Fields.TITLE: {"source": "files.bib/000025", "note": ""},
            Fields.JOURNAL: {"source": "generic_field_requirements", "note": "missing"},
            Fields.YEAR: {"source": "generic_field_requirements", "note": ""},
            Fields.VOLUME: {"source": "generic_field_requirements", "note": "missing"},
            Fields.NUMBER: {"source": "generic_field_requirements", "note": "missing"},
        },
        Fields.STATUS: RecordState.md_needs_manual_preparation,
        Fields.ORIGIN: ["files.bib/000025"],
        Fields.AUTHOR: "Aydin, Ömer and Karaarslan, Enis",
        Fields.BOOKTITLE: "Emerging Computer Technologies",
        Fields.TITLE: "OpenAI ChatGPT Generated Literature Review: Digital Twin in Healthcare",
        Fields.YEAR: "2022",
        Fields.PAGES: "22--31",
    }
    record = colrev.record.record.Record(record_dict)
    record.change_entrytype(ENTRYTYPES.INPROCEEDINGS)

    expected = {
        Fields.ID: "r2",
        Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
        Fields.D_PROV: {},
        Fields.MD_PROV: {
            Fields.AUTHOR: {"source": "files.bib/000025", "note": ""},
            Fields.TITLE: {"source": "files.bib/000025", "note": ""},
            Fields.BOOKTITLE: {"source": "manual", "note": ""},
            Fields.YEAR: {"source": "generic_field_requirements", "note": ""},
            Fields.PAGES: {"source": "manual", "note": ""},
        },
        Fields.STATUS: RecordState.md_needs_manual_preparation,
        Fields.ORIGIN: ["files.bib/000025"],
        Fields.AUTHOR: "Aydin, Ömer and Karaarslan, Enis",
        Fields.BOOKTITLE: "Emerging Computer Technologies",
        Fields.TITLE: "OpenAI ChatGPT Generated Literature Review: Digital Twin in Healthcare",
        Fields.YEAR: "2022",
        Fields.PAGES: "22--31",
    }

    assert record.data == expected


def test_change_entrytype_article() -> None:
    """Test record.change_entrytype(ENTRYTYPES.ARTICLE)"""

    input_value = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
            Fields.PUBLISHER: {"source": "import.bib/id_0001", "note": ""},
            Fields.BOOKTITLE: {
                "source": "import.bib/id_0001",
                "note": "",
            },
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.BOOKTITLE: "MIS Quarterly",
        Fields.YEAR: "2020",
        Fields.TITLE: "Editorial",
        Fields.AUTHOR: "Rai, Arun",
        Fields.PAGES: "1--3",
        Fields.PUBLISHER: "Elsevier",
        Fields.LANGUAGE: "eng",
    }
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
            Fields.PUBLISHER: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {
                "source": "import.bib/id_0001|rename-from:booktitle",
                "note": "",
            },
            Fields.VOLUME: {
                "source": "generic_field_requirements",
                "note": DefectCodes.MISSING,
            },
            Fields.NUMBER: {
                "source": "generic_field_requirements",
                "note": DefectCodes.MISSING,
            },
        },
        Fields.D_PROV: {"language": {"note": "", "source": "manual"}},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "Editorial",
        Fields.AUTHOR: "Rai, Arun",
        Fields.PAGES: "1--3",
        Fields.PUBLISHER: "Elsevier",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "UNKNOWN",
        Fields.NUMBER: "UNKNOWN",
        Fields.LANGUAGE: "eng",
    }
    rec = colrev.record.record.Record(input_value)
    rec.change_entrytype(ENTRYTYPES.ARTICLE)
    actual = rec.data
    assert expected == actual


def test_add_provenance_all() -> None:
    """Test record.add_provenance_all()"""

    r1_mod = r1.copy()
    del r1_mod.data[Fields.MD_PROV]
    r1_mod.add_provenance_all(source="import.bib/id_0001")
    print(r1_mod.data)
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
    }
    actual = r1_mod.data
    assert expected == actual

    # Curated
    r1_mod = r1.copy()
    r1_mod.data[Fields.MD_PROV] = {
        FieldValues.CURATED: {"source": "manual", "note": ""}
    }
    r1_mod.data["custom_field"] = "test"
    r1_mod.add_provenance_all(source="import.bib/id_0001")
    print(r1_mod.data)
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
        "custom_field": "test",
        Fields.MD_PROV: {FieldValues.CURATED: {"source": "manual", "note": ""}},
        Fields.D_PROV: {"custom_field": {"source": "import.bib/id_0001", "note": ""}},
    }
    actual = r1_mod.data
    assert expected == actual


def test_format_bib_style() -> None:
    """Test record.format_bib_style()"""

    expected = "Rai, Arun (2020) EDITORIAL. MIS Quarterly, (45) 1"
    actual = r1.format_bib_style()
    assert expected == actual


def test_print_citation_format() -> None:
    """Test record.print_citation_format()"""

    r1.print_citation_format()


def test_get_value() -> None:
    """Test record.get_value()"""
    expected = "Rai, Arun"
    actual = r1.get_value(Fields.AUTHOR)
    assert expected == actual

    expected = "Rai, Arun"
    actual = r1.get_value(Fields.AUTHOR, default="custom_file")
    assert expected == actual

    expected = "custom_file"
    actual = r1.get_value(Fields.FILE, default="custom_file")
    assert expected == actual


def test_get_colrev_id() -> None:
    """Test record.get_colrev_id()"""

    # Test type: phdthesis
    r1_mod = r1.copy()
    r1_mod.data[Fields.ENTRYTYPE] = "phdthesis"
    r1_mod.data["school"] = "University of Minnesota"
    r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    expected = "colrev_id1:|phdthesis|university-of-minnesota|2020|rai|editorial"
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: techreport
    r1_mod = r1.copy()
    r1_mod.data[Fields.ENTRYTYPE] = "techreport"
    r1_mod.data["institution"] = "University of Minnesota"
    r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    expected = "colrev_id1:|techreport|university-of-minnesota|2020|rai|editorial"
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: inproceedings
    r1_mod = r1.copy()
    r1_mod.data[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
    r1_mod.data[Fields.BOOKTITLE] = "International Conference on Information Systems"
    r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    expected = "colrev_id1:|p|international-conference-on-information-systems|2020|rai|editorial"

    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    r1_mod = r1.copy()
    r1_mod.data[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
    r1_mod.data[Fields.JOURNAL] = "Journal of Management Information Systems"
    r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    expected = "colrev_id1:|a|journal-of-management-information-systems|45|1|2020|rai|editorial"

    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    r1_mod = r1.copy()
    r1_mod.data[Fields.ENTRYTYPE] = "monogr"
    r1_mod.data[Fields.SERIES] = "Lecture notes in cs"
    r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    expected = "colrev_id1:|monogr|lecture-notes-in-cs|2020|rai|editorial"
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    r1_mod = r1.copy()
    r1_mod.data[Fields.ENTRYTYPE] = "online"
    r1_mod.data[Fields.URL] = "www.loc.de/subpage.html"
    r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    expected = "colrev_id1:|online|wwwlocde-subpagehtml|2020|rai|editorial"
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # def test_get_colrev_id() -> None:
    # """Test record.get_colrev_id()"""

    # r1_mod = r1.copy()
    # r1_mod.data[Fields.COLREV_ID] = r1_mod.get_colrev_id()
    # expected = "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"
    # actual = r1_mod.get_colrev_id()
    # assert expected == actual

    # Test str colrev_id
    r1_mod = r1.copy()
    r1_mod.data[Fields.COLREV_ID] = "colrev_id1:|a|nature|45|1|2020|rai|editorial"
    expected = "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test list colrev_id
    r1_mod = r1.copy()
    r1_mod.data[Fields.COLREV_ID] = "colrev_id1:|a|nature|45|1|2020|rai|editorial"
    expected = "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"
    actual = r1_mod.get_colrev_id()
    assert expected == actual


def test_provenance() -> None:
    """Test record provenance"""

    r1_mod = r1.copy()

    r1_mod.add_field_provenance(key=Fields.URL, source="manual", note="test")
    expected = "manual"
    actual = r1_mod.data[Fields.D_PROV][Fields.URL]["source"]
    assert expected == actual

    expected = "test"
    actual = r1_mod.data[Fields.D_PROV][Fields.URL]["note"]
    assert expected == actual

    r1_mod.add_field_provenance_note(key=Fields.ID, note="test")  # pass / no changes
    assert Fields.ID not in r1_mod.data[Fields.MD_PROV]
    assert Fields.ID not in r1_mod.data[Fields.D_PROV]

    r1_mod.add_field_provenance_note(key=Fields.URL, note="1")
    expected = "test,1"
    actual = r1_mod.data[Fields.D_PROV][Fields.URL]["note"]
    assert expected == actual

    r1_mod.data[Fields.D_PROV][Fields.URL]["note"] = ""
    r1_mod.add_field_provenance_note(key=Fields.URL, note="1")
    expected = "1"
    actual = r1_mod.data[Fields.D_PROV][Fields.URL]["note"]
    assert expected == actual

    # expected = {"source": "manual", "note": "test,1"}  # type: ignore
    # actual = r1_mod.get_field_provenance(key=Fields.URL)
    # assert expected == actual

    r1_mod.add_field_provenance(key=Fields.AUTHOR, source="manual", note="test")
    expected = "test"
    actual = r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["note"]
    assert expected == actual

    actual = r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["source"]
    expected = "manual"
    assert expected == actual

    r1_mod.add_field_provenance_note(key=Fields.AUTHOR, note="check")
    expected = "test,check"
    actual = r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["note"]
    assert expected == actual

    r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["note"] = "IGNORE:missing,other"
    r1_mod.add_field_provenance(key=Fields.AUTHOR, source="manual", note="missing")
    expected = "other,missing"
    actual = r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["note"]
    assert expected == actual

    r1_mod.add_field_provenance(key=Fields.AUTHOR, source="manual", note="third")
    expected = "other,missing,third"
    actual = r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["note"]
    assert expected == actual

    r1_mod.add_field_provenance(key=Fields.AUTHOR, source="manual", note="third")
    expected = "other,missing,third"  # already added
    actual = r1_mod.data[Fields.MD_PROV][Fields.AUTHOR]["note"]
    assert expected == actual


def test_set_masterdata_complete() -> None:
    """Test record.set_masterdata_complete()"""

    # field=UNKNOWN and no not_missing note
    r1_mod = r1.copy()
    r1_mod.data[Fields.NUMBER] = "UNKNOWN"
    r1_mod.data[Fields.VOLUME] = "UNKNOWN"
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "test", "note": f"IGNORE:{DefectCodes.MISSING}"},
            Fields.NUMBER: {"source": "test", "note": f"IGNORE:{DefectCodes.MISSING}"},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.PAGES: "1--3",
    }
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    actual = r1_mod.data
    print(r1_mod.data)
    assert expected == actual

    # missing fields and no colrev_masterdata_provenance
    r1_mod = r1.copy()
    del r1_mod.data[Fields.VOLUME]
    del r1_mod.data[Fields.NUMBER]
    del r1_mod.data[Fields.MD_PROV][Fields.NUMBER]
    del r1_mod.data[Fields.MD_PROV][Fields.VOLUME]
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "test", "note": f"IGNORE:{DefectCodes.MISSING}"},
            Fields.NUMBER: {"source": "test", "note": f"IGNORE:{DefectCodes.MISSING}"},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.PAGES: "1--3",
    }
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    actual = r1_mod.data
    print(r1_mod.data)
    assert expected == actual

    # misleading DefectCodes.MISSING note
    r1_mod = r1.copy()
    r1_mod.data[Fields.MD_PROV][Fields.VOLUME]["note"] = DefectCodes.MISSING
    r1_mod.data[Fields.MD_PROV][Fields.NUMBER]["note"] = DefectCodes.MISSING
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    actual = r1_mod.data
    print(r1_mod.data)
    assert expected == actual

    r1_mod.data[Fields.MD_PROV] = {"CURATED": {"source": ":https...", "note": ""}}
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    del r1_mod.data[Fields.MD_PROV]
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)


def test_set_masterdata_consistent() -> None:
    """Test record.set_masterdata_consistent()"""

    r1_mod = r1.copy()
    r1_mod.data[Fields.MD_PROV][Fields.JOURNAL][
        "note"
    ] = DefectCodes.INCONSISTENT_WITH_ENTRYTYPE
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }
    r1_mod.set_masterdata_consistent()
    actual = r1_mod.data
    print(actual)
    assert expected == actual

    r1_mod = r1.copy()
    del r1_mod.data[Fields.MD_PROV]
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {},
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }
    r1_mod.set_masterdata_consistent()
    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_reset_pdf_provenance_notes() -> None:
    """Test record.reset_pdf_provenance_notes()"""

    # defects
    r1_mod = r1.copy()
    r1_mod.data[Fields.D_PROV][Fields.FILE] = {
        "source": "test",
        "note": "defects",
    }
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {
            Fields.FILE: {"source": "test", "note": ""},
        },
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }
    r1_mod.reset_pdf_provenance_notes()
    actual = r1_mod.data
    assert expected == actual

    # missing provenance
    r1_mod = r1.copy()
    del r1_mod.data[Fields.D_PROV]
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {Fields.FILE: {"source": "ORIGINAL", "note": ""}},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }
    r1_mod.reset_pdf_provenance_notes()
    actual = r1_mod.data
    assert expected == actual

    # file missing in missing provenance
    r1_mod = r1.copy()
    # del r1_mod.data[Fields.D_PROV][Fields.FILE]
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {
            Fields.FILE: {"source": "NA", "note": ""},
        },
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }
    r1_mod.reset_pdf_provenance_notes()
    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_get_tei_filename() -> None:
    """Test record.get_tei_filename()"""

    r1_mod = r1.copy()
    r1_mod.data[Fields.FILE] = "data/pdfs/Rai2020.pdf"
    expected = Path("data/.tei/Rai2020.tei.xml")
    actual = r1_mod.get_tei_filename()
    assert expected == actual


def test_merge_select_non_all_caps() -> None:
    """Test record.merge() - all-caps cases"""
    # Select title-case (not all-caps title) and full author name

    r1_mod = colrev.record.record.Record(v1).copy()
    r2_mod = colrev.record.record.Record(v2).copy()
    print(r1_mod)
    print(r2_mod)
    r1_mod.data[Fields.TITLE] = "Editorial"
    r2_mod.data[Fields.ORIGIN] = ["import.bib/id_0002"]
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": "language-unknown"},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.VOLUME: {"source": "import.bib/id_0001", "note": ""},
            Fields.NUMBER: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001", "import.bib/id_0002"],
        Fields.YEAR: "2020",
        Fields.TITLE: "Editorial",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    r1_mod.merge(r2_mod, default_source="test")
    actual = r1_mod.data
    assert expected == actual


def test_merge_local_index(mocker) -> None:  # type: ignore
    """Test record.merge() - local-index"""

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Gerit Wagner", "gerit.wagner@uni-bamberg.de"),
    )

    r1_mod = colrev.record.record.Record(
        {
            Fields.ID: "r1",
            Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
            Fields.D_PROV: {},
            Fields.MD_PROV: {Fields.VOLUME: {"source": "source-1", "note": ""}},
            Fields.STATUS: RecordState.md_prepared,
            Fields.ORIGIN: ["orig1"],
            Fields.TITLE: "EDITORIAL",
            Fields.AUTHOR: "Rai, Arun",
            Fields.JOURNAL: "MIS Quarterly",
            Fields.VOLUME: "45",
            Fields.PAGES: "1--3",
        }
    )
    r2_mod = colrev.record.record.Record(
        {
            Fields.ID: "r2",
            Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
            Fields.D_PROV: {},
            Fields.MD_PROV: {
                Fields.VOLUME: {"source": "source-1", "note": ""},
                Fields.NUMBER: {"source": "source-1", "note": ""},
            },
            Fields.STATUS: RecordState.md_prepared,
            Fields.ORIGIN: ["orig2"],
            Fields.TITLE: "Editorial",
            Fields.AUTHOR: "ARUN RAI",
            Fields.JOURNAL: "MISQ",
            Fields.VOLUME: "45",
            Fields.NUMBER: "4",
            Fields.PAGES: "1--3",
        }
    )

    r1_mod.merge(r2_mod, default_source="test")
    print(r1_mod)


def test_get_container_title() -> None:
    """Test record.get_container_title()"""

    r1_mod = r1.copy()

    # article
    expected = "MIS Quarterly"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
    r1_mod.data[Fields.BOOKTITLE] = "ICIS"
    expected = "ICIS"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data[Fields.ENTRYTYPE] = "book"
    r1_mod.data[Fields.TITLE] = "Momo"
    expected = "Momo"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data[Fields.ENTRYTYPE] = "inbook"
    r1_mod.data[Fields.BOOKTITLE] = "Book title a"
    expected = "Book title a"
    actual = r1_mod.get_container_title()
    assert expected == actual

    del r1_mod.data[Fields.ENTRYTYPE]
    r1_mod.data[Fields.JOURNAL] = "MIS Quarterly"
    expected = "MIS Quarterly"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data[Fields.ENTRYTYPE] = "unknown"
    expected = "NA"
    actual = r1_mod.get_container_title()
    assert expected == actual


def test_complete_provenance() -> None:
    """Test record.complete_provenance()"""

    r1_mod = r1.copy()
    del r1_mod.data[Fields.MD_PROV]
    del r1_mod.data[Fields.D_PROV]
    r1_mod.update_field(key=Fields.URL, value="www.test.eu", source="asdf")

    r1_mod.complete_provenance(source_info="test")
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.D_PROV: {Fields.URL: {"source": "test", "note": ""}},
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
        Fields.URL: "www.test.eu",
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "test", "note": ""},
            Fields.TITLE: {"source": "test", "note": ""},
            Fields.AUTHOR: {"source": "test", "note": ""},
            Fields.JOURNAL: {"source": "test", "note": ""},
            Fields.VOLUME: {"source": "test", "note": ""},
            Fields.NUMBER: {"source": "test", "note": ""},
            Fields.PAGES: {"source": "test", "note": ""},
        },
    }
    actual = r1_mod.data
    assert expected == actual


def test_get_toc_key() -> None:
    """Test record.get_toc_key()"""

    expected = "mis-quarterly|45|1"
    actual = r1.get_toc_key()
    assert expected == actual

    input_value = {
        Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
        Fields.BOOKTITLE: "International Conference on Information Systems",
        Fields.YEAR: "2012",
    }
    expected = "international-conference-on-information-systems|2012"
    actual = colrev.record.record.Record(input_value).get_toc_key()
    assert expected == actual

    input_value = {
        Fields.ENTRYTYPE: ENTRYTYPES.PHDTHESIS,
        Fields.ID: "test",
        Fields.TITLE: "Thesis on asteroids",
        Fields.YEAR: "2012",
    }
    with pytest.raises(
        colrev_exceptions.NotTOCIdentifiableException,
        match="ENTRYTYPE .* not toc-identifiable",
    ):
        colrev.record.record.Record(input_value).get_toc_key()


def test_prescreen_exclude() -> None:
    """Test record.prescreen_exclude()"""

    r1_mod = r1.copy()
    r1_mod.data[Fields.STATUS] = RecordState.rev_synthesized
    r1_mod.data[Fields.NUMBER] = "UNKNOWN"
    r1_mod.data[Fields.VOLUME] = "UNKNOWN"

    r1_mod.prescreen_exclude(reason="retracted", print_warning=True)
    expected = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.MD_PROV: {
            Fields.YEAR: {"source": "import.bib/id_0001", "note": ""},
            Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
            Fields.AUTHOR: {"source": "import.bib/id_0001", "note": ""},
            Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
            Fields.PAGES: {"source": "import.bib/id_0001", "note": ""},
        },
        Fields.D_PROV: {},
        Fields.STATUS: RecordState.rev_prescreen_excluded,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.PAGES: "1--3",
        Fields.PRESCREEN_EXCLUSION: "retracted",
        Fields.RETRACTED: FieldValues.RETRACTED,
    }

    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_get_record_similarity() -> None:
    """Test record.get_record_similarity()"""

    v1 = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }
    v2 = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_prepared,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, A",
        Fields.JOURNAL: "MISQ",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    r1 = colrev.record.record.Record(v1)
    r2 = colrev.record.record.Record(v2)

    actual = colrev.record.record.Record.get_record_similarity(record_a=r1, record_b=r2)
    expected = 0.9074
    assert expected == actual


def test_set_status() -> None:
    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.MD_PROV: {
            Fields.TITLE: {
                "source": "import.bib/id_0001",
                "note": DefectCodes.MOSTLY_ALL_CAPS,
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    record = colrev.record.record.Record(record_dict)
    record.set_status(RecordState.md_prepared)
    expected = RecordState.md_prepared
    assert expected == record.data[Fields.STATUS]


def test_defects() -> None:
    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.MD_PROV: {
            Fields.TITLE: {
                "source": "import.bib/id_0001",
                "note": DefectCodes.MOSTLY_ALL_CAPS,
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    record = colrev.record.record.Record(record_dict)
    actual = record.defects(Fields.TITLE)
    assert actual == [DefectCodes.MOSTLY_ALL_CAPS]
    assert record.has_quality_defects(key=Fields.TITLE)

    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.D_PROV: {
            "literature_review": {
                "source": "import.bib/id_0001",
                "note": "custom-defect",
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    record = colrev.record.record.Record(record_dict)
    actual = record.defects("literature_review")
    assert actual == ["custom-defect"]
    assert record.has_quality_defects(key="literature_review")


def test_has_fatal_quality_defects() -> None:
    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.INPROCEEDINGS,
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2009",
        Fields.TITLE: "The Working Lifeworld of Situated Subjects and the World System of Software Maintenance: Destabilizing a Distinction",
        Fields.AUTHOR: "Campagnolo, Gianmarco",
        Fields.JOURNAL: "All Sprouts Content",
        Fields.VOLUME: "9",
        Fields.NUMBER: "2",
        Fields.URL: "https://aisel.aisnet.org/sprouts_all/257",
        Fields.ABSTRACT: "This is a theory of the ways post-sale software maintenance processes relate with local contexts of software usage. The larger topic addressed by the theory is the relationship between situated subjects' life world and social theories and the possibility to define situations in contemporary analyses of global phenomena. The narrower topic concerns the covariance of local usage practices with software maintenance processes within and across public sector organizations. The theory builds upon fieldwork conducted since 2006 in a number of Italian public sector organizations. Three different approaches to software maintenance with their relation with local software usage practices have been devised: in-house providing, contract work, and internal maintenance. In this position paper, I will present some evidence only from the case of the in-house providing model.",
        Fields.DATE: "February 3, 2009",
    }

    record = colrev.record.record.Record(record_dict)
    assert not record.has_fatal_quality_defects()

    record_dict = {
        "ID": "Curran2020",
        "ENTRYTYPE": "article",
        "colrev_origin": ["web_of_science.bib/WOS:000616658300022"],
        "colrev_status": RecordState.md_needs_manual_preparation,  # type: ignore
        "colrev_masterdata_provenance": {  # type: ignore
            "author": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "journal": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "pages": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "title": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "volume": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "year": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "number": {"source": "generic_field_requirements", "note": "missing"},
        },
        "colrev_data_provenance": {  # type: ignore
            "abstract": {
                "source": "web_of_science.bib/WOS:000616658300022",
                "note": "",
            },
            "colrev.web_of_science.unique-id": {
                "source": "web_of_science.bib/WOS:000616658300022",
                "note": "",
            },
            "issn": {"source": "web_of_science.bib/WOS:000616658300022", "note": ""},
            "language": {"source": "LanguageDetector", "note": ""},
        },
        "colrev.web_of_science.unique-id": "WOS:000616658300022",
        "journal": "International Journal of Communication",
        "title": "Intersectional English(es) and the Gig Economy: Teaching English Online",
        "year": "2020",
        "volume": "14",
        "number": "UNKNOWN",
        "pages": "2667--2686",
        "abstract": "This article introduces LanguaSpeak, a heretofore underexplored digital platform that functions as a market for language learners and teachers. It argues that LanguaSpeak, through both its interface and users' communicative practice, unwittingly reinforces existing language ideologies, particularly around race. In making this argument, the article suggests the notion of ``intersectional English(es){''} as a means through which scholars can productively consider the ways in which race, nationality, and language intersect and are (re)enforced through online interfaces/interaction. Drawing on data collected from the profiles of English teachers from the United States and the Philippines, this article examines how language, nationality, and race intersect on LanguaSpeak. Key differences identified between the two countries' teachers include price and marketing strategies. Specifically, White male American teachers are found to enjoy significant advantages over other teachers, reflecting dominant language ideologies. This has implications for English language teaching and language discrimination more broadly.",
        "issn": "1932-8036",
        "author": "Curran, Nathaniel Ming",
        "language": "eng",
    }
    record = colrev.record.record.Record(record_dict)
    assert not record.has_fatal_quality_defects()


def test_get_field_provenance_source() -> None:
    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.D_PROV: {
            "custom_field": {
                "source": "import.bib/id_0001a",
                "note": DefectCodes.MOSTLY_ALL_CAPS,
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
        "custom_field": "test",
    }

    record = colrev.record.record.Record(record_dict)
    actual = record.get_field_provenance_source("custom_field")
    assert actual == "import.bib/id_0001a"

    record.data[Fields.D_PROV] = {}
    actual = record.get_field_provenance_source("custom_field")
    assert actual == "ORIGINAL"

    del record.data[Fields.D_PROV]
    actual = record.get_field_provenance_source("custom_field")
    assert actual == "ORIGINAL"


def test_get_field_provenance_notes() -> None:

    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.D_PROV: {
            "custom_field": {
                "source": "import.bib/id_0001a",
                "note": DefectCodes.MOSTLY_ALL_CAPS,
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
        "custom_field": "test",
    }

    record = colrev.record.record.Record(record_dict)
    actual = record.get_field_provenance_notes("custom_field")
    assert actual == [DefectCodes.MOSTLY_ALL_CAPS]

    record.data[Fields.D_PROV] = {}
    actual = record.get_field_provenance_notes("custom_field")
    assert actual == []


def test_is_retracted() -> None:

    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.D_PROV: {
            "custom_field": {
                "source": "import.bib/id_0001a",
                "note": DefectCodes.MOSTLY_ALL_CAPS,
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.AUTHOR: "Rai, Arun",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
        Fields.RETRACTED: FieldValues.RETRACTED,
    }

    record = colrev.record.record.Record(record_dict)
    assert record.is_retracted()

    del record.data[Fields.RETRACTED]
    actual = record.is_retracted()
    assert actual is False

    record.data["colrev.crossref.crossmark"] = "True"
    assert record.is_retracted()

    record.data["crossmark"] = "True"
    assert record.is_retracted()

    record.data["warning"] = "Withdrawn (according to DBLP)"
    assert record.is_retracted()


def test_ignored_defect(
    # quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    record_dict = {
        Fields.ID: "r1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.STATUS: RecordState.md_retrieved,
        Fields.D_PROV: {
            Fields.AUTHOR: {
                "source": "import.bib/id_0001a",
                "note": f"IGNORE:{DefectCodes.MISSING}",
            }
        },
        Fields.ORIGIN: ["import.bib/id_0001"],
        Fields.YEAR: "2020",
        Fields.TITLE: "EDITORIAL",
        Fields.JOURNAL: "MIS Quarterly",
        Fields.VOLUME: "45",
        Fields.NUMBER: "1",
        Fields.PAGES: "1--3",
    }

    record = colrev.record.record.Record(record_dict)
    record.change_entrytype(ENTRYTYPES.ARTICLE)  # Should not change anything
    assert record.ignored_defect(key=Fields.AUTHOR, defect=DefectCodes.MISSING)
