#!/usr/bin/env python
"""Tests of the Record class"""
from pathlib import Path

import pytest

import colrev.env.local_index
import colrev.exceptions as colrev_exceptions
import colrev.record

# pylint: disable=too-many-lines
# pylint: disable=line-too-long


v1 = {
    "ID": "r1",
    "ENTRYTYPE": "article",
    "colrev_masterdata_provenance": {
        "year": {"source": "import.bib/id_0001", "note": ""},
        "title": {"source": "import.bib/id_0001", "note": ""},
        "author": {"source": "import.bib/id_0001", "note": ""},
        "journal": {"source": "import.bib/id_0001", "note": ""},
        "volume": {"source": "import.bib/id_0001", "note": ""},
        "number": {"source": "import.bib/id_0001", "note": ""},
        "pages": {"source": "import.bib/id_0001", "note": ""},
    },
    "colrev_data_provenance": {},
    "colrev_status": colrev.record.RecordState.md_prepared,
    "colrev_origin": ["import.bib/id_0001"],
    "year": "2020",
    "title": "EDITORIAL",
    "author": "Rai, Arun",
    "journal": "MIS Quarterly",
    "volume": "45",
    "number": "1",
    "pages": "1--3",
}
v2 = {
    "ID": "r1",
    "ENTRYTYPE": "article",
    "colrev_masterdata_provenance": {
        "year": {"source": "import.bib/id_0001", "note": ""},
        "title": {"source": "import.bib/id_0001", "note": ""},
        "author": {"source": "import.bib/id_0001", "note": ""},
        "journal": {"source": "import.bib/id_0001", "note": ""},
        "volume": {"source": "import.bib/id_0001", "note": ""},
        "number": {"source": "import.bib/id_0001", "note": ""},
        "pages": {"source": "import.bib/id_0001", "note": ""},
    },
    "colrev_data_provenance": {},
    "colrev_status": colrev.record.RecordState.md_prepared,
    "colrev_origin": ["import.bib/id_0001"],
    "year": "2020",
    "title": "EDITORIAL",
    "author": "Rai, A",
    "journal": "MISQ",
    "volume": "45",
    "number": "1",
    "pages": "1--3",
}

r1 = colrev.record.Record(data=v1)
r2 = colrev.record.Record(data=v2)


def test_eq() -> None:
    """Test equality of records"""
    # pylint: disable=comparison-with-itself
    assert r1 == r1
    assert r1 != r2


def test_copy() -> None:
    """Test record copies"""
    r1_cop = r1.copy()
    assert r1 == r1_cop


