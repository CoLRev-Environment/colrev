#!/usr/bin/env python
import colrev.review_manager


def test_add_colrev_ids() -> None:
    import colrev.record

    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
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
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, A",
        "journal": "MISQ",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }


def test_provenance() -> None:
    import colrev.record

    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
        "year": "2020",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
        "url": "www.test.com",
    }
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
    import colrev.record

    v1 = {
        "ID": "R1",
        "ENTRYTYPE": "article",
        "colrev_data_provenance": {},
        "colrev_masterdata_provenance": {},
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1",
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
    import colrev.record

    R1 = colrev.record.Record(
        data={
            "ID": "R1",
            "colrev_data_provenance": {"url": {"source": "manual", "note": "testing"}},
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
            "url": "www.test.com",
        }
    )
    expected = {
        "ID": "R1",
        "colrev_data_provenance": "url:manual;testing;",
        "colrev_masterdata_provenance": "volume:source-1;;",
        "colrev_status": colrev.record.RecordState.md_prepared,
        "colrev_origin": "orig1;",
        "title": "EDITORIAL",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "pages": "1--3",
        "url": "www.test.com",
    }

    result = R1.get_data(stringify=True)
    assert expected == result
