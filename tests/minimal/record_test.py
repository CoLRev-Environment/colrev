#!/usr/bin/env python
import pytest

import colrev.exceptions as colrev_exceptions
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
    assert R1 != R2


def test_copy() -> None:
    R1_cop = R1.copy()
    assert R1 == R1_cop


def test_update_field() -> None:
    R2_mod = R2.copy()

    # Test append_edit=True / identifying_field
    R2_mod.update_field(
        key="journal", value="Mis Quarterly", source="test", append_edit=True
    )
    expected = "import.bib/id_0001|test"
    actual = R2_mod.data["colrev_masterdata_provenance"]["journal"]["source"]
    assert expected == actual

    # Test append_edit=True / non-identifying_field
    R2_mod.update_field(
        key="non_identifying_field", value="nfi_value", source="import.bib/id_0001"
    )
    R2_mod.update_field(
        key="non_identifying_field", value="changed", source="test", append_edit=True
    )
    expectd = "import.bib/id_0001|test"
    actual = R2_mod.data["colrev_data_provenance"]["non_identifying_field"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / identifying field
    del R2_mod.data["colrev_masterdata_provenance"]["journal"]
    R2_mod.update_field(
        key="journal", value="Mis Quarterly", source="test", append_edit=True
    )
    expected = "original|test"
    actual = R2_mod.data["colrev_masterdata_provenance"]["journal"]["source"]
    assert expected == actual

    # Test append_edit=True (without key in *provenance) / non-identifying field
    del R2_mod.data["colrev_data_provenance"]["non_identifying_field"]
    R2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    expected = "original|test"
    actual = R2_mod.data["colrev_data_provenance"]["non_identifying_field"]["source"]
    assert expected == actual


def test_rename_field() -> None:
    R2_mod = R2.copy()

    # Identifying field
    R2_mod.rename_field(key="journal", new_key="booktitle")
    expected = "import.bib/id_0001|rename-from:journal"
    actual = R2_mod.data["colrev_masterdata_provenance"]["booktitle"]["source"]
    assert expected == actual
    assert "journal" not in R2_mod.data
    assert "journal" not in R2_mod.data["colrev_masterdata_provenance"]

    # Non-identifying field
    R2_mod.update_field(
        key="link", value="https://www.test.org", source="import.bib/id_0001"
    )
    R2_mod.rename_field(key="link", new_key="url")
    expected = "import.bib/id_0001|rename-from:link"
    actual = R2_mod.data["colrev_data_provenance"]["url"]["source"]
    assert expected == actual
    assert "link" not in R2_mod.data
    assert "link" not in R2_mod.data["colrev_data_provenance"]


def test_remove_field() -> None:
    R2_mod = R2.copy()
    R2_mod.remove_field(key="number", not_missing_note=True)
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "import.bib/id_0001", "note": ""},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "import.bib/id_0001", "note": "not_missing"},
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

    actual = R2_mod.data
    assert expected == actual


def test_diff() -> None:
    R2_mod = R2.copy()
    R2_mod.remove_field(key="pages")
    # keep_source_if_equal
    R2_mod.update_field(
        key="journal", value="MISQ", source="test", keep_source_if_equal=True
    )

    R2_mod.update_field(key="non_identifying_field", value="nfi_value", source="test")
    R2_mod.update_field(key="booktitle", value="ICIS", source="test")
    R2_mod.update_field(key="publisher", value="Elsevier", source="test")
    print(R1.get_diff(other_record=R2_mod))
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
    actual = R1.get_diff(other_record=R2_mod)
    assert expected == actual

    print(R1.get_diff(other_record=R2_mod, identifying_fields_only=False))
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
    actual = R1.get_diff(other_record=R2_mod, identifying_fields_only=False)
    assert expected == actual


def test_change_entrytype_inproceedings() -> None:
    R1_mod = R1.copy()
    R1_mod.data["volume"] = "UNKNOWN"
    R1_mod.data["number"] = "UNKNOWN"
    R1_mod.data["title"] = "Editorial"
    R1_mod.update_field(
        key="publisher",
        value="Elsevier",
        source="import.bib/id_0001",
        note="inconsistent with entrytype",
    )
    R1_mod.change_entrytype(new_entrytype="inproceedings")
    print(R1_mod.data)
    expected = {
        "ID": "R1",
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
    }
    actual = R1_mod.data
    assert expected == actual


def test_change_entrytype_article() -> None:
    input = {
        "ID": "R1",
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
    }
    expected = {
        "ID": "R1",
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
    }
    REC = colrev.record.Record(data=input)
    REC.change_entrytype(new_entrytype="article")
    actual = REC.data
    assert expected == actual


