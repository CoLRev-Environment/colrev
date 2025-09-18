#!/usr/bin/env python
"""Tests for the quality model"""
from __future__ import annotations

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.record.qm.quality_model
import colrev.record.record
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState

# flake8: noqa: E501


def test_container_title_abbreviated(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the ContainerTitleAbbreviatedChecker directly
    from colrev.record.qm.checkers.container_title_abbreviated import (
        ContainerTitleAbbreviatedChecker,
    )

    container_title_abbreviated_checker = ContainerTitleAbbreviatedChecker(
        quality_model
    )

    # Test case 1: Abbreviated container title in the journal field
    v_t_record.data[Fields.JOURNAL] = "JAMA"
    container_title_abbreviated_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        DefectCodes.CONTAINER_TITLE_ABBREVIATED
    ]

    # Test case 2: Abbreviated container title in the booktitle field
    v_t_record.data[Fields.BOOKTITLE] = "Proc."
    container_title_abbreviated_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == [
        DefectCodes.CONTAINER_TITLE_ABBREVIATED
    ]

    # Test case 3: Non-abbreviated container title
    v_t_record.data[Fields.JOURNAL] = "Journal of Medicine"
    v_t_record.data[Fields.BOOKTITLE] = "Proceedings of the Conference"
    container_title_abbreviated_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == []

    # Test case 4: Ignoring container title abbreviated defect in the journal field
    v_t_record.data[Fields.JOURNAL] = "JAMA"
    v_t_record.ignore_defect(
        key=Fields.JOURNAL, defect=DefectCodes.CONTAINER_TITLE_ABBREVIATED
    )
    container_title_abbreviated_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        f"IGNORE:{DefectCodes.CONTAINER_TITLE_ABBREVIATED}"
    ]


def test_doi_not_matching_pattern(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the DOIPatternChecker directly
    from colrev.record.qm.checkers.doi_not_matching_pattern import DOIPatternChecker

    doi_pattern_checker = DOIPatternChecker(quality_model)

    # Test case 1: DOI not matching the pattern
    v_t_record.data[Fields.DOI] = "20.1002/invalid_doi"
    doi_pattern_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == [
        DefectCodes.DOI_NOT_MATCHING_PATTERN
    ]

    # Test case 2: DOI matching the pattern
    v_t_record.data[Fields.DOI] = "10.1002/valid_doi"
    doi_pattern_checker.run(record=v_t_record)
    print(v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == []

    # Test case 3: Ignoring DOI not matching pattern defect
    v_t_record.data[Fields.DOI] = "20.1002/invalid_doi"
    v_t_record.ignore_defect(
        key=Fields.DOI, defect=DefectCodes.DOI_NOT_MATCHING_PATTERN
    )
    doi_pattern_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == [
        f"IGNORE:{DefectCodes.DOI_NOT_MATCHING_PATTERN}"
    ]
    assert not v_t_record.has_quality_defects()


def test_erroneous_symbol_in_field(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the ErroneousSymbolInFieldChecker directly
    from colrev.record.qm.checkers.erroneous_symbol_in_field import (
        ErroneousSymbolInFieldChecker,
    )

    erroneous_symbol_checker = ErroneousSymbolInFieldChecker(quality_model)
    # Test case 1: Erroneous symbols in the title field
    v_t_record.data[Fields.TITLE] = "Title with Erroneous Symbol ™"
    erroneous_symbol_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.ERRONEOUS_SYMBOL_IN_FIELD
    ]
    v_t_record.data[Fields.TITLE] = (
        "Artificial intelligence and the conduct of literature reviews"
    )

    # Test case 2: No erroneous symbols in the author field
    v_t_record.data[Fields.AUTHOR] = "John Doe"
    erroneous_symbol_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []

    # Test case 3: Ignoring erroneous symbol defect in the title field
    v_t_record.data[Fields.TITLE] = "Title with Erroneous Symbol ™"
    v_t_record.ignore_defect(
        key=Fields.TITLE, defect=DefectCodes.ERRONEOUS_SYMBOL_IN_FIELD
    )
    erroneous_symbol_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.ERRONEOUS_SYMBOL_IN_FIELD}"
    ]


def test_erroneous_term_in_field(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the ErroneousTermInFieldChecker directly
    from colrev.record.qm.checkers.erroneous_term_in_field import (
        ErroneousTermInFieldChecker,
    )

    erroneous_term_checker = ErroneousTermInFieldChecker(quality_model)

    # Test case 1: Erroneous terms in the author field
    print(v_t_record.data[Fields.AUTHOR])
    v_t_record.data[Fields.AUTHOR] = "John Doe from Harvard University"
    erroneous_term_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.ERRONEOUS_TERM_IN_FIELD
    ]
    v_t_record.data[Fields.AUTHOR] = "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy"

    # Test case 2: No erroneous terms in the title field
    v_t_record.data[Fields.TITLE] = "A Study on Artificial Intelligence"
    erroneous_term_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case 3: Ignoring erroneous term defect in the author field
    v_t_record.data[Fields.AUTHOR] = "John Doe from Harvard University"
    v_t_record.ignore_defect(
        key=Fields.AUTHOR, defect=DefectCodes.ERRONEOUS_TERM_IN_FIELD
    )
    erroneous_term_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.ERRONEOUS_TERM_IN_FIELD}"
    ]


def test_erroneous_title_field(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the ErroneousTitleFieldChecker directly
    from colrev.record.qm.checkers.erroneous_title_field import (
        ErroneousTitleFieldChecker,
    )

    erroneous_title_checker = ErroneousTitleFieldChecker(quality_model)

    # Test case 1: Erroneous title with symbols and digits
    v_t_record.data[Fields.TITLE] = "A I S ssociation for nformation ystems"
    erroneous_title_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.ERRONEOUS_TITLE_FIELD
    ]

    # Test case 2: No erroneous title
    v_t_record.data[Fields.TITLE] = "A Study on Artificial Intelligence"
    erroneous_title_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case 4: Erroneous title with symbols and digits
    v_t_record.data[Fields.TITLE] = "PII: S0963-8687(03)00063-5"
    erroneous_title_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.ERRONEOUS_TITLE_FIELD
    ]

    # Test case 3: Ignoring erroneous title defect
    v_t_record.data[Fields.TITLE] = (
        "The International Journal of Information Systems Applications Chairman of the Editorial Board"
    )
    v_t_record.ignore_defect(key=Fields.TITLE, defect=DefectCodes.ERRONEOUS_TITLE_FIELD)
    erroneous_title_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.ERRONEOUS_TITLE_FIELD}"
    ]