def test_update_field() -> None:
    """Test record.update_field()"""
    r2_mod = r2.copy()

    # Test append_edit=True / identifying_field
    r2_mod.update_field(
        key="journal", value="Mis Quarterly", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = r2_mod.data["colrev_masterdata_provenance"]["journal"]["source"]
    assert expected == actual

    # Test append_edit=True / non-identifying_field
    r2_mod.update_field(
        key="non_identifying_field", value="nfi_value", source="import.bib/id_0001"
    )
    r2_mod.update_field(
        key="non_identifying_field", value="changed", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = r2_mod.data["colrev_data_provenance"]["non_identifying_field"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / identifying field
    del r2_mod.data["colrev_masterdata_provenance"]["journal"]
    r2_mod.update_field(
        key="journal",
        value="Mis Quarterly",
        source="test",
        append_edit=True,
        keep_source_if_equal=False,
    )
    expected = "original|test"
    actual = r2_mod.data["colrev_masterdata_provenance"]["journal"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / non-identifying field
    del r2_mod.data["colrev_data_provenance"]["non_identifying_field"]
    r2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    expected = "original|test"
    actual = r2_mod.data["colrev_data_provenance"]["non_identifying_field"]["source"]
    assert expected == actual


def test_rename_field() -> None:
    """Test record.rename_field()"""

    r2_mod = r2.copy()

    # Identifying field
    r2_mod.rename_field(key="journal", new_key="booktitle")
    expected = "import.bib/id_0001|rename-from:journal"
    actual = r2_mod.data["colrev_masterdata_provenance"]["booktitle"]["source"]
    assert expected == actual
    assert "journal" not in r2_mod.data
    assert "journal" not in r2_mod.data["colrev_masterdata_provenance"]

    # Non-identifying field
    r2_mod.update_field(
        key="link", value="https://www.test.org", source="import.bib/id_0001"
    )
    r2_mod.rename_field(key="link", new_key="url")
    expected = "import.bib/id_0001|rename-from:link"
    actual = r2_mod.data["colrev_data_provenance"]["url"]["source"]
    assert expected == actual
    assert "link" not in r2_mod.data
    assert "link" not in r2_mod.data["colrev_data_provenance"]


def test_remove_field() -> None:
    """Test record.remove_field()"""

    r2_mod = r2.copy()
    del r2_mod.data["colrev_masterdata_provenance"]["number"]
    r2_mod.remove_field(key="number", not_missing_note=True, source="test")
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "test", "note": "not-missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, A",
        "journal": "MISQ",
        "volume": "45",
        "pages": "1--3",
    }

    actual = r2_mod.data
    print(actual)
    assert expected == actual


def test_diff() -> None:
    """Test record.diff()"""

    r2_mod = r2.copy()
    r2_mod.remove_field(key="pages")
    # keep_source_if_equal
    r2_mod.update_field(
        key="journal", value="MISQ", source="test", keep_source_if_equal=True
    )

    r2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    r2_mod.update_field(key="booktitle", value="ICIS", source="test")
    r2_mod.update_field(key="publisher", value="Elsevier", source="test")
    print(r1.get_diff(other_record=r2_mod))
    expected = [
        (
            "add",
            "",
            [
                ("booktitle", {"source": "test", "note": ""}),
                ("publisher", {"source": "test", "note": ""}),
            ],
        ),
        ("remove", "", [("pages", {"source": "import.bib/id_0001", "note": ""})]),
        ("change", "author", ("Rai, Arun", "Rai, A")),
        ("change", "journal", ("MIS Quarterly", "MISQ")),
        ("add", "", [("booktitle", "ICIS"), ("publisher", "Elsevier")]),
        ("remove", "", [("pages", "1--3")]),
    ]
    actual = r1.get_diff(other_record=r2_mod)
    assert expected == actual

    print(r1.get_diff(other_record=r2_mod, identifying_fields_only=False))
    expected = [
        (
            "add",
            "colrev_masterdata_provenance",
            [
                ("booktitle", {"source": "test", "note": ""}),
                ("publisher", {"source": "test", "note": ""}),
            ],
        ),
        (
            "remove",
            "colrev_masterdata_provenance",
            [("pages", {"source": "import.bib/id_0001", "note": ""})],
        ),
        (
            "add",
            "colrev_data_provenance",
            [("non_identifying_field", {"source": "test", "note": ""})],
        ),
        ("change", "author", ("Rai, Arun", "Rai, A")),
        ("change", "journal", ("MIS Quarterly", "MISQ")),
        (
            "add",
            "",
            [
                ("non_identifying_field", "nfi_value"),
                ("booktitle", "ICIS"),
                ("publisher", "Elsevier"),
            ],
        ),
        ("remove", "", [("pages", "1--3")]),
    ]
    actual = r1.get_diff(other_record=r2_mod, identifying_fields_only=False)
    assert expected == actual


def test_change_entrytype_inproceedings(
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.change_entrytype(new_entrytype="inproceedings")"""

    r1_mod = r1.copy()
    r1_mod.data["volume"] = "UNKNOWN"
    r1_mod.data["number"] = "UNKNOWN"
    r1_mod.data["title"] = "Editorial"
    r1_mod.data["language"] = "eng"
    r1_mod.update_field(
        key="publisher",
        value="Elsevier",
        source="import.bib/id_0001",
        note="inconsistent-with-entrytype",
    )
    r1_mod.change_entrytype(new_entrytype="inproceedings", qm=quality_model)
    print(r1_mod.data)
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "inproceedings",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "publisher": {"source": "import.bib/id_0001", "note": ""},
            "booktitle": {
                "source": "import.bib/id_0001|rename-from:journal",
                "note": "",
            },
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "booktitle": "MIS Quarterly",
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "pages": "1--3",
        "publisher": "Elsevier",
        "language": "eng",
    }
    actual = r1_mod.data
    assert expected == actual

    with pytest.raises(
        colrev.exceptions.MissingRecordQualityRuleSpecification,
    ):
        r1_mod.change_entrytype(new_entrytype="dialoge", qm=quality_model)


def test_change_entrytype_article(
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.change_entrytype(new_entrytype="article")"""
    input_value = {
        "ID": "r1",
        "ENTRYTYPE": "inproceedings",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "publisher": {"source": "import.bib/id_0001", "note": ""},
            "booktitle": {
                "source": "import.bib/id_0001",
                "note": "",
            },
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "booktitle": "MIS Quarterly",
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "pages": "1--3",
        "publisher": "Elsevier",
        "language": "eng",
    }
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "publisher": {"source": "import.bib/id_0001", "note": ""},
            "journal": {
                "source": "import.bib/id_0001|rename-from:booktitle",
                "note": "",
            },
            "volume": {"source": "generic_field_requirements", "note": "missing"},
            "number": {"source": "generic_field_requirements", "note": "missing"},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_needs_manual_preparation,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "pages": "1--3",
        "publisher": "Elsevier",
        "journal": "MIS Quarterly",
        "volume": "UNKNOWN",
        "number": "UNKNOWN",
        "language": "eng",
    }
    rec = colrev.record.Record(data=input_value)
    rec.change_entrytype(new_entrytype="article", qm=quality_model)
    actual = rec.data
    assert expected == actual


def test_add_provenance_all() -> None:
    """Test record.add_provenance_all()"""

    r1_mod = r1.copy()
    del r1_mod.data["colrev_masterdata_provenance"]
    r1_mod.add_provenance_all(source="import.bib/id_0001")
    print(r1_mod.data)
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {
            "ID": {"source": "import.bib/id_0001", "note": ""},
            "colrev_origin": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
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


def test_shares_origins() -> None:
    """Test record.shares_origins()"""
    assert r1.shares_origins(other_record=r2)


def test_get_value() -> None:
    """Test record.get_value()"""
    expected = "Rai, Arun"
    actual = r1.get_value(key="author")
    assert expected == actual

    expected = "Rai, Arun"
    actual = r1.get_value(key="author", default="custom_file")
    assert expected == actual

    expected = "custom_file"
    actual = r1.get_value(key="file", default="custom_file")
    assert expected == actual


def test_create_colrev_id() -> None:
    """Test record.create_colrev_id()"""

    # Test type: phdthesis
    r1_mod = r1.copy()
    r1_mod.data["ENTRYTYPE"] = "phdthesis"
    r1_mod.data["school"] = "University of Minnesota"
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = ["colrev_id1:|phdthesis|university-of-minnesota|2020|rai|editorial"]
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: techreport
    r1_mod = r1.copy()
    r1_mod.data["ENTRYTYPE"] = "techreport"
    r1_mod.data["institution"] = "University of Minnesota"
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = ["colrev_id1:|techreport|university-of-minnesota|2020|rai|editorial"]
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: inproceedings
    r1_mod = r1.copy()
    r1_mod.data["ENTRYTYPE"] = "inproceedings"
    r1_mod.data["booktitle"] = "International Conference on Information Systems"
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = [
        "colrev_id1:|p|international-conference-on-information-systems|2020|rai|editorial"
    ]
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    r1_mod = r1.copy()
    r1_mod.data["ENTRYTYPE"] = "article"
    r1_mod.data["journal"] = "Journal of Management Information Systems"
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = [
        "colrev_id1:|a|journal-of-management-information-systems|45|1|2020|rai|editorial"
    ]
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    r1_mod = r1.copy()
    r1_mod.data["ENTRYTYPE"] = "monogr"
    r1_mod.data["series"] = "Lecture notes in cs"
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = ["colrev_id1:|monogr|lecture-notes-in-cs|2020|rai|editorial"]
    actual = r1_mod.get_colrev_id()
    assert expected == actual

    # Test type: article
    r1_mod = r1.copy()
    r1_mod.data["ENTRYTYPE"] = "online"
    r1_mod.data["url"] = "www.loc.de/subpage.html"
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = ["colrev_id1:|online|wwwlocde-subpagehtml|2020|rai|editorial"]
    actual = r1_mod.get_colrev_id()
    assert expected == actual


def test_get_colrev_id() -> None:
    """Test record.get_colrev_id()"""

    r1_mod = r1.copy()
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()
    expected = ["colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"]
    actual = r1_mod.get_colrev_id()
    assert expected == actual


def test_has_overlapping_colrev_id() -> None:
    """Test record.has_overlapping_colrev_id()"""

    r1_mod = r1.copy()
    r1_mod.data["colrev_id"] = r1_mod.create_colrev_id()

    r2_mod = r1.copy()
    r2_mod.data["colrev_id"] = r2_mod.create_colrev_id()

    assert r2_mod.has_overlapping_colrev_id(record=r1_mod)

    r2_mod.data["colrev_id"] = []
    assert not r2_mod.has_overlapping_colrev_id(record=r1_mod)


def test_provenance() -> None:
    """Test record provenance"""

    r1_mod = r1.copy()

    r1_mod.add_data_provenance(key="url", source="manual", note="test")
    expected = "manual"
    actual = r1_mod.data["colrev_data_provenance"]["url"]["source"]
    assert expected == actual

    expected = "test"
    actual = r1_mod.data["colrev_data_provenance"]["url"]["note"]
    assert expected == actual

    r1_mod.add_data_provenance_note(key="url", note="1")
    expected = "test,1"
    actual = r1_mod.data["colrev_data_provenance"]["url"]["note"]
    assert expected == actual

    expected = {"source": "manual", "note": "test,1"}  # type: ignore
    actual = r1_mod.get_field_provenance(key="url")
    assert expected == actual

    r1_mod.add_masterdata_provenance(key="author", source="manual", note="test")
    expected = "test"
    actual = r1_mod.data["colrev_masterdata_provenance"]["author"]["note"]
    assert expected == actual

    actual = r1_mod.data["colrev_masterdata_provenance"]["author"]["source"]
    expected = "manual"
    assert expected == actual

    r1_mod.add_masterdata_provenance_note(key="author", note="check")
    expected = "test,check"
    actual = r1_mod.data["colrev_masterdata_provenance"]["author"]["note"]
    assert expected == actual


def test_set_masterdata_complete() -> None:
    """Test record.set_masterdata_complete()"""

    # field=UNKNOWN and no not_missing note
    r1_mod = r1.copy()
    r1_mod.data["number"] = "UNKNOWN"
    r1_mod.data["volume"] = "UNKNOWN"
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "test", "note": "not-missing"},
            "number": {"source": "test", "note": "not-missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
    }
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    actual = r1_mod.data
    print(r1_mod.data)
    assert expected == actual

    # missing fields and no colrev_masterdata_provenance
    r1_mod = r1.copy()
    del r1_mod.data["volume"]
    del r1_mod.data["number"]
    del r1_mod.data["colrev_masterdata_provenance"]["number"]
    del r1_mod.data["colrev_masterdata_provenance"]["volume"]
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "test", "note": "not-missing"},
            "number": {"source": "test", "note": "not-missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
    }
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    actual = r1_mod.data
    print(r1_mod.data)
    assert expected == actual

    # misleading "missing" note
    r1_mod = r1.copy()
    r1_mod.data["colrev_masterdata_provenance"]["volume"]["note"] = "missing"
    r1_mod.data["colrev_masterdata_provenance"]["number"]["note"] = "missing"
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    actual = r1_mod.data
    print(r1_mod.data)
    assert expected == actual

    r1_mod.data["colrev_masterdata_provenance"] = {
        "CURATED": {"source": ":https...", "note": ""}
    }
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)
    del r1_mod.data["colrev_masterdata_provenance"]
    r1_mod.set_masterdata_complete(source="test", masterdata_repository=False)


def test_set_masterdata_consistent() -> None:
    """Test record.set_masterdata_consistent()"""

    r1_mod = r1.copy()
    r1_mod.data["colrev_masterdata_provenance"]["journal"][
        "note"
    ] = "inconsistent-with-entrytype"
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    r1_mod.set_masterdata_consistent()
    actual = r1_mod.data
    print(actual)
    assert expected == actual

    r1_mod = r1.copy()
    del r1_mod.data["colrev_masterdata_provenance"]
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {},
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    r1_mod.set_masterdata_consistent()
    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_reset_pdf_provenance_notes() -> None:
    """Test record.reset_pdf_provenance_notes()"""

    # defects
    r1_mod = r1.copy()
    r1_mod.data["colrev_data_provenance"]["file"] = {
        "source": "test",
        "note": "defects",
    }
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {
            "file": {"source": "test", "note": ""},
        },
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    r1_mod.reset_pdf_provenance_notes()
    actual = r1_mod.data
    assert expected == actual

    # missing provenance
    r1_mod = r1.copy()
    del r1_mod.data["colrev_data_provenance"]
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {"file": {"source": "ORIGINAL", "note": ""}},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    r1_mod.reset_pdf_provenance_notes()
    actual = r1_mod.data
    assert expected == actual

    # file missing in missing provenance
    r1_mod = r1.copy()
    # del r1_mod.data["colrev_data_provenance"]["file"]
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {
            "file": {"source": "NA", "note": ""},
        },
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    r1_mod.reset_pdf_provenance_notes()
    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_cleanup_pdf_processing_fields() -> None:
    """Test record.cleanup_pdf_processing_fields()"""

    r1_mod = r1.copy()
    r1_mod.data["text_from_pdf"] = "This is the full text inserted from the PDF...."
    r1_mod.data["pages_in_file"] = "12"

    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    r1_mod.cleanup_pdf_processing_fields()
    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_get_tei_filename() -> None:
    """Test record.get_tei_filename()"""

    r1_mod = r1.copy()
    r1_mod.data["file"] = "data/pdfs/Rai2020.pdf"
    expected = Path("data/.tei/Rai2020.tei.xml")
    actual = r1_mod.get_tei_filename()
    assert expected == actual


def test_get_record_similarity() -> None:
    """Test record.get_record_similarity()"""

    expected = 0.854
    actual = colrev.record.Record.get_record_similarity(record_a=r1, record_b=r2)
    assert expected == actual


def test_merge_select_non_all_caps() -> None:
    """Test record.merge() - all-caps cases"""
    # Select title-case (not all-caps title) and full author name

    r1_mod = colrev.record.Record(data=v1).copy()
    r2_mod = colrev.record.Record(data=v2).copy()
    print(r1_mod)
    print(r2_mod)
    r1_mod.data["title"] = "Editorial"
    r2_mod.data["colrev_origin"] = ["import.bib/id_0002"]
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001", "import.bib/id_0002"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    r1_mod.merge(merging_record=r2_mod, default_source="test")
    actual = r1_mod.data
    assert expected == actual


def test_merge_except_errata() -> None:
    """Test record.merge() - errata cases"""

    # Mismatching part suffixes
    r1_mod = r1.copy()
    r2_mod = r2.copy()
    r1_mod.data["title"] = "Editorial - Part 1"
    r2_mod.data["title"] = "Editorial - Part 2"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        r2_mod.merge(merging_record=r1_mod, default_source="test")

    # Mismatching erratum (a-b)
    r1_mod = r1.copy()
    r2_mod = r2.copy()
    r2_mod.data["title"] = "Erratum - Editorial"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        r1_mod.merge(merging_record=r2_mod, default_source="test")

    # Mismatching erratum (b-a)
    r1_mod = r1.copy()
    r2_mod = r2.copy()
    r1_mod.data["title"] = "Erratum - Editorial"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        r2_mod.merge(merging_record=r1_mod, default_source="test")

    # Mismatching commentary
    r1_mod = r1.copy()
    r2_mod = r2.copy()
    r1_mod.data["title"] = "Editorial - a commentary to the other paper"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        r2_mod.merge(merging_record=r1_mod, default_source="test")


def test_merge_local_index(mocker) -> None:  # type: ignore
    """Test record.merge() - local-index"""

    mocker.patch(
        "colrev.env.environment_manager.EnvironmentManager.get_name_mail_from_git",
        return_value=("Gerit Wagner", "gerit.wagner@uni-bamberg.de"),
    )

    r1_mod = colrev.record.Record(
        data={
            "ID": "r1",
            "colrev_data_provenance": {},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""}
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": ["orig1"],
            "title": "EDITORIAL",
            "author": "Rai, Arun",
            "journal": "MIS Quarterly",
            "volume": "45",
            "pages": "1--3",
        }
    )
    r2_mod = colrev.record.Record(
        data={
            "ID": "r2",
            "colrev_data_provenance": {},
            "colrev_masterdata_provenance": {
                "volume": {"source": "source-1", "note": ""},
                "number": {"source": "source-1", "note": ""},
            },
            "colrev_status": colrev.record.RecordState.md_prepared,
            "colrev_origin": ["orig2"],
            "title": "Editorial",
            "author": "ARUN RAI",
            "journal": "MISQ",
            "volume": "45",
            "number": "4",
            "pages": "1--3",
        }
    )

    r1_mod.merge(merging_record=r2_mod, default_source="test")
    print(r1_mod)

    # from colrev.env import LocalIndex

    # LOCAL_INDEX = LocalIndex()
    # record = {
    #     "ID": "StandingStandingLove2010",
    #     "ENTRYTYPE": "article",
    #     "colrev_origin": "lr_db.bib/Standing2010",
    #     "colrev_status": RecordState.rev_synthesized,
    #     "colrev_id": "colrev_id1:|a|decision-support-systems|49|1|2010|standing-standing-love|a-review-of-research-on-e-marketplaces-1997-2008;",
    #     "colrev_pdf_id": "cpid2:ffffffffffffffffc3f00fffc2000023c2000023c0000003ffffdfffc0005fffc007ffffffffffffffffffffc1e00003c1e00003cfe00003ffe00003ffe00003ffffffffe7ffffffe3dd8003c0008003c0008003c0008003c0008003c0008003c0008003c0008003c0018003ffff8003e7ff8003e1ffffffffffffffffffffff",
    #     "exclusion_criteria": "NA",
    #     "file": "/home/gerit/ownCloud/data/journals/DSS/49_1/A-review-of-research-on-e-marketplaces-1997-2008_2010.pdf",
    #     "doi": "10.1016/J.DSS.2009.12.008",
    #     "author": "Standing, Susan and Standing, Craig and Love, Peter E. D",
    #     "journal": "Decision Support Systems",
    #     "title": "A review of research on e-marketplaces 1997–2008",
    #     "year": "2010",
    #     "volume": "49",
    #     "number": "1",
    #     "pages": "41--51",
    #     "literature_review": "yes",
    #     "metadata_source_repository_paths": "/home/gerit/ownCloud/data/AI Research/Literature Reviews/LRDatabase/wip/lrs_target_variable",
    # }

    # LOCAL_INDEX.index_record(record=record)

    # DEDUPE test:

    local_index_instance = colrev.env.local_index.LocalIndex()
    mocker.patch(
        "colrev.env.local_index.LocalIndex.is_duplicate", return_value="unknown"
    )

    # short cids / empty lists
    assert "unknown" == local_index_instance.is_duplicate(
        record1_colrev_id=[], record2_colrev_id=[]
    )
    assert "unknown" == local_index_instance.is_duplicate(
        record1_colrev_id=["short"], record2_colrev_id=["short"]
    )

    # Same repo and overlapping colrev_ids -> duplicate
    # assert "yes" == local_index_instance.is_duplicate(
    #     record1_colrev_id=[
    #         "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|power-and-information-technology-research-a-metatriangulation-review"
    #     ],
    #     record2_colrev_id=[
    #         "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|review-power-and-information-technology-research-a-metatriangulation-review"
    #     ],
    # )

    mocker.patch("colrev.env.local_index.LocalIndex.is_duplicate", return_value="no")

    # Different curated repos -> no duplicate
    assert "no" == local_index_instance.is_duplicate(
        record1_colrev_id=[
            "colrev_id1:|a|mis-quarterly|26|4|2002|jasperson-carte-saunders-butler-croes-zheng|power-and-information-technology-research-a-metatriangulation-review"
        ],
        record2_colrev_id=[
            "colrev_id1:|a|information-systems-research|15|2|2004|fichman|real-options-and-it-platform-adoption-implications-for-theory-and-practice"
        ],
    )