def test_add_provenance_all() -> None:
    R1_mod = R1.copy()
    del R1_mod.data["colrev_masterdata_provenance"]
    R1_mod.add_provenance_all(source="import.bib/id_0001")
    print(R1_mod.data)
    expected = {
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
    }
    actual = R1_mod.data
    assert expected == actual


def test_format_bib_style() -> None:
    expected = "Rai, Arun (2020) EDITORIAL. MIS Quarterly, (45) 1"
    actual = R1.format_bib_style()
    assert expected == actual


def test_shares_origins() -> None:
    assert R1.shares_origins(other_record=R2)


def test_set_status() -> None:
    R1_mod = R1.copy()
    R1_mod.data["author"] = "UNKNOWN"
    R1_mod.set_status(target_state=colrev.record.RecordState.md_prepared)
    expected = colrev.record.RecordState.md_needs_manual_preparation
    actual = R1_mod.data["colrev_status"]
    assert expected == actual


def test_get_value() -> None:
    expected = "Rai, Arun"
    actual = R1.get_value(key="author")
    assert expected == actual

    expected = "Rai, Arun"
    actual = R1.get_value(key="author", default="custom_file")
    assert expected == actual

    expected = "custom_file"
    actual = R1.get_value(key="file", default="custom_file")
    assert expected == actual


def test_get_colrev_id() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_id"] = R1_mod.create_colrev_id()
    expected = ["colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"]
    actual = R1_mod.get_colrev_id()
    assert expected == actual


def test_add_colrev_ids() -> None:
    expected = "colrev_id1:|a|mis-quarterly|45|1|2020|rai|editorial"
    actual = R1.create_colrev_id()
    assert expected == actual

    expected = "colrev_id1:|a|misq|45|1|2020|rai|editorial"
    actual = R2.create_colrev_id()
    assert expected == actual


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
    expected = "manual"
    actual = R1.data["colrev_data_provenance"]["url"]["source"]
    assert expected == actual

    expected = "test"
    actual = R1.data["colrev_data_provenance"]["url"]["note"]
    assert expected == actual

    R1.add_data_provenance_note(key="url", note="1")
    expected = "test,1"
    actual = R1.data["colrev_data_provenance"]["url"]["note"]
    assert expected == actual

    expected = {"source": "manual", "note": "test,1"}  # type: ignore
    actual = R1.get_field_provenance(key="url")
    assert expected == actual

    R1.add_masterdata_provenance(key="author", source="manual", note="test")
    expected = "test"
    actual = R1.data["colrev_masterdata_provenance"]["author"]["note"]
    assert expected == actual

    actual = R1.data["colrev_masterdata_provenance"]["author"]["source"]
    expected = "manual"
    assert expected == actual

    R1.add_masterdata_provenance_note(key="author", note="check")
    expected = "test,check"
    actual = R1.data["colrev_masterdata_provenance"]["author"]["note"]
    assert expected == actual


def test_set_masterdata_complete() -> None:
    R1_mod = R1.copy()

    R1_mod.data["number"] = "UNKNOWN"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "manual", "note": "test,check"},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "volume": {"source": "import.bib/id_0001", "note": ""},
            "number": {"source": "test", "note": "not_missing"},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {"url": {"source": "manual", "note": "test,1"}},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "pages": "1--3",
    }
    R1_mod.set_masterdata_complete(source="test")
    actual = R1_mod.data
    print(R1_mod.data)
    assert expected == actual


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
        expected = {"author"}
        actual = set(R1.get_quality_defects())
        assert expected == actual
        assert R1.has_quality_defects()

    v1["author"] = "Rai, Arun"

    title_defects = ["EDITORIAL"]  # all-caps
    for title_defect in title_defects:
        v1["title"] = title_defect
        R1 = colrev.record.Record(data=v1)
        expected = {"title"}
        actual = set(R1.get_quality_defects())
        assert expected == actual
        assert R1.has_quality_defects()


def test_apply_restrictions() -> None:
    input = {"ENTRYTYPE": "phdthesis"}
    R_test = colrev.record.Record(data=input)
    restrictions = {
        "ENTRYTYPE": "article",
        "journal": "MISQ",
        "booktitle": "ICIS",
        "volume": True,
        "number": True,
    }
    R_test.apply_restrictions(restrictions=restrictions)
    expected = {
        "ENTRYTYPE": "article",
        "colrev_status": colrev.record.RecordState.md_needs_manual_preparation,
        "colrev_masterdata_provenance": {
            "author": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "title": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "year": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "volume": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
            "number": {
                "source": "colrev_curation.masterdata_restrictions",
                "note": "missing",
            },
        },
        "journal": "MISQ",
        "booktitle": "ICIS",
    }
    actual = R_test.data
    assert expected == actual