def test_html_tags_(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the HTMLTagChecker directly
    from colrev.record.qm.checkers.html_tags import HTMLTagChecker

    html_tag_checker = HTMLTagChecker(quality_model)

    # TODO : tags like <i>

    # Test case 1: HTML tags present in the title
    v_t_record.data[Fields.TITLE] = "An overview of &#60;HTML&#62; tags"
    html_tag_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.HTML_TAGS
    ]

    # Test case 2: HTML tags present in the journal name
    v_t_record.data[Fields.JOURNAL] = "Journal of &#60;Web&#62; Development"
    html_tag_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        DefectCodes.HTML_TAGS
    ]

    # Test case 3: No HTML tags present
    v_t_record.data[Fields.TITLE] = "An overview of Web Development"
    v_t_record.data[Fields.JOURNAL] = "Journal of Web Development"
    html_tag_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == []

    # Test case 4: Ignoring HTML tags defect
    v_t_record.data[Fields.TITLE] = "An overview of &#60;HTML&#62; tags"
    v_t_record.ignore_defect(key=Fields.TITLE, defect=DefectCodes.HTML_TAGS)
    html_tag_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        "IGNORE:html-tags"
    ]


def test_identical_values_between_title_and_container(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the IdenticalValuesChecker directly
    from colrev.record.qm.checkers.identical_values_between_title_and_container import (
        IdenticalValuesChecker,
    )

    identical_values_checker = IdenticalValuesChecker(quality_model)

    # Test case 1: Identical values in title and journal
    v_t_record.data[Fields.TITLE] = "The Great Adventure"
    v_t_record.data[Fields.JOURNAL] = "The Great Adventure"
    identical_values_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER
    ]

    # Test case 2: Identical values in title and booktitle, ignoring "the " prefix
    v_t_record.data[Fields.TITLE] = "The Great Adventure"
    v_t_record.data[Fields.BOOKTITLE] = "Great Adventure"
    identical_values_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER
    ]

    # Test case 5: Title field is unknown
    v_t_record.data[Fields.TITLE] = FieldValues.UNKNOWN
    identical_values_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects(), "Defects found for an unknown title"
    assert (
        v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []
    ), "Provenance notes found for an unknown title"

    # Test case 3: No identical values
    v_t_record.data[Fields.TITLE] = "The Great Adventure"
    v_t_record.data[Fields.JOURNAL] = "Journal of Great Adventures"
    del v_t_record.data[Fields.BOOKTITLE]
    identical_values_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case 4: Ignoring identical values defect
    v_t_record.data[Fields.TITLE] = "The Great Adventure"
    v_t_record.data[Fields.JOURNAL] = "The Great Adventure"
    v_t_record.ignore_defect(
        key=Fields.TITLE,
        defect=DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER,
    )
    identical_values_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER}"
    ]


def test_incomplete_field(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the IncompleteFieldChecker directly
    from colrev.record.qm.checkers.incomplete_field import IncompleteFieldChecker

    incomplete_field_checker = IncompleteFieldChecker(quality_model)

    # Test case 1: Incomplete field in the title
    v_t_record.data[Fields.TITLE] = "A Study on..."
    incomplete_field_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.INCOMPLETE_FIELD
    ]

    # Test case 2: Incomplete field in the author
    v_t_record.data[Fields.AUTHOR] = "Doe, J. and Smith, S. and ..."
    incomplete_field_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.INCOMPLETE_FIELD
    ]

    # Test case 5: Institutional author
    v_t_record.data[Fields.AUTHOR] = "{Microsoft}"
    incomplete_field_checker.run(record=v_t_record)
    assert (
        v_t_record.has_quality_defects()
    ), "Institutional author considered incomplete"
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []

    # Test case 3: No incomplete fields
    v_t_record.data[Fields.TITLE] = "A Complete Study"
    v_t_record.data[Fields.AUTHOR] = "Doe, John and Smith, Jane"
    incomplete_field_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []

    # Test case 4: Ignoring incomplete field defect in the title
    v_t_record.data[Fields.TITLE] = "A Study on..."
    v_t_record.ignore_defect(key=Fields.TITLE, defect=DefectCodes.INCOMPLETE_FIELD)
    incomplete_field_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.INCOMPLETE_FIELD}"
    ]


def test_inconsistent_content(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the InconsistentContentChecker directly
    from colrev.record.qm.checkers.inconsistent_content import (
        InconsistentContentChecker,
    )

    inconsistent_content_checker = InconsistentContentChecker(quality_model)

    # Test case 1: Inconsistent content in the journal field
    v_t_record.data[Fields.JOURNAL] = "Proceedings of the conference on..."
    inconsistent_content_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        DefectCodes.INCONSISTENT_CONTENT
    ]

    # Test case 2: Inconsistent content in the booktitle field
    v_t_record.data[Fields.BOOKTITLE] = "Journal of Advanced Research"
    inconsistent_content_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == [
        DefectCodes.INCONSISTENT_CONTENT
    ]

    # Test case 3: No inconsistent content
    v_t_record.data[Fields.JOURNAL] = "Journal of Advanced Research"
    v_t_record.data[Fields.BOOKTITLE] = "Proceedings of the Advanced Research Symposium"
    inconsistent_content_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == []

    # Test case 4: Ignoring inconsistent content defect in the journal field
    v_t_record.data[Fields.JOURNAL] = "Proceedings of the conference on..."
    v_t_record.ignore_defect(
        key=Fields.JOURNAL, defect=DefectCodes.INCONSISTENT_CONTENT
    )
    inconsistent_content_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        f"IGNORE:{DefectCodes.INCONSISTENT_CONTENT}"
    ]