def test_get_container_title() -> None:
    """Test record.get_container_title()"""

    r1_mod = r1.copy()

    # article
    expected = "MIS Quarterly"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data["ENTRYTYPE"] = "inproceedings"
    r1_mod.data["booktitle"] = "ICIS"
    expected = "ICIS"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data["ENTRYTYPE"] = "book"
    r1_mod.data["title"] = "Momo"
    expected = "Momo"
    actual = r1_mod.get_container_title()
    assert expected == actual

    r1_mod.data["ENTRYTYPE"] = "inbook"
    r1_mod.data["booktitle"] = "Book title a"
    expected = "Book title a"
    actual = r1_mod.get_container_title()
    assert expected == actual


def test_complete_provenance() -> None:
    """Test record.complete_provenance()"""

    r1_mod = r1.copy()
    del r1_mod.data["colrev_masterdata_provenance"]
    del r1_mod.data["colrev_data_provenance"]
    r1_mod.update_field(key="url", value="www.test.eu", source="asdf")

    r1_mod.complete_provenance(source_info="test")
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {"url": {"source": "test", "note": ""}},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.eu",
        "colrev_masterdata_provenance": {
            "year": {"source": "test", "note": ""},
            "title": {"source": "test", "note": ""},
            "author": {"source": "test", "note": ""},
            "journal": {"source": "test", "note": ""},
            "volume": {"source": "test", "note": ""},
            "number": {"source": "test", "note": ""},
            "pages": {"source": "test", "note": ""},
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
        "ENTRYTYPE": "inproceedings",
        "booktitle": "International Conference on Information Systems",
        "year": "2012",
    }
    expected = "international-conference-on-information-systems|2012"
    actual = colrev.record.Record(data=input_value).get_toc_key()
    assert expected == actual

    input_value = {
        "ENTRYTYPE": "phdthesis",
        "ID": "test",
        "title": "Thesis on asteroids",
        "year": "2012",
    }
    with pytest.raises(
        colrev_exceptions.NotTOCIdentifiableException,
        match="ENTRYTYPE .* not toc-identifiable",
    ):
        colrev.record.Record(data=input_value).get_toc_key()


