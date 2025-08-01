#!/usr/bin/env python
"""Test the tei parser"""
import json
import platform
import re
from pathlib import Path

import pytest

import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

# pylint: disable=line-too-long
# pylint: disable=too-many-lines


@pytest.fixture(scope="module")
def script_loc(request) -> Path:  # type: ignore
    """Return the directory of the currently running test script"""

    return Path(request.fspath).parent


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
@pytest.fixture(scope="module")
def tei_doc(script_loc) -> colrev.env.tei_parser.TEIParser:  # type: ignore
    """Return the tei_doc"""

    tei_file = script_loc.parent.joinpath("data/WagnerLukyanenkoParEtAl2022.tei.xml")

    tei_doc = colrev.env.tei_parser.TEIParser(tei_path=tei_file)
    return tei_doc


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_creation(script_loc) -> None:  # type: ignore
    """Test the tei"""
    tei_file = script_loc.parent.joinpath("data/WagnerLukyanenkoParEtAl2022.tei.xml")
    pdf_path = script_loc.parent.joinpath("data/WagnerLukyanenkoParEtAl2022.pdf")

    tmp_tei_file = tei_file.with_name(tei_file.stem + "_tmp.tei.xml")
    if tmp_tei_file.exists():
        tmp_tei_file.unlink(missing_ok=True)
    tei_file.rename(tmp_tei_file)

    try:

        colrev.env.tei_parser.TEIParser(pdf_path=pdf_path, tei_path=tei_file)

        with open(tei_file) as file:
            tei_content = file.read()

        tei_content = re.sub(
            r'(ident="GROBID" when=")[^"]+(">)', r"\g<1>NA\g<2>", tei_content
        )

        with open(tei_file, "w") as file:
            file.write(tei_content)
    except Exception as exc:
        print("Restoring original TEI file")
        tmp_tei_file.rename(tei_file)
        raise exc


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_version(tei_doc) -> None:  # type: ignore
    """Test the tei version"""
    assert "0.8.2" == tei_doc.get_grobid_version()


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_get_metadata(tei_doc) -> None:  # type: ignore
    """Test the tei version"""
    assert (
        "Artificial intelligence (AI) is beginning to transform traditional research practices in many areas. In this context, literature reviews stand out because they operate on large and rapidly growing volumes of documents, that is, partially structured (meta)data, and pervade almost every type of paper published in information systems research or related social science disciplines. To familiarize researchers with some of the recent trends in this area, we outline how AI can expedite individual steps of the literature review process. Considering that the use of AI in this context is in an early stage of development, we propose a comprehensive research agenda for AI-based literature reviews (AILRs) in our field. With this agenda, we would like to encourage design science research and a broader constructive discourse on shaping the future of AILRs in research."
        == tei_doc.get_abstract()
    )

    # Note : Journal extraction not (yet) supported well
    # Did not find a journal paper where the journal was extracted correctly
    assert {
        Fields.ENTRYTYPE: ENTRYTYPES.MISC,
        Fields.AUTHOR: "Wagner, Gerit and Lukyanenko, Roman and Par, Guy and Paré, Guy",
        Fields.DOI: "10.1177/02683962211048201",
        Fields.TITLE: "Debates and Perspectives Paper",
    } == tei_doc.get_metadata()

    assert [
        "Artificial intelligence",
        "machine learning",
        "natural language processing",
        "research data management",
        "data infrastructure",
        "automation",
        "literature review",
    ] == tei_doc.get_paper_keywords()

    assert [
        {"surname": "Wagner", "forename": "Gerit"},
        {"surname": "Lukyanenko", "forename": "Roman"},
        {
            "surname": "Par",
            "forename": "Guy",
            "emai": "guy.pare@hec.ca",
            "ORCID": "0000-0001-7425-1994",
        },
        {"surname": "Paré", "forename": "Guy"},
    ] == tei_doc.get_author_details()


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_reference_extraction(tei_doc, helpers) -> None:  # type: ignore
    """Test the tei extraction of references"""

    expected_file = Path("data/tei/references_expected.json")
    actual = tei_doc.get_references(add_intext_citation_count=True)
    try:
        with open(helpers.test_data_path / expected_file, encoding="utf-8") as file:
            expected = json.load(file)
    except FileNotFoundError as exc:
        with open(
            helpers.test_data_path / expected_file, "w", encoding="utf-8"
        ) as file:
            json.dump(actual, file, indent=4)
        raise Exception(
            f"The expected_file ({expected_file.name}) was not (yet) available. "
            f"An initial version was created in {expected_file}. "
            "Please check, update, and add/commit it. Afterwards, rerun the tests."
        ) from exc

    if expected != actual:
        with open(
            helpers.test_data_path / expected_file, "w", encoding="utf-8"
        ) as file:
            json.dump(actual, file, indent=4)
    assert expected == actual


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_citations_per_section(tei_doc, helpers, tmp_path) -> None:  # type: ignore
    """Test the tei citations per section method."""

    expected_file = Path("data/tei/citations_per_section_expected.json")
    actual = tei_doc.get_citations_per_section()
    try:
        with open(helpers.test_data_path / expected_file, encoding="utf-8") as file:
            expected = json.load(file)
    except FileNotFoundError as exc:
        with open(
            helpers.test_data_path / expected_file, "w", encoding="utf-8"
        ) as file:
            json.dump(actual, file, indent=4)
        raise Exception(
            f"The expected_file ({expected_file.name}) was not (yet) available. "
            f"An initial version was created in {expected_file}. "
            "Please check, update, and add/commit it. Afterwards, rerun the tests."
        ) from exc

    if expected != actual:
        with open(
            helpers.test_data_path / expected_file, "w", encoding="utf-8"
        ) as file:
            json.dump(actual, file, indent=4)
    assert expected == actual


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_mark_references(tei_doc, tmp_path) -> None:  # type: ignore
    """Test the tei extraction of references"""

    # change tei_path to prevent changes to the original tei file
    tei_doc.tei_path = tmp_path / Path("test.tei.xml")
    tei_doc.mark_references(
        records={
            "TEST_ID": {
                Fields.ID: "TEST_ID",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.STATUS: RecordState.rev_included,
                Fields.TITLE: "What constitutes a theoretical contribution?",
                Fields.JOURNAL: "Academy of Management Review",
                Fields.AUTHOR: "Whetten, D. A",
                Fields.YEAR: "1989",
                Fields.VOLUME: "14",
                Fields.NUMBER: "4",
            },
            "NO_TITLE": {
                Fields.ID: "NO_TITLE",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.STATUS: RecordState.rev_included,
                Fields.JOURNAL: "Academy of Management Review",
                Fields.AUTHOR: "Whetten, D. A",
                Fields.YEAR: "1989",
                Fields.VOLUME: "14",
                Fields.NUMBER: "4",
            },
            "NOT_INCLUDED": {
                Fields.ID: "NOT_INCLUDED",
                Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
                Fields.STATUS: RecordState.rev_prescreen_excluded,
                Fields.JOURNAL: "Academy of Management Review",
                Fields.AUTHOR: "Whetten, D. A",
                Fields.YEAR: "1989",
                Fields.VOLUME: "14",
                Fields.NUMBER: "4",
            },
        }
    )
    actual = tei_doc.get_tei_str()
    expected = '<biblStruct xml:id="b118" ID="TEST_ID">'
    assert expected in actual

    expected = 'theoretical rationale <ref type="bibr" target="#b118" ID="TEST_ID">(Whetten, 1989)</ref>, which is critical '
    assert expected in actual

    assert "NO_TITLE" not in actual

    assert "NOT_INCLUDED" not in actual


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_exception(tmp_path) -> None:  # type: ignore

    tei_path = tmp_path / Path("erroneous_tei.tei.xml")

    with open(tei_path, "wb") as f:
        f.write(b"[BAD_INPUT_DATA]")

    with pytest.raises(colrev_exceptions.TEIException):
        colrev.env.tei_parser.TEIParser(tei_path=tei_path)


@pytest.mark.skipif(
    platform.system() != "Linux", reason="Docker tests only run on Linux runners"
)
def test_tei_pdf_not_exists() -> None:

    pdf_path = Path("data/non_existent.pdf")

    with pytest.raises(FileNotFoundError):
        colrev.env.tei_parser.TEIParser(pdf_path=pdf_path)
