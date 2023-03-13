#!/usr/bin/env python
import colrev.record

v1 = {
    "ID": "R1",
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
    "ID": "R1",
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

R1 = colrev.record.Record(data=v1)
R2 = colrev.record.Record(data=v2)


def test_eq() -> None:
    assert R1 == R1


def test_copy() -> None:
    R1_cop = R1.copy()
    assert R1 == R1_cop


def test_diff() -> None:
    R2_mod = R2.copy()
    R2_mod.remove_field(key="pages")
    R2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    print(R1.get_diff(other_record=R2_mod))
    assert [
        ("remove", "", [("pages", {"source": "import.bib/id_0001", "note": ""})]),
        ("change", "author", ("Rai, Arun", "Rai, A")),
        ("change", "journal", ("MIS Quarterly", "MISQ")),
        ("remove", "", [("pages", "1--3")]),
    ] == R1.get_diff(other_record=R2_mod)
    print(R1.get_diff(other_record=R2_mod, identifying_fields_only=False))
    assert [
        (
            "remove",
            "colrev_masterdata_provenance",
            [("pages", {"source": "import.bib/id_0001", "note": ""})],
        ),
        (
            "add",
            "colrev_data_provenance",
            [("non_identifying_field", {"source": "original|test", "note": ""})],
        ),
        ("change", "author", ("Rai, Arun", "Rai, A")),
        ("change", "journal", ("MIS Quarterly", "MISQ")),
        ("add", "", [("non_identifying_field", "nfi_value")]),
        ("remove", "", [("pages", "1--3")]),
    ] == R1.get_diff(other_record=R2_mod, identifying_fields_only=False)


def test_change_entrytype() -> None:
    R1_mod = R1.copy()
    R1_mod.change_entrytype(new_entrytype="inproceedings")
    print(R1_mod.data)
    assert {
        "ID": "R1",
        "ENTRYTYPE": "inproceedings",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
            "booktitle": {
                "source": "import.bib/id_0001|rename-from:journal",
                "note": "",
            },
        },
        "colrev_data_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "booktitle": "MIS Quarterly",
    } == R1_mod.data


def test_add_provenance_all() -> None:
    R1_mod = R1.copy()
    del R1_mod.data["colrev_masterdata_provenance"]
    R1_mod.add_provenance_all(source="import.bib/id_0001")
    print(R1_mod.data)
    assert {
        "ID": "R1",
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
    } == R1_mod.data


def test_format_bib_style() -> None:
    assert "Rai, Arun (2020) EDITORIAL. MIS Quarterly, (45) 1" == R1.format_bib_style()


def test_shares_origins() -> None:
    assert R1.shares_origins(other_record=R2)


def test_set_status() -> None:
    R1_mod = R1.copy()
    R1_mod.data["author"] = "UNKNOWN"
    R1_mod.set_status(target_state=colrev.record.RecordState.md_prepared)
    assert (
        colrev.record.RecordState.md_needs_manual_preparation
        == R1_mod.data["colrev_status"]
    )


def test_get_value() -> None:
    assert "Rai, Arun" == R1.get_value(key="author")
    assert "Rai, Arun" == R1.get_value(key="author", default="custom_file")
    assert "custom_file" == R1.get_value(key="file", default="custom_file")


def test_get_colrev_id() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    assert [
        "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"
    ] == R1_mod.get_colrev_id()


def test_add_colrev_ids() -> None:
    assert (
        "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial" == R1.create_colrev_id()
    )
    assert "colrev_id1:|a|misq|45|1|2020|rai|editorial" == R2.create_colrev_id()


def test_has_overlapping_colrev_id() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()

    R2_mod = R1.copy()
    R2_mod.data["colrev_id"] = R2_mod.create_colrev_id()

    assert R2_mod.has_overlapping_colrev_id(record=R1_mod)

    R2_mod.data["colrev_id"] = []
    assert not R2_mod.has_overlapping_colrev_id(record=R1_mod)


def test_provenance() -> None:
    R1 = colrev.record.Record(data=v1)
    R1.add_data_provenance(key="url", source="manual", note="test")
    assert R1.data["colrev_data_provenance"]["url"]["source"] == "manual"
    assert R1.data["colrev_data_provenance"]["url"]["note"] == "test"

    R1.add_data_provenance_note(key="url", note="1")
    assert R1.data["colrev_data_provenance"]["url"]["note"] == "test,1"

    assert R1.get_field_provenance(key="url") == {"source": "manual", "note": "test,1"}

    R1.add_masterdata_provenance(key="author", source="manual", note="test")
    assert R1.data["colrev_masterdata_provenance"]["author"]["note"] == "test"
    assert R1.data["colrev_masterdata_provenance"]["author"]["source"] == "manual"

    R1.add_masterdata_provenance_note(key="author", note="check")
    assert R1.data["colrev_masterdata_provenance"]["author"]["note"] == "test,check"


def test_defects() -> None:
    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.com",
    }

    author_defects = [
        "RAI",  # all-caps
        "Rai, Arun and B",  # incomplete part
        "Rai, Phd, Arun",  # additional title
        "Rai, Arun; Straub, Detmar",  # incorrect delimiter
        "Mathiassen, Lars and jonsson, katrin and Holmstrom, Jonny",  # author without capital letters
        "University, Villanova and Sipior, Janice",  # University in author field
    ]
    for author_defect in author_defects:
        v1["author"] = author_defect
        R1 = colrev.record.Record(data=v1)
        assert set(R1.get_quality_defects()) == {"author"}
        assert R1.has_quality_defects()
    v1["author"] = "Rai, Arun"

    title_defects = ["EDITORIAL"]  # all-caps
    for title_defect in title_defects:
        v1["title"] = title_defect
        R1 = colrev.record.Record(data=v1)
        assert set(R1.get_quality_defects()) == {"title"}
        assert R1.has_quality_defects()


def test_parse_bib() -> None:
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": "year:import.bib/id_0001;;\n                                    title:import.bib/id_0001;;\n                                    author:manual;check,test;\n                                    journal:import.bib/id_0001;;\n                                    volume:import.bib/id_0001;;\n                                    number:import.bib/id_0001;;\n                                    pages:import.bib/id_0001;;",
        "colrev_data_provenance": "url:manual;test,1;",
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "import.bib/id_0001;",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    result = R1.get_data(stringify=True)
    assert expected == result
    R1_mod = R1.copy()
    R1_mod.data["colrev_origin"] = "import.bib/id_0001;"
    result = R1_mod.get_data(stringify=True)
    print(R1_mod.data["colrev_origin"])
    assert expected == result