def test_print_diff_pair() -> None:
    """Test record.print_diff_pair()"""

    colrev.record.Record.print_diff_pair(
        record_pair=[r1.data, r2.data], keys=["title", "journal", "booktitle"]
    )


def test_prescreen_exclude() -> None:
    """Test record.prescreen_exclude()"""

    r1_mod = r1.copy()
    r1_mod.data["colrev_status"] = colrev.record.RecordState.rev_synthesized
    r1_mod.data["number"] = "UNKNOWN"
    r1_mod.data["volume"] = "UNKNOWN"

    r1_mod.prescreen_exclude(reason="retracted", print_warning=True)
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.rev_prescreen_excluded,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
        "prescreen_exclusion": "retracted",
    }

    actual = r1_mod.data
    print(actual)
    assert expected == actual


def test_parse_bib() -> None:
    """Test parse_bib"""

    r1_mod = r1.copy()
    r1_mod.data["colrev_origin"] = "import.bib/id_0001;md_crossref.bib/01;"
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": "year:import.bib/id_0001;;\n                                    title:import.bib/id_0001;;\n                                    author:import.bib/id_0001;;\n                                    journal:import.bib/id_0001;;\n                                    volume:import.bib/id_0001;;\n                                    number:import.bib/id_0001;;\n                                    pages:import.bib/id_0001;;",
        "colrev_data_provenance": "",
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "import.bib/id_0001;\n                                    md_crossref.bib/01;",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }
    print(type(r1_mod.data["colrev_origin"]))
    actual = r1_mod.get_data(stringify=True)
    assert expected == actual


