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
    "title": "Editorial",
    "author": "Rai, A",
    "journal": "MISQ",
    "volume": "45",
    "number": "1",
    "pages": "1--3",
}

R1 = colrev.record.Record(data=v1)
R2 = colrev.record.Record(data=v2)


def test_merge_select_non_all_caps() -> None:
    # Select title-case (not all-caps title) and full author name
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    expected = {
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
        "title": "Editorial",
        "author": "Rai, Arun",
        "journal": "MIS Quarterly",
        "volume": "45",
        "number": "1",
        "pages": "1--3",
    }

    R1_mod.merge(merging_record=R2_mod, default_source="test")
    actual = R1_mod.data
    assert expected == actual


def test_merge_except_errata() -> None:
    # Mismatching part suffixes
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R1_mod.data["title"] = "Editorial - Part 1"
    R2_mod.data["title"] = "Editorial - Part 2"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R2_mod.merge(merging_record=R1_mod, default_source="test")

    # Mismatching erratum (a-b)
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R2_mod.data["title"] = "Erratum - Editorial"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R1_mod.merge(merging_record=R2_mod, default_source="test")

    # Mismatching erratum (b-a)
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R1_mod.data["title"] = "Erratum - Editorial"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R2_mod.merge(merging_record=R1_mod, default_source="test")

    # Mismatching commentary
    R1_mod = R1.copy()
    R2_mod = R2.copy()
    R1_mod.data["title"] = "Editorial - a commentary to the other paper"
    with pytest.raises(
        colrev.exceptions.InvalidMerge,
    ):
        R2_mod.merge(merging_record=R1_mod, default_source="test")
