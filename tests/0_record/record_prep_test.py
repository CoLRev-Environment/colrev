#!/usr/bin/env python
"""Tests of the PrepRecord class"""
import pytest

import colrev.exceptions as colrev_exceptions
import colrev.record.record
import colrev.record.record_prep
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

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


@pytest.mark.parametrize(
    "input_string, expected",
    [
        ("Tom Smith", "Smith, Tom"),
        (
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
        ),
        (
            "Garza, JL;Wu, ZH;Singh, M;Cherniack, MG.",
            "Garza, JL and Wu, ZH and Singh, M and Cherniack, MG.",
        ),
        (
            "Joseph Rottman, Erran Carmel, Mary Lacity",
            "Rottman, Joseph and Carmel, Erran and Lacity, Mary",
        ),
    ],
)
def test_format_author_field(input_string: str, expected: str) -> None:
    """Test record.format_author_field()"""

    actual = colrev.record.record_prep.PrepRecord.format_author_field(input_string)
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

    input_dict = {Fields.TITLE: input_text}
    input_record = colrev.record.record_prep.PrepRecord(input_dict)
    input_record.format_if_mostly_upper(Fields.TITLE, case=case)
    actual = input_record.data[Fields.TITLE]
    assert expected == actual


def test_format_if_mostly_upper_case() -> None:

    input_dict = {
        Fields.TITLE: "ORGANIZATIONS LIKE ieee, ACM OPERATE B2B and c2C BUSINESSES"
    }
    record = colrev.record.record_prep.PrepRecord(input_dict)
    with pytest.raises(colrev_exceptions.ParameterError):
        record.format_if_mostly_upper(Fields.TITLE, case="xy")


def test_unify_pages_field() -> None:
    """Test record.unify_pages_field()"""

    prep_rec = r1.copy_prep_rec()
    prep_rec.data[Fields.PAGES] = "1-2"
    prep_rec.unify_pages_field()
    expected = "1--2"
    actual = prep_rec.data[Fields.PAGES]
    assert expected == actual

    del prep_rec.data[Fields.PAGES]
    prep_rec.unify_pages_field()

    prep_rec.data[Fields.PAGES] = ["1", "2"]
    prep_rec.unify_pages_field()