def test_inconsistent_with_entrytype(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the InconsistentWithEntrytypeChecker directly
    from colrev.record.qm.checkers.inconsistent_with_entrytype import (
        InconsistentWithEntrytypeChecker,
    )

    inconsistent_with_entrytype_checker = InconsistentWithEntrytypeChecker(
        quality_model
    )

    # Test case 1: Inconsistent fields for entrytype 'article'
    v_t_record.data["ENTRYTYPE"] = "article"
    v_t_record.data[Fields.BOOKTITLE] = "Proceedings of the conference on..."
    v_t_record.data[Fields.ISBN] = "123-4567890123"
    inconsistent_with_entrytype_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == [
        DefectCodes.INCONSISTENT_WITH_ENTRYTYPE
    ]
    assert v_t_record.get_field_provenance_notes(key=Fields.ISBN) == [
        DefectCodes.INCONSISTENT_WITH_ENTRYTYPE
    ]

    # Test case 2: No inconsistent fields for entrytype 'inproceedings'
    v_t_record.data["ENTRYTYPE"] = "inproceedings"
    del v_t_record.data[Fields.JOURNAL]
    del v_t_record.data[Fields.NUMBER]
    inconsistent_with_entrytype_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.NUMBER) == []

    # Test case 3: Ignoring inconsistent with entrytype defect in the booktitle field
    v_t_record.data["ENTRYTYPE"] = "article"
    v_t_record.data[Fields.BOOKTITLE] = "Journal of Advanced Research"
    v_t_record.remove_field(key=Fields.ISBN)
    v_t_record.ignore_defect(
        key=Fields.BOOKTITLE, defect=DefectCodes.INCONSISTENT_WITH_ENTRYTYPE
    )
    inconsistent_with_entrytype_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == [
        f"IGNORE:{DefectCodes.INCONSISTENT_WITH_ENTRYTYPE}"
    ]
    print(v_t_record)
    assert not v_t_record.has_quality_defects()


def test_isbn_not_matching_pattern(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the ISBNPatternChecker directly
    from colrev.record.qm.checkers.isbn_not_matching_pattern import ISBNPatternChecker

    isbn_pattern_checker = ISBNPatternChecker(quality_model)

    # Test case 1: ISBN not matching pattern
    v_t_record.data[Fields.ISBN] = "ISBN 123-456-789"
    isbn_pattern_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.ISBN) == [
        DefectCodes.ISBN_NOT_MATCHING_PATTERN
    ]

    # Test case 2: ISBN matching pattern
    v_t_record.data[Fields.ISBN] = "978-3-16-148410-0"
    isbn_pattern_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.ISBN) == []

    # Test case 3: Ignoring ISBN not matching pattern defect
    v_t_record.data[Fields.ISBN] = "ISBN 123-456-789"
    v_t_record.ignore_defect(
        key=Fields.ISBN, defect=DefectCodes.ISBN_NOT_MATCHING_PATTERN
    )
    isbn_pattern_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.ISBN) == [
        f"IGNORE:{DefectCodes.ISBN_NOT_MATCHING_PATTERN}"
    ]


def test_language_format_error(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the LanguageFormatChecker directly
    from colrev.record.qm.checkers.language_format_error import LanguageFormatChecker

    language_format_checker = LanguageFormatChecker(quality_model)

    # Test case 1: Language format error
    v_t_record.data[Fields.LANGUAGE] = "engg"
    language_format_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(Fields.LANGUAGE) == [
        DefectCodes.LANGUAGE_FORMAT_ERROR
    ]

    # Test case 2: Language format correct
    v_t_record.data[Fields.LANGUAGE] = "eng"
    language_format_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(Fields.LANGUAGE) == []

    # Test case 3: Ignoring language format error defect
    v_t_record.data[Fields.LANGUAGE] = "engg"
    v_t_record.ignore_defect(
        key=Fields.LANGUAGE, defect=DefectCodes.LANGUAGE_FORMAT_ERROR
    )
    print(v_t_record)
    language_format_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(Fields.LANGUAGE) == [
        f"IGNORE:{DefectCodes.LANGUAGE_FORMAT_ERROR}"
    ]


def test_language_unknown(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the LanguageUnknownChecker directly
    from colrev.record.qm.checkers.language_unknown import LanguageChecker

    language_unknown_checker = LanguageChecker(quality_model)

    # Test case 1: Language unknown
    del v_t_record.data[Fields.LANGUAGE]
    language_unknown_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.LANGUAGE_UNKNOWN
    ]

    # Test case 2: Language known
    v_t_record.data[Fields.LANGUAGE] = "eng"
    language_unknown_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case 3: Ignoring language unknown defect
    del v_t_record.data[Fields.LANGUAGE]
    v_t_record.ignore_defect(key=Fields.TITLE, defect=DefectCodes.LANGUAGE_UNKNOWN)
    language_unknown_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.LANGUAGE_UNKNOWN}"
    ]


def test_missing_field(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the MissingFieldChecker directly
    from colrev.record.qm.checkers.missing_field import MissingFieldChecker

    missing_field_checker = MissingFieldChecker(quality_model)

    # Test case 1: Field is missing
    del v_t_record.data[Fields.TITLE]
    missing_field_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.MISSING
    ]

    # Test case 2: Field is not missing
    v_t_record.data[Fields.TITLE] = "A Valid Title"
    missing_field_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case: Non-existing entry type
    v_t_record.data["ENTRYTYPE"] = "nonexistent"
    missing_field_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    # Test case 3: Ignoring missing field defect
    v_t_record.data["ENTRYTYPE"] = "article"
    title = v_t_record.data.pop(Fields.TITLE)
    v_t_record.ignore_defect(key=Fields.TITLE, defect=DefectCodes.MISSING)
    missing_field_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.MISSING}"
    ]
    v_t_record.data[Fields.TITLE] = title
    author = v_t_record.data.pop(Fields.AUTHOR)
    v_t_record.ignore_defect(key=Fields.AUTHOR, defect=DefectCodes.MISSING)
    missing_field_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.MISSING}"
    ]
    v_t_record.data[Fields.AUTHOR] = author