def test_print_prescreen_record(capfd) -> None:  # type: ignore
    """Test record.print_prescreen_record()"""

    r1_mod = r1.copy()
    expected = "  ID: r1 (article)\n  \x1b[92mEDITORIAL\x1b[0m\n  Rai, Arun\n  MIS Quarterly (2020) 45(1)\n"

    r1_mod.print_prescreen_record()
    actual, _ = capfd.readouterr()
    assert expected == actual


def test_print_pdf_prep_man(capfd) -> None:  # type: ignore
    """Test record.print_pdf_prep_man()"""
    r2_mod = r2.copy()

    r2_mod.data["abstract"] = "This paper focuses on ..."
    r2_mod.data["url"] = "www.gs.eu"
    r2_mod.data["colrev_data_provenance"]["file"] = {
        "note": "nr_pages_not_matching,title_not_in_first_pages,author_not_in_first_pages"
    }

    expected = """\x1b[91mRai, A\x1b[0m\n\x1b[91mEDITORIAL\x1b[0m\nMISQ (2020) 45(1), \x1b[91mpp.1--3\x1b[0m\n\nAbstract: This paper focuses on ...\n\n\nurl: www.gs.eu\n\n"""

    r2_mod.print_pdf_prep_man()
    actual, _ = capfd.readouterr()
    assert expected == actual


