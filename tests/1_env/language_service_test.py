#!/usr/bin/env python
"""Test the language service"""
import pytest

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

# pylint: disable=line-too-long
# flake8: noqa

VALID = True
INVALID = False

v1 = {
    Fields.ID: "R1",
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

R1 = colrev.record.record.Record(v1)


@pytest.mark.parametrize(
    "text, expected",
    [
        (
            "An Integrated Framework for Understanding Digital Work in Organizations",
            ("eng", 0.9),
        ),
        (
            "Editorial",
            ("eng", 0.9),
        ),
        (
            "Introduction",
            ("eng", 0.9),
        ),
        (
            "“Escaping the rat race”: Justifications in digital nomadism",
            ("eng", 0.45),
        ),
    ],
)
def test_compute_language_confidence_values(
    text: str,
    expected: bool,
    language_service: colrev.env.language_service.LanguageService,
) -> None:
    """Test the compute_language_confidence_values"""
    confidence_values = language_service.compute_language_confidence_values(text=text)

    # test the first/most likely result
    predicted_lang, predicted_conf = confidence_values[0]
    expected_lang, expected_conf = expected  # type: ignore
    # predicted_lang = predicted_lang.name.lower()
    assert expected_lang == predicted_lang  # type: ignore
    assert expected_conf < predicted_conf  # type: ignore


@pytest.mark.parametrize(
    "text, expected_lang",
    [
        (
            "An Integrated Framework for Understanding Digital Work in Organizations",
            "eng",
        ),
        (
            "Editorial",
            "eng",
        ),
        (
            "Introduction",
            "eng",
        ),
        (
            "“Escaping the rat race”: Justifications in digital nomadism",
            "eng",
        ),
        (
            "Maxillary Implant Prosthodontic Treatment Using Digital Laboratory Protocol for a Patient with Epidermolysis Bullosa: A Case History Report",
            "",
        ),
        ("ελληνικά", "ell"),
        (
            "공유경제 참여자의 비즈니스 등록정책에 대한 인식과 심적기재: 온라인 발화에 대한 텍스트마이닝",
            "kor",
        ),
        ("سماوي يدور", "ara"),
        ("שלום", "heb"),
        ("кириллический", "rus"),
        ("平台经济的典型特征、垄断分析与反垄断监管", "chi"),
        ("공유경제 플랫폼 규제접근방법에 대한 연구", "kor"),
    ],
)
def test_compute_language(
    text: str,
    expected_lang: str,
    language_service: colrev.env.language_service.LanguageService,
) -> None:
    """Test the compute_language"""
    predicted_lang = language_service.compute_language(text=text)
    assert expected_lang == predicted_lang


@pytest.mark.parametrize(
    "language_code, expected",
    [
        ("eng", VALID),
        ("en", INVALID),
    ],
)
def test_validate_iso_639_3_language_codes(
    language_code: str,
    expected: bool,
    language_service: colrev.env.language_service.LanguageService,
) -> None:
    """Test the validate_iso_639_3_language_codes"""
    if VALID == expected:
        language_service.validate_iso_639_3_language_codes(
            lang_code_list=[language_code]
        )
    else:
        with pytest.raises(colrev_exceptions.InvalidLanguageCodeException):
            language_service.validate_iso_639_3_language_codes(
                lang_code_list=[language_code]
            )


@pytest.mark.parametrize(
    "language_code, expected",
    [
        ("en", "eng"),
        ("fr", "fra"),
        ("de", "deu"),
        ("ar", "ara"),
        ("ENGLISH", "eng"),
        ("Russian", "rus"),
        ("English", "eng"),
        ("Spanish", "spa"),
        ("Chinese", "zho"),
        ("Portuguese", "por"),
        ("German", "deu"),
        ("Hungarian", "hun"),
        ("French", "fra"),
    ],
)
def test_unify_to_iso_639_3_language_codes(
    language_code: str,
    expected: bool,
    language_service: colrev.env.language_service.LanguageService,
) -> None:
    """Test the unify_to_iso_639_3_language_codes"""
    R1.data[Fields.LANGUAGE] = language_code
    language_service.unify_to_iso_639_3_language_codes(record=R1)
    actual = R1.data[Fields.LANGUAGE]

    assert expected == actual


def test_unify_to_iso_639_3_language_codes_missing(
    language_service: colrev.env.language_service.LanguageService,
) -> None:
    """Test the unify_to_iso_639_3_language_codes"""
    R1.data.pop(Fields.LANGUAGE, None)
    language_service.unify_to_iso_639_3_language_codes(record=R1)
    # No exception should be raised