def test_mostly_all_caps(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the MostlyAllCapsChecker directly
    from colrev.record.qm.checkers.mostly_all_caps import MostlyAllCapsFieldChecker

    mostly_all_caps_checker = MostlyAllCapsFieldChecker(quality_model)

    # Test case 1: Title is mostly all caps
    v_t_record.data[Fields.TITLE] = "THIS IS AN ALL CAPS TITLE"
    mostly_all_caps_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        DefectCodes.MOSTLY_ALL_CAPS
    ]

    # Test case 2: Title is not mostly all caps
    v_t_record.data[Fields.TITLE] = "This is Not an All Caps Title"
    mostly_all_caps_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case: Title is "PLOS ONE" - should be ok
    v_t_record.data[Fields.JOURNAL] = "PLOS ONE"
    mostly_all_caps_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == []

    # Test case: Online source with short title in all caps - should be ok
    v_t_record.data["ENTRYTYPE"] = "online"
    v_t_record.data[Fields.TITLE] = "SHORT"
    mostly_all_caps_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == []

    # Test case 3: Ignoring mostly all caps defect
    v_t_record.data[Fields.TITLE] = "THIS IS AN ALL CAPS TITLE"
    v_t_record.ignore_defect(key=Fields.TITLE, defect=DefectCodes.MOSTLY_ALL_CAPS)
    mostly_all_caps_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.TITLE) == [
        f"IGNORE:{DefectCodes.MOSTLY_ALL_CAPS}"
    ]


def test_name_abbreviated(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the NameAbbreviatedChecker directly
    from colrev.record.qm.checkers.name_abbreviated import NameAbbreviatedChecker

    name_abbreviated_checker = NameAbbreviatedChecker(quality_model)

    # Test case 1: Name abbreviated in the author field
    v_t_record.data[Fields.AUTHOR] = "John Doe et al"
    name_abbreviated_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_ABBREVIATED
    ]

    # Test case 2: Name abbreviated in the editor field
    v_t_record.data[Fields.EDITOR] = "Jane Smith and others"
    name_abbreviated_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == [
        DefectCodes.NAME_ABBREVIATED
    ]

    # Test case 3: No name abbreviation
    v_t_record.data[Fields.AUTHOR] = "John Doe"
    v_t_record.data[Fields.EDITOR] = "Jane Smith"
    name_abbreviated_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == []

    # Test case 4: Ignoring name abbreviated defect in the author field
    v_t_record.data[Fields.AUTHOR] = "John Doe et al"
    v_t_record.ignore_defect(key=Fields.AUTHOR, defect=DefectCodes.NAME_ABBREVIATED)
    name_abbreviated_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.NAME_ABBREVIATED}"
    ]


def test_name_format_separators(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the NameFormatSeparatorsChecker directly
    from colrev.record.qm.checkers.name_format_separators import (
        NameFormatSeparatorsChecker,
    )

    name_format_separators_checker = NameFormatSeparatorsChecker(quality_model)

    # Test case 1: Name format issues in the author field due to incorrect separators
    v_t_record.data[Fields.AUTHOR] = "Doe, John; Smith, Jane"
    name_format_separators_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_FORMAT_SEPARTORS
    ]

    # Test case 2: Name format issues in the editor field due to incorrect separators
    v_t_record.data[Fields.EDITOR] = "Smith, Jane nf Doe, John"
    name_format_separators_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == [
        DefectCodes.NAME_FORMAT_SEPARTORS
    ]

    # Test case 3: No name format issues
    v_t_record.data[Fields.AUTHOR] = "Doe, John and Smith, Jane"
    v_t_record.data[Fields.EDITOR] = "Smith, Jane and Doe, John"
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == []

    v_t_record.data[Fields.AUTHOR] = (
        "Jackson, Corey Brian and Østerlund, Carsten S. and Harandi, Mahboobeh and Kharwar, Dhruv and Crowston, Kevin"
    )
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = (
        "Seidel, Stefan and Recker, Jan and {vom Brocke}, Jan"
    )
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = "Du, Wenyu (Derek) and Pan, Shan L. and Wu, Junjie"
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = (
        'Lee, Jeongsik "Jay" and Park, Hyunwoo and Zaggl, Michael'
    )
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = (
        "Aguirre‐Urreta, Miguel I. and Rönkkö, Mikko and Marakas, George M."
    )
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = "Córdoba, José‐Rodrigo"
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = (
        'Zahedi, Fatemeh "Mariam" and Abbasi, Ahmed and Chen, Yan'
    )
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    # Name format issues due to "I N T R  O D " in the author field
    v_t_record.data[Fields.AUTHOR] = "I N T R O D"
    name_format_separators_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_FORMAT_SEPARTORS
    ]
    assert v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = "Tom"
    name_format_separators_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_FORMAT_SEPARTORS
    ]
    assert v_t_record.has_quality_defects()

    v_t_record.data[Fields.AUTHOR] = "name, with-no-capitals"
    name_format_separators_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_FORMAT_SEPARTORS
    ]
    assert v_t_record.has_quality_defects()

    # Test case 4: Ignoring name format defect in the author field
    v_t_record.data[Fields.AUTHOR] = "Doe, John; Smith, Jane"
    v_t_record.ignore_defect(
        key=Fields.AUTHOR, defect=DefectCodes.NAME_FORMAT_SEPARTORS
    )
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.NAME_FORMAT_SEPARTORS}"
    ]

    # Test case 5: No name format defect for abbreviated names
    v_t_record.data[Fields.AUTHOR] = "Doe, John and Smith, Jane and others"
    v_t_record.data[Fields.MD_PROV][Fields.AUTHOR]["note"] = ""
    name_format_separators_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []


def test_name_format_titles(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the NameFormatTitleChecker directly
    from colrev.record.qm.checkers.name_format_titles import NameFormatTitleChecker

    name_format_title_checker = NameFormatTitleChecker(quality_model)

    # Test case 1: Name format issues in the author field due to titles
    v_t_record.data[Fields.AUTHOR] = "Dr. John Doe"
    name_format_title_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_FORMAT_TITLES
    ]

    # Test case 2: Name format issues in the editor field due to titles
    v_t_record.data[Fields.EDITOR] = "Prof. Jane Smith"
    name_format_title_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == [
        DefectCodes.NAME_FORMAT_TITLES
    ]

    # Test case 3: No name format issues
    v_t_record.data[Fields.AUTHOR] = "John Doe"
    v_t_record.data[Fields.EDITOR] = "Jane Smith"
    name_format_title_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == []

    # Test case 4: Ignoring name format defect in the author field
    v_t_record.data[Fields.AUTHOR] = "Dr. John Doe"
    v_t_record.ignore_defect(key=Fields.AUTHOR, defect=DefectCodes.NAME_FORMAT_TITLES)
    name_format_title_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.NAME_FORMAT_TITLES}"
    ]


def test_name_particles(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the NameParticlesChecker directly
    from colrev.record.qm.checkers.name_particles import NameParticlesChecker

    name_particles_checker = NameParticlesChecker(quality_model)

    # Test case 1: Name particles issues in the author field
    v_t_record.data[Fields.AUTHOR] = "Neumann, John von"
    name_particles_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.NAME_PARTICLES
    ]

    # Test case 2: Name particles issues in the editor field
    v_t_record.data[Fields.EDITOR] = "Beethoven, Ludwig vom"
    name_particles_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == [
        DefectCodes.NAME_PARTICLES
    ]

    # Test case 3: No name particles issues
    v_t_record.data[Fields.AUTHOR] = "John Doe"
    v_t_record.data[Fields.EDITOR] = "Jane Smith"
    name_particles_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []
    assert v_t_record.get_field_provenance_notes(key=Fields.EDITOR) == []

    # Test case 4: Ignoring name particles defect in the author field
    v_t_record.data[Fields.AUTHOR] = "Neumann, John von"
    v_t_record.ignore_defect(key=Fields.AUTHOR, defect=DefectCodes.NAME_PARTICLES)
    name_particles_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.NAME_PARTICLES}"
    ]


def test_page_range(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the PageRangeChecker directly
    from colrev.record.qm.checkers.page_range import PageRangeChecker

    page_range_checker = PageRangeChecker(quality_model)

    # Test case 1: Page range issues due to descending page numbers
    v_t_record.data[Fields.PAGES] = "123--100"
    page_range_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.PAGES) == [
        DefectCodes.PAGE_RANGE
    ]

    # Test case 2: No page range issues
    v_t_record.data[Fields.PAGES] = "100--123"
    page_range_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.PAGES) == []

    # Test case 3: Ignoring page range defect
    v_t_record.data[Fields.PAGES] = "123--100"
    v_t_record.ignore_defect(key=Fields.PAGES, defect=DefectCodes.PAGE_RANGE)
    page_range_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.PAGES) == [
        f"IGNORE:{DefectCodes.PAGE_RANGE}"
    ]


def test_pubmedid_not_matching_pattern(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the PubmedIDPatternChecker directly
    from colrev.record.qm.checkers.pubmedid_not_matching_pattern import (
        PubmedIDPatternChecker,
    )

    pubmedid_pattern_checker = PubmedIDPatternChecker(quality_model)

    # Test case 1: PubmedID not matching the pattern
    v_t_record.data[Fields.PUBMED_ID] = "123456789A"
    pubmedid_pattern_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.PUBMED_ID) == [
        DefectCodes.PUBMED_ID_NOT_MATCHING_PATTERN
    ]

    # Test case 2: PubmedID matching the pattern
    v_t_record.data[Fields.PUBMED_ID] = "1234567"
    pubmedid_pattern_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.PUBMED_ID) == []

    # Test case 3: Ignoring PubmedID pattern defect
    v_t_record.data[Fields.PUBMED_ID] = "123456789A"
    v_t_record.ignore_defect(
        key=Fields.PUBMED_ID, defect=DefectCodes.PUBMED_ID_NOT_MATCHING_PATTERN
    )
    pubmedid_pattern_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.PUBMED_ID) == [
        f"IGNORE:{DefectCodes.PUBMED_ID_NOT_MATCHING_PATTERN}"
    ]
    # TODO : check whether pubmedid shoudl be in masterdata  provenance!??!
    # assert not v_t_record.has_quality_defects()


def test_thesis_with_multiple_authors(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the ThesisWithMultipleAuthorsChecker directly
    from colrev.record.qm.checkers.thesis_with_multiple_authors import (
        ThesisWithMultipleAuthorsChecker,
    )

    thesis_with_multiple_authors_checker = ThesisWithMultipleAuthorsChecker(
        quality_model
    )

    # Test case 1: Thesis with multiple authors
    v_t_record.data["ENTRYTYPE"] = "phdthesis"
    v_t_record.data[Fields.AUTHOR] = "John Doe and Jane Smith"
    thesis_with_multiple_authors_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        DefectCodes.THESIS_WITH_MULTIPLE_AUTHORS
    ]

    # Test case 2: Thesis with a single author
    v_t_record.data["ENTRYTYPE"] = "mastertsthesis"
    v_t_record.data[Fields.AUTHOR] = "John Doe"
    thesis_with_multiple_authors_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == []

    # Test case 3: Ignoring thesis with multiple authors defect
    v_t_record.data["ENTRYTYPE"] = "thesis"
    v_t_record.data[Fields.AUTHOR] = "John Doe and Jane Smith"
    v_t_record.ignore_defect(
        key=Fields.AUTHOR, defect=DefectCodes.THESIS_WITH_MULTIPLE_AUTHORS
    )
    thesis_with_multiple_authors_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.AUTHOR) == [
        f"IGNORE:{DefectCodes.THESIS_WITH_MULTIPLE_AUTHORS}"
    ]