def test_get_container_title() -> None:
    R1_mod = R1.copy()

    # article
    expected = "MIS Quarterly"
    actual = R1_mod.get_container_title()
    assert expected == actual

    R1_mod.data["ENTRYTYPE"] = "inproceedings"
    R1_mod.data["booktitle"] = "ICIS"
    expected = "ICIS"
    actual = R1_mod.get_container_title()
    assert expected == actual

    R1_mod.data["ENTRYTYPE"] = "book"
    R1_mod.data["title"] = "Momo"
    expected = "Momo"
    actual = R1_mod.get_container_title()
    assert expected == actual

    R1_mod.data["ENTRYTYPE"] = "inbook"
    R1_mod.data["booktitle"] = "Book title a"
    expected = "Book title a"
    actual = R1_mod.get_container_title()
    assert expected == actual


def test_complete_provenance() -> None:
    R1_mod = R1.copy()
    del R1_mod.data["colrev_masterdata_provenance"]
    del R1_mod.data["colrev_data_provenance"]
    R1_mod.update_field(key="url", value="www.test.eu", source="asdf")

    R1_mod.complete_provenance(source_info="test")
    expected = {
        "ID": "R1",
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
    actual = R1_mod.data
    assert expected == actual


def test_get_toc_key() -> None:
    expected = "mis-quarterly|45|1"
    actual = R1.get_toc_key()
    assert expected == actual

    input = {
        "ENTRYTYPE": "inproceedings",
        "booktitle": "International Conference on Information Systems",
        "year": "2012",
    }
    expected = "international-conference-on-information-systems|2012"
    actual = colrev.record.Record(data=input).get_toc_key()
    assert expected == actual

    input = {
        "ENTRYTYPE": "phdthesis",
        "ID": "test",
        "title": "Thesis on asteroids",
        "year": "2012",
    }
    with pytest.raises(
        colrev_exceptions.NotTOCIdentifiableException,
        match="ENTRYTYPE .* not toc-identifiable",
    ):
        actual = colrev.record.Record(data=input).get_toc_key()


def test_print_citation_format() -> None:
    R1.print_citation_format()


def test_print_diff_pair() -> None:
    colrev.record.Record.print_diff_pair(
        record_pair=[R1.data, R2.data], keys=["title", "journal", "booktitle"]
    )


def test_prescreen_exclude() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_status"] = colrev.record.RecordState.rev_synthesized
    R1_mod.data["number"] = "UNKNOWN"
    R1_mod.data["volume"] = "UNKNOWN"

    R1_mod.prescreen_exclude(reason="retracted", print_warning=True)
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": {
            "year": {"source": "import.bib/id_0001", "note": ""},
            "title": {"source": "import.bib/id_0001", "note": ""},
            "author": {"source": "manual", "note": "test,check"},
            "journal": {"source": "import.bib/id_0001", "note": ""},
            "pages": {"source": "import.bib/id_0001", "note": ""},
        },
        "colrev_data_provenance": {"url": {"source": "manual", "note": "test,1"}},
        "colrev_status": colrev.record.RecordState.rev_prescreen_excluded,
        "colrev_origin": ["import.bib/id_0001"],
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "pages": "1--3",
        "prescreen_exclusion": "retracted",
    }

    actual = R1_mod.data
    print(actual)
    assert expected == actual


def test_parse_bib() -> None:
    R1_mod = R1.copy()
    R1_mod.data["colrev_origin"] = "import.bib/id_0001;md_crossref.bib/01;"
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": "year:import.bib/id_0001;;\n                                    title:import.bib/id_0001;;\n                                    author:manual;check,test;\n                                    journal:import.bib/id_0001;;\n                                    volume:import.bib/id_0001;;\n                                    number:import.bib/id_0001;;\n                                    pages:import.bib/id_0001;;",
        "colrev_data_provenance": "url:manual;test,1;",
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
    expected = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_masterdata_provenance": "year:import.bib/id_0001;;\n                                    title:import.bib/id_0001;;\n                                    author:manual;check,test;\n                                    journal:import.bib/id_0001;;\n                                    volume:import.bib/id_0001;;\n                                    number:import.bib/id_0001;;\n                                    pages:import.bib/id_0001;;",
        "colrev_data_provenance": "url:manual;test,1;",
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
    print(type(R1_mod.data["colrev_origin"]))
    actual = R1_mod.get_data(stringify=True)
    assert expected == actual