@pytest.mark.parametrize(
    "input_string, expected",
    [
        ("Tom Smith", "Smith, Tom"),
        (
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
        ),
    ],
)
def test_format_author_field(input_string: str, expected: str) -> None:
    """Test record.format_author_field()"""

    actual = colrev.record.PrepRecord.format_author_field(input_string=input_string)
    assert expected == actual


def test_extract_text_by_page(  # type: ignore
    helpers, record_with_pdf: colrev.record.Record
) -> None:
    """Test record.extract_text_by_page()"""
    expected = (
        helpers.test_data_path / Path("WagnerLukyanenkoParEtAl2022_content.txt")
    ).read_text(encoding="utf-8")
    actual = record_with_pdf.extract_text_by_page(
        pages=[0], project_path=helpers.test_data_path
    )
    actual = actual.rstrip()
    assert expected == actual


def test_set_pages_in_pdf(helpers, record_with_pdf: colrev.record.Record) -> None:  # type: ignore
    """Test record.set_pages_in_pdf()"""

    expected = 18
    record_with_pdf.set_pages_in_pdf(project_path=helpers.test_data_path)
    actual = record_with_pdf.data["pages_in_file"]
    assert expected == actual


def test_set_text_from_pdf(helpers, record_with_pdf: colrev.record.Record) -> None:  # type: ignore
    """Test record.set_text_from_pdf()"""

    expected = (
        (helpers.test_data_path / Path("WagnerLukyanenkoParEtAl2022_content.txt"))
        .read_text(encoding="utf-8")
        .replace("\n", " ")
    )
    record_with_pdf.set_text_from_pdf(project_path=helpers.test_data_path)
    actual = record_with_pdf.data["text_from_pdf"]
    actual = actual[0:4234]
    assert expected == actual