def test_year_format(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the YearFormatChecker directly
    from colrev.record.qm.checkers.year_format import YearFormatChecker

    year_format_checker = YearFormatChecker(quality_model)

    # Test case 1: Year format is correct
    v_t_record.data[Fields.YEAR] = "2021"
    year_format_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.YEAR) == []

    # Test case 2: Year format is incorrect
    v_t_record.data[Fields.YEAR] = "20twentyone"
    year_format_checker.run(record=v_t_record)
    assert v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.YEAR) == [
        DefectCodes.YEAR_FORMAT
    ]

    # Test case 3: Ignoring year format defect
    v_t_record.data[Fields.YEAR] = "20twentyone"
    v_t_record.ignore_defect(key=Fields.YEAR, defect=DefectCodes.YEAR_FORMAT)
    year_format_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.YEAR) == [
        f"IGNORE:{DefectCodes.YEAR_FORMAT}"
    ]


def test_inconsistent_with_doi_metadata(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    # Setup: Instantiate the DOIConsistencyChecker directly
    from colrev.record.qm.checkers.inconsistent_with_doi_metadata import (
        InconsistentWithDOIMetadataChecker,
    )

    import colrev.packages.crossref.src.crossref_api as crossref_api

    @classmethod  # type: ignore
    def patched_query_doi(cls, *, doi):  # type: ignore
        """
        Patched method to simulate Crossref DOI query responses for testing purposes.
        """
        # Updated simulated response data for testing
        simulated_responses = {
            "10.1177/02683962211048201": {
                "ENTRYTYPE": "article",
                "ID": "WagnerLukyanenkoParEtAl2022",
                "author": "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy",
                "title": "Artificial intelligence and the conduct of literature reviews",
                "journal": "Journal of Information Technology",
                "volume": "37",
                "doi": "10.1177/02683962211048201",
                "year": "2022",
            },
            "RecordNotFoundInPrepSourceException": {},
        }

        if doi == "RecordNotFoundInPrepSourceException":
            raise colrev_exceptions.RecordNotFoundInPrepSourceException(msg="test")

        # Return the simulated response if DOI is in the simulated responses
        if doi in simulated_responses:
            return colrev.record.record.Record(simulated_responses[doi])
        else:
            # Simulate a DOI not found scenario
            return None

    # Patch the CrossrefSearchSource.query_doi method
    original_method = crossref_api.query_doi
    crossref_api.query_doi = patched_query_doi  # type: ignore

    doi_consistency_checker = InconsistentWithDOIMetadataChecker(quality_model)

    # Test case 1: DOI metadata is consistent
    doi_consistency_checker.run(record=v_t_record)
    v_t_record.data[Fields.DOI] = "10.1177/02683962211048201"
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == []

    # Test case 2: DOI metadata is inconsistent
    v_t_record.data[Fields.DOI] = "10.1177/02683962211048201"
    v_t_record.data[Fields.TITLE] = "Inconsistent"
    v_t_record.data[Fields.AUTHOR] = "Inconsistent"
    doi_consistency_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == [
        DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    ]

    # Test case 9: DOI "RecordNotFoundInPrepSourceException" (exception handled in run())
    v_t_record.data[Fields.DOI] = "RecordNotFoundInPrepSourceException"
    doi_consistency_checker.run(record=v_t_record)
    v_t_record.data[Fields.DOI] = "10.1177/02683962211048201"
    v_t_record.data[Fields.JOURNAL] = "Journal of Information Technology"
    v_t_record.data[Fields.TITLE] = (
        "Artificial intelligence and the conduct of literature reviews"
    )
    v_t_record.data[Fields.AUTHOR] = "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy"

    # Test case 11: v_t_record with journal = "JIT" and no defects
    v_t_record.data[Fields.JOURNAL] = "JIT"
    doi_consistency_checker.run(record=v_t_record)
    assert (
        not v_t_record.has_quality_defects()
    ), "Record with journal 'JIT' should not have quality defects"
    v_t_record.data[Fields.JOURNAL] = "Journal of Information Technology"

    # Test case 10: v_t_record without journal and with title = unknown
    v_t_record.data.pop(Fields.JOURNAL, None)
    v_t_record.data[Fields.TITLE] = FieldValues.UNKNOWN
    doi_consistency_checker.run(record=v_t_record)
    assert (
        not v_t_record.has_quality_defects()
    ), "Record should not have quality defects when title is unknown and journal is not provided"

    # Test case 3: Ignoring DOI metadata inconsistency
    v_t_record.data[Fields.TITLE] = "Inconsistent"
    v_t_record.data[Fields.AUTHOR] = "Inconsistent"

    v_t_record.ignore_defect(
        key=Fields.DOI, defect=DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    )
    doi_consistency_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == [
        f"IGNORE:{DefectCodes.INCONSISTENT_WITH_DOI_METADATA}"
    ]

    # Test case 4: DOI not in record data
    v_t_record.data.pop(Fields.DOI, None)
    doi_consistency_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    # Test case 5: DOI ignored defect
    v_t_record.data[Fields.DOI] = "10.1177/02683962211048201"
    v_t_record.ignore_defect(
        key=Fields.DOI, defect=DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    )
    doi_consistency_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    # Test case 6: DOI metadata from 'md_curated.bib' source
    v_t_record.data[Fields.D_PROV] = {
        Fields.DOI: {"source": "md_curated.bib", "note": ""}
    }
    doi_consistency_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    # Test case 7: DOI metadata conflicts
    v_t_record.data[Fields.D_PROV].pop(Fields.DOI, None)
    v_t_record.data[Fields.TITLE] = "Mismatched Title"
    print(v_t_record.data)
    doi_consistency_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.DOI) == [
        DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    ]

    # Test case 8: DOI metadata does not conflict
    v_t_record.data[Fields.MD_PROV].pop(Fields.DOI, None)
    v_t_record.data[Fields.TITLE] = (
        "Artificial intelligence and the conduct of literature reviews"
    )
    v_t_record.data[Fields.AUTHOR] = "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy"
    print(v_t_record)
    doi_consistency_checker.run(record=v_t_record)
    print(v_t_record)
    assert not v_t_record.has_quality_defects()

    crossref_api.CrossrefAPI.query_doi = original_method  # type: ignore


