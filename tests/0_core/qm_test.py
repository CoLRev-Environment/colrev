#!/usr/bin/env python
"""Tests for the quality model"""
from __future__ import annotations

import pytest

import colrev.qm.quality_model
import colrev.record
from colrev.constants import DefectCodes
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


@pytest.mark.parametrize(
    "author_str, defects",
    [
        ("{{European Union}}", {}),
        ("RAI", {DefectCodes.MOSTLY_ALL_CAPS, DefectCodes.INCOMPLETE_FIELD}),
        (
            "Rai, Arun and B,",
            {DefectCodes.INCOMPLETE_FIELD, DefectCodes.NAME_FORMAT_SEPARTORS},
        ),
        ("Rai, Arun and B", {DefectCodes.NAME_FORMAT_SEPARTORS}),
        # additional title
        (
            "Rai, PhD, Arun",
            {DefectCodes.NAME_FORMAT_TITLES, DefectCodes.NAME_FORMAT_SEPARTORS},
        ),
        (
            "Rai, Phd, Arun",
            {DefectCodes.NAME_FORMAT_TITLES, DefectCodes.NAME_FORMAT_SEPARTORS},
        ),
        ("GuyPhD, Arun", {}),  #
        (
            "Rai, Arun; Straub, Detmar",
            {DefectCodes.NAME_FORMAT_SEPARTORS},
        ),
        # author without capital letters
        # NOTE: it's not a separator error, should be something more relevant
        (
            "Mathiassen, Lars and jonsson, katrin",
            {DefectCodes.NAME_FORMAT_SEPARTORS},
        ),
        (
            "University, Villanova and Sipior, Janice",
            {"erroneous-term-in-field"},
        ),
        (
            "Mourato, Inês and Dias, Álvaro and Pereira, Leandro",
            {},
        ),
        ("DUTTON, JANE E. and ROBERTS, LAURA", {DefectCodes.MOSTLY_ALL_CAPS}),
        ("Rai, Arun et al.", {DefectCodes.NAME_ABBREVIATED}),
        (
            "Rai, Arun, and others",
            {
                DefectCodes.NAME_FORMAT_SEPARTORS,
                DefectCodes.NAME_ABBREVIATED,
                DefectCodes.INCOMPLETE_FIELD,
            },
        ),
        (
            "Rai, and others",
            {
                DefectCodes.NAME_FORMAT_SEPARTORS,
                DefectCodes.INCOMPLETE_FIELD,
                DefectCodes.NAME_ABBREVIATED,
            },
        ),
        (
            "Neale, J. and Boitano, T. and Cooke, M. and Morrow, D. and et al.",
            {DefectCodes.NAME_ABBREVIATED, DefectCodes.NAME_FORMAT_SEPARTORS},
        ),
        (
            "Brocke, Jan vom",
            {DefectCodes.NAME_PARTICLES},
        ),
        (
            "vom Brocke, Jan",
            {DefectCodes.NAME_PARTICLES},
        ),
        (
            "{vom Brocke}, Jan",
            {},
        ),
        # (
        #     "Þórðarson, Kristinn and Oskarsdottir, Maria",
        #     [],
        # ),
    ],
)
def test_get_quality_defects_author(
    author_str: str,
    defects: set,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - author field"""
    v_t_record.data[Fields.AUTHOR] = author_str
    v_t_record.run_quality_model(qm=quality_model)
    if not defects:
        if v_t_record.has_quality_defects():
            print(v_t_record.defects(field=Fields.AUTHOR))
        assert not v_t_record.has_quality_defects()
        return

    assert v_t_record.has_quality_defects()
    # for defect in defects:
    actual = set(v_t_record.data[Fields.MD_PROV][Fields.AUTHOR]["note"].split(","))
    assert defects == actual


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
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data[Fields.TITLE] = title_str

    v_t_record.run_quality_model(qm=quality_model)
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
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - journal field"""
    v_t_record.data[Fields.JOURNAL] = journal_str

    v_t_record.run_quality_model(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.JOURNAL]["note"].split(
            ","
        )
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "name_str, defects",
    [
        ("Author, Name and Other, Author", [DefectCodes.THESIS_WITH_MULTIPLE_AUTHORS]),
    ],
)
def test_thesis_multiple_authors(
    name_str: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - thesis with multiple authors"""
    v_t_record.data[Fields.ENTRYTYPE] = "thesis"
    v_t_record.data[Fields.AUTHOR] = name_str

    v_t_record.run_quality_model(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.AUTHOR]["note"].split(
            ","
        )
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "year, defects",
    [
        ("204", [DefectCodes.YEAR_FORMAT]),
        ("2004", []),
    ],
)
def test_year(
    year: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - thesis with multiple authors"""
    v_t_record.data[Fields.YEAR] = year

    v_t_record.run_quality_model(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.YEAR]["note"].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "titles, defects",
    [
        (
            ["Test title", Fields.JOURNAL, "Test title"],
            [DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER],
        ),
        (["Test title", "booktitle", "Test Book"], []),
        (
            ["Test title", "booktitle", "Test title"],
            [DefectCodes.IDENTICAL_VALUES_BETWEEN_TITLE_AND_CONTAINER],
        ),
    ],
)
def test_get_quality_defects_identical_title(
    titles: list,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test record.get_quality_defects() - title field"""
    v_t_record.data[Fields.TITLE] = titles[0]
    v_t_record.data[titles[1]] = titles[2]

    if titles[1] == "booktitle":
        v_t_record.data[Fields.ENTRYTYPE] = "incollection"
        v_t_record.data[Fields.PUBLISHER] = "not missing"

    v_t_record.run_quality_model(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.TITLE]["note"].split(
            ","
        )
    assert v_t_record.has_quality_defects()


def test_get_quality_defects_testing_missing_field_year_forthcoming(
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Tests for when year = forthcoming"""

    v_t_record.data[Fields.YEAR] = "forthcoming"
    del v_t_record.data[Fields.VOLUME]
    del v_t_record.data[Fields.NUMBER]
    v_t_record.run_quality_model(qm=quality_model)
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
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test if booktitle is abbreviated"""

    v_t_record.data[Fields.ENTRYTYPE] = "inbook"
    v_t_record.data[Fields.BOOKTITLE] = booktitle
    v_t_record.data[Fields.CHAPTER] = 10
    v_t_record.data[Fields.PUBLISHER] = "nobody"
    del v_t_record.data[Fields.JOURNAL]
    v_t_record.run_quality_model(qm=quality_model)
    if not defects:
        assert not v_t_record.has_quality_defects()
        return
    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.BOOKTITLE][
            "note"
        ].split(",")
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "language, defects",
    [
        ("eng", []),
        ("cend", ["language-format-error"]),  # TODO
    ],
)
def test_get_quality_defects_language_format(
    language: str,
    defects: list,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Tests for invalid language code"""

    v_t_record.data[Fields.LANGUAGE] = language
    v_t_record.run_quality_model(qm=quality_model)

    if not defects:
        assert not v_t_record.has_quality_defects()
        return

    for defect in defects:
        assert defect in v_t_record.data[Fields.MD_PROV][Fields.LANGUAGE]["note"].split(
            ","
        )
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
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Tests for missing and inconsistent data for ENTRYTYPE"""

    v_t_record.data[Fields.ENTRYTYPE] = entrytype
    v_t_record.run_quality_model(qm=quality_model)
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


@pytest.mark.parametrize(
    "doi, defect",
    [
        ("10.1177/02683962211048201", False),
        ("10.5555/2014-04-01", False),
        ("https://journals.sagepub.com/doi/10.1177/02683962211048201", True),
    ],
)
def test_doi_not_matching_pattern(
    doi: str,
    defect: bool,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test the doi-not-matching-pattern checker"""
    v_t_record.data[Fields.DOI] = doi
    v_t_record.run_quality_model(qm=quality_model)
    # Ignore defects that should be tested separately
    v_t_record.remove_masterdata_provenance_note(
        key=Fields.DOI, note=DefectCodes.INCONSISTENT_WITH_DOI_METADATA
    )
    if not defect:
        assert not v_t_record.has_quality_defects()
        return
    assert (
        v_t_record.data[Fields.MD_PROV][Fields.DOI]["note"]
        == DefectCodes.DOI_NOT_MATCHING_PATTERN
    )
    assert v_t_record.has_quality_defects()


@pytest.mark.parametrize(
    "isbn, defect",
    [
        ("10.1177/02683962211048201", True),
        ("978-3-16-148410-0", False),
        ("978-1605666594", False),
    ],
)
def test_isbn_not_matching_pattern(
    isbn: str,
    defect: bool,
    book_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test the isbn-not-matching-pattern checker"""
    book_record.data[Fields.ISBN] = isbn
    book_record.run_quality_model(qm=quality_model)
    if not defect:
        print(book_record.data)
        assert not book_record.has_quality_defects()
        return
    assert (
        DefectCodes.ISBN_NOT_MATCHING_PATTERN
        in book_record.data[Fields.MD_PROV][Fields.ISBN]["note"]
    )
    assert book_record.has_quality_defects()


@pytest.mark.parametrize(
    "pmid, defect",
    [
        ("1", False),
        ("33044175", False),
        ("33044175.2", False),
        ("10.1177/02683962211048201", True),
    ],
)
def test_pubmedid_not_matching_pattern(
    pmid: str,
    defect: bool,
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    """Test the doi-not-matching-pattern checker"""
    v_t_record.data[Fields.PUBMED_ID] = pmid
    v_t_record.run_quality_model(qm=quality_model)
    if not defect:
        assert not v_t_record.has_quality_defects()
        return
    assert (
        v_t_record.data[Fields.MD_PROV][Fields.PUBMED_ID]["note"]
        == DefectCodes.PUBMED_ID_NOT_MATCHING_PATTERN
    )
    assert v_t_record.has_quality_defects()


def test_retracted(
    quality_model: colrev.qm.quality_model.QualityModel,
    v_t_record: colrev.record.Record,
) -> None:
    """Test whether run_quality_model detects retracts"""

    # Retracted (crossmark)
    r1_mod = v_t_record.copy_prep_rec()
    r1_mod.data["crossmark"] = "True"
    r1_mod.data[Fields.LANGUAGE] = "eng"
    r1_mod.run_quality_model(qm=quality_model)
    expected = v_t_record.copy_prep_rec()
    expected.data[Fields.PRESCREEN_EXCLUSION] = "retracted"
    expected.data[Fields.STATUS] = colrev.record.RecordState.rev_prescreen_excluded
    expected.data[Fields.MD_PROV] = {}
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
    #     "colrev_status": colrev.record.RecordState.rev_prescreen_excluded,
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
    v_t_record: colrev.record.Record,
    quality_model: colrev.qm.quality_model.QualityModel,
) -> None:
    v_t_record.data["journal"] = "JOURNAL OF INFORMATION TECHNOLOGY"
    v_t_record.run_quality_model(qm=quality_model)
    v_t_record.ignore_defect(field="journal", defect=DefectCodes.MOSTLY_ALL_CAPS)
    v_t_record.run_quality_model(qm=quality_model, set_prepared=True)
    assert v_t_record.data[Fields.STATUS] == colrev.record.RecordState.md_prepared
    assert not v_t_record.has_quality_defects()