def test_get_retrieval_similarity() -> None:
    """Test record.get_retrieval_similarity()"""

    expected = 0.934
    actual = colrev.record.PrepRecord.get_retrieval_similarity(
        record_original=r1, retrieved_record_original=r2
    )
    assert expected == actual


@pytest.mark.parametrize(
    "input_text, expected, case",
    [
        (
            "TECHNOLOGICAL ENTITLEMENT: IT'S MY TECHNOLOGY AND I'LL (AB)USE IT HOW I WANT TO",
            "Technological entitlement: it's my technology and I'll (ab)use it how I want to",
            "sentence",
        ),
        (
            "A STUDY OF B2B IN M&A SETTINGS",
            "A study of B2B in M&A settings",
            "sentence",
        ),
        (
            "What makes one intrinsically interested in it? an exploratory study on influences of autistic tendency and gender in the u.s. and india",
            "What makes one intrinsically interested in it? an exploratory study on influences of autistic tendency and gender in the u.s. and india",
            "sentence",
        ),
        (
            "ORGANIZATIONS LIKE ieee, ACM OPERATE B2B and c2C BUSINESSES",
            "Organizations like IEEE, ACM operate B2B and C2C businesses",
            "sentence",
        ),
    ],
)
def test_format_if_mostly_upper(input_text: str, expected: str, case: str) -> None:
    """Test record.format_if_mostly_upper()"""

    input_dict = {"title": input_text}
    input_record = colrev.record.PrepRecord(data=input_dict)
    input_record.format_if_mostly_upper(key="title", case=case)
    actual = input_record.data["title"]
    assert expected == actual