# TODO : fix the following
# TODO: record_not_in_toc


def test_record_not_in_toc(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Test record_not_in_toc"""
    from colrev.record.qm.checkers.record_not_in_toc import RecordNotInTOCChecker

    record_not_in_toc_checker = RecordNotInTOCChecker(quality_model)

    original_retrieve_from_toc = record_not_in_toc_checker.local_index.retrieve_from_toc

    def patched_retrieve_from_toc(  # type: ignore
        record: colrev.record.record.Record,
        *,
        similarity_threshold=0.9,
        include_file=False,
    ):
        """
        Patched method to simulate TOC query responses for testing purposes.
        """
        # Updated simulated TOC data for testing based on exact DOI match
        simulated_toc_entries = {
            "10.1177/02683962211048201": {
                "ENTRYTYPE": "article",
                "JOURNAL": "Journal of Information Technology",
                "author": "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy",
                "title": "Artificial intelligence and the conduct of literature reviews",
                "volume": "37",
                "year": "2022",
            },
        }

        doi = record.data.get(Fields.DOI, "") if record else ""
        if doi == "NOT_IN_TOC":
            raise colrev_exceptions.RecordNotInTOCException(
                record_id="test-id", toc_key="test_toc_key"
            )
        # Return the TOC entry if DOI matches exactly
        if doi in simulated_toc_entries:
            return [simulated_toc_entries[doi]]
        else:
            return []  # Simulate not found in TOC

    # Patch the retrieve_from_toc method
    record_not_in_toc_checker.local_index.retrieve_from_toc = patched_retrieve_from_toc  # type: ignore

    # Test case 1: Record is in TOC
    v_t_record.data[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
    record_not_in_toc_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()

    # Test case 2: Record is not in TOC
    v_t_record.data[Fields.DOI] = "NOT_IN_TOC"
    v_t_record.data.pop(Fields.MD_PROV, None)
    record_not_in_toc_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        DefectCodes.RECORD_NOT_IN_TOC
    ]
    v_t_record.data[Fields.DOI] = "10.1177/02683962211048201"

    # Test case 4: INPROCEEDINGS record not in TOC
    v_t_record.data[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
    v_t_record.data[Fields.DOI] = "NOT_IN_TOC"
    v_t_record.data.pop(Fields.MD_PROV, None)
    record_not_in_toc_checker.run(record=v_t_record)
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == [
        DefectCodes.RECORD_NOT_IN_TOC
    ]

    # Test case 3: Ignoring record not in TOC defect
    v_t_record.data[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
    v_t_record.data[Fields.DOI] = "NOT_IN_TOC"
    v_t_record.data.pop(Fields.MD_PROV, None)
    v_t_record.ignore_defect(key=Fields.JOURNAL, defect=DefectCodes.RECORD_NOT_IN_TOC)
    record_not_in_toc_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.JOURNAL) == [
        f"IGNORE:{DefectCodes.RECORD_NOT_IN_TOC}"
    ]

    # Test case 5: Ignoring record not in TOC defect for INPROCEEDINGS
    v_t_record.data[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
    v_t_record.data[Fields.DOI] = "NOT_IN_TOC"
    v_t_record.data.pop(Fields.MD_PROV, None)
    v_t_record.ignore_defect(key=Fields.BOOKTITLE, defect=DefectCodes.RECORD_NOT_IN_TOC)
    record_not_in_toc_checker.run(record=v_t_record)
    assert not v_t_record.has_quality_defects()
    assert v_t_record.get_field_provenance_notes(key=Fields.BOOKTITLE) == [
        f"IGNORE:{DefectCodes.RECORD_NOT_IN_TOC}"
    ]

    record_not_in_toc_checker.local_index.retrieve_from_toc = original_retrieve_from_toc  # type: ignore


def test_get_quality_defects_incomplete_field(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Test incomplete_field"""
    v_t_record.data[Fields.AUTHOR] = "Author et al"
    v_t_record.data[Fields.MD_PROV] = {Fields.AUTHOR: {}}
    v_t_record.data[Fields.MD_PROV][Fields.AUTHOR][
        "note"
    ] = f"IGNORE:{DefectCodes.INCOMPLETE_FIELD}"
    v_t_record.run_quality_model(quality_model=quality_model)

    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "title_str, defects",
    [
        ("EDITORIAL", [DefectCodes.MOSTLY_ALL_CAPS]),
        ("SAMJ�", [DefectCodes.ERRONEOUS_SYMBOL_IN_FIELD]),
        ("™", [DefectCodes.ERRONEOUS_SYMBOL_IN_FIELD]),
        ("Some_Other_Title", [DefectCodes.ERRONEOUS_TITLE_FIELD]),
        ("Some other title", []),
        ("Some ...", [DefectCodes.INCOMPLETE_FIELD]),
    ],
)
def test_get_quality_defects_title(
    title_str: str,
    defects: list,
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data[Fields.TITLE] = title_str

    v_t_record.run_quality_model(quality_model=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.TITLE]["note"].split(
            ","
        )
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "journal_str, defects",
    [
        ("A U-ARCHIT URBAN", [DefectCodes.MOSTLY_ALL_CAPS]),
        ("SOS", [DefectCodes.CONTAINER_TITLE_ABBREVIATED]),
        ("SAMJ", [DefectCodes.CONTAINER_TITLE_ABBREVIATED]),
        ("SAMJ�", [DefectCodes.ERRONEOUS_SYMBOL_IN_FIELD]),
        ("A Journal, Conference", [DefectCodes.INCONSISTENT_CONTENT]),
    ],
)
def test_get_quality_defects_journal(
    journal_str: str,
    defects: list,
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - journal field"""
    v_t_record.data[Fields.JOURNAL] = journal_str

    v_t_record.run_quality_model(quality_model=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.JOURNAL]["note"].split(
            ","
        )
    assert v_t_record.has_quality_defects()


def test_get_quality_defects_testing_missing_field_year_forthcoming(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Tests for when year = forthcoming"""

    v_t_record.data[Fields.YEAR] = "forthcoming"
    del v_t_record.data[Fields.VOLUME]
    del v_t_record.data[Fields.NUMBER]
    v_t_record.run_quality_model(quality_model=quality_model)
    assert (
        v_t_record.data[Fields.MD_PROV][Fields.VOLUME]["note"]
        == f"IGNORE:{DefectCodes.MISSING}"
    )
    assert (
        v_t_record.data[Fields.MD_PROV][Fields.NUMBER]["note"]
        == f"IGNORE:{DefectCodes.MISSING}"
    )


@pytest.mark.parametrize(
    "booktitle, defects",
    [
        ("JAMS", [DefectCodes.CONTAINER_TITLE_ABBREVIATED]),
        ("Normal book", []),
    ],
)
def test_get_quality_defects_book_title_abbr(
    booktitle: str,
    defects: list,
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Test if booktitle is abbreviated"""

    v_t_record.data[Fields.ENTRYTYPE] = "inbook"
    v_t_record.data[Fields.BOOKTITLE] = booktitle
    v_t_record.data[Fields.CHAPTER] = 10
    v_t_record.data[Fields.PUBLISHER] = "nobody"
    del v_t_record.data[Fields.JOURNAL]
    v_t_record.run_quality_model(quality_model=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.BOOKTITLE][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "entrytype, missing, defects",
    [
        (ENTRYTYPES.ARTICLE, [], []),
        (ENTRYTYPES.INPROCEEDINGS, [Fields.BOOKTITLE], [Fields.NUMBER, Fields.JOURNAL]),
        (ENTRYTYPES.INCOLLECTION, [Fields.BOOKTITLE, Fields.PUBLISHER], []),
        (ENTRYTYPES.INBOOK, [Fields.PUBLISHER, Fields.CHAPTER], [Fields.JOURNAL]),
    ],
)
def test_get_quality_defects_missing_fields(
    entrytype: str,
    missing: list,
    defects: list,
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    """Tests for missing and inconsistent data for ENTRYTYPE"""

    v_t_record.data[Fields.ENTRYTYPE] = entrytype
    v_t_record.run_quality_model(quality_model=quality_model)
    if not missing:
        assert not v_t_record.has_quality_defects()
        return
    for missing_key in missing:
        assert (
            v_t_record.data[Fields.MD_PROV][missing_key]["note"] == DefectCodes.MISSING
        )
    for key in v_t_record.data[Fields.MD_PROV]:
        if key in missing:
            continue
        assert key in defects
        assert (
            v_t_record.data[Fields.MD_PROV][key]["note"]
            == DefectCodes.INCONSISTENT_WITH_ENTRYTYPE
        )
    assert v_t_record.has_quality_defects()


def test_retracted(
    quality_model: colrev.record.qm.quality_model.QualityModel,
    v_t_record: colrev.record.record.Record,
) -> None:
    """Test whether run_quality_model detects retracts"""

    # Retracted (crossmark)
    r1_mod = v_t_record.copy_prep_rec()
    r1_mod.data["crossmark"] = "True"
    r1_mod.data[Fields.LANGUAGE] = "eng"
    r1_mod.run_quality_model(quality_model=quality_model)
    expected = v_t_record.copy_prep_rec()
    expected.data[Fields.PRESCREEN_EXCLUSION] = "retracted"
    expected.data[Fields.RETRACTED] = FieldValues.RETRACTED
    expected.data[Fields.STATUS] = RecordState.rev_prescreen_excluded
    expected.data[Fields.MD_PROV] = {}
    expected.data[Fields.D_PROV] = {}
    # expected = {
    #     "ID": "r1",
    #     "ENTRYTYPE": "article",
    #     Fields.MD_PROV: {
    #         "year": {"source": "import.bib/id_0001", "note": ""},
    #         Fields.TITLE: {"source": "import.bib/id_0001", "note": ""},
    #         "author": {"source": "import.bib/id_0001", "note": ""},
    #         Fields.JOURNAL: {"source": "import.bib/id_0001", "note": ""},
    #         "volume": {"source": "import.bib/id_0001", "note": ""},
    #         "number": {"source": "import.bib/id_0001", "note": ""},
    #         "pages": {"source": "import.bib/id_0001", "note": ""},
    #     },
    #     "colrev_data_provenance": {},
    #     "colrev_status": RecordState.rev_prescreen_excluded,
    #     "colrev_origin": ["import.bib/id_0001"],
    #     "year": "2020",
    #     Fields.TITLE: "EDITORIAL",
    #     "author": "Rai, Arun",
    #     Fields.JOURNAL: "MIS Quarterly",
    #     "volume": "45",
    #     "number": "1",
    #     "pages": "1--3",
    #     "prescreen_exclusion": "retracted",
    #     "language": "eng",
    # }
    actual = r1_mod.data
    assert expected.data == actual


def test_defect_ignore(
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    v_t_record.data["journal"] = "JOURNAL OF INFORMATION TECHNOLOGY"
    v_t_record.run_quality_model(quality_model=quality_model)
    v_t_record.ignore_defect(key="journal", defect=DefectCodes.MOSTLY_ALL_CAPS)
    v_t_record.run_quality_model(quality_model=quality_model, set_prepared=True)
    assert v_t_record.data[Fields.STATUS] == RecordState.md_prepared
    assert not v_t_record.has_quality_defects()


def test_run_quality_model_curated(  # type: ignore
    mocker,
    v_t_record: colrev.record.record.Record,
    quality_model: colrev.record.qm.quality_model.QualityModel,
) -> None:
    mocker.patch(
        "colrev.record.record.Record.masterdata_is_curated",
        return_value=True,
    )
    v_t_record.run_quality_model(quality_model=quality_model, set_prepared=True)

    assert v_t_record.data[Fields.STATUS] == RecordState.md_prepared