def test_rename_fields_based_on_mapping() -> None:
    """Test record.rename_fields_based_on_mapping()"""

    prep_rec = r1.copy_prep_rec()

    prep_rec.rename_fields_based_on_mapping(mapping={"Number": "issue"})
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "issue": {"source": "import.bib/id_0001|rename-from:number", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "pages": "1--3",
        "issue": "1",
    }

    actual = prep_rec.data
    assert expected == actual


def test_unify_pages_field() -> None:
    """Test record.unify_pages_field()"""

    prep_rec = r1.copy_prep_rec()
    prep_rec.data["pages"] = "1-2"
    prep_rec.unify_pages_field()
    expected = "1--2"
    actual = prep_rec.data["pages"]
    assert expected == actual

    del prep_rec.data["pages"]
    prep_rec.unify_pages_field()

    prep_rec.data["pages"] = ["1", "2"]
    prep_rec.unify_pages_field()


def test_preparation_save_condition() -> None:
    """Test record.preparation_save_condition()"""

    prep_rec = r1.copy_prep_rec()
    prep_rec.data["colrev_status"] = colrev.record.RecordState.md_imported
    prep_rec.data["colrev_masterdata_provenance"]["title"][
        "note"
    ] = "disagreement with test"
    expected = True
    actual = prep_rec.preparation_save_condition()
    assert expected == actual

    prep_rec.data["colrev_masterdata_provenance"]["title"]["note"] = "record_not_in_toc"
    expected = True
    actual = prep_rec.preparation_save_condition()
    assert expected == actual


def test_preparation_break_condition() -> None:
    """Test record.preparation_break_condition()"""

    prep_rec = r1.copy_prep_rec()
    prep_rec.data["colrev_masterdata_provenance"]["title"][
        "note"
    ] = "disagreement with website"
    expected = True
    actual = prep_rec.preparation_break_condition()
    assert expected == actual

    prep_rec = r1.copy_prep_rec()
    prep_rec.data["colrev_status"] = colrev.record.RecordState.rev_prescreen_excluded
    expected = True
    actual = prep_rec.preparation_break_condition()
    assert expected == actual


def test_update_metadata_status(
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.update_metadata_status()"""

    # Retracted (crossmark)
    r1_mod = r1.copy_prep_rec()
    r1_mod.data["crossmark"] = "True"
    r1_mod.data["language"] = "eng"
    r1_mod.update_metadata_status()
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.rev_prescreen_excluded,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "prescreen_exclusion": "retracted",
        "language": "eng",
    }
    actual = r1_mod.data
    assert expected == actual

    # Curated
    r1_mod = r1.copy_prep_rec()
    r1_mod.data["colrev_masterdata_provenance"] = {
        "CURATED": {"source": "http...", "note": ""}
    }
    r1_mod.data["title"] = "Editorial"
    r1_mod.data["language"] = "eng"
    r1_mod.update_metadata_status()
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "CURATED": {"source": "http...", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "language": "eng",
    }
    actual = r1_mod.data
    assert expected == actual

    # Quality defect
    r1_mod = r1.copy_prep_rec()
    r1_mod.data["author"] = "Rai, Arun, ARUN"
    r1_mod.data["language"] = "eng"
    r1_mod.update_masterdata_provenance(qm=quality_model)
    r1_mod.update_metadata_status()
    expected = {
        "ID": "r1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": "mostly-all-caps"},
            "author": {
                "source": "import.bib/id_0001",
                "note": "name-format-separators",
            },
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_needs_manual_preparation,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun, ARUN",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "language": "eng",
    }
    actual = r1_mod.data
    assert expected == actual
