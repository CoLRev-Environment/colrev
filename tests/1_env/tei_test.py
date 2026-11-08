#!/usr/bin/env python
"""Test the tei parser"""

import platform
import re
from difflib import unified_diff
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

    return Path(request.fspath).parents[0]


@pytest.fixture(scope="module")
def tei_doc(script_loc) -> colrev.env.tei_parser.TEIParser:  # type: ignore
    """Return the tei_doc"""

    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")

    tei_file = script_loc.parent.joinpath("data/WagnerLukyanenkoParEtAl2022.tei.xml")

    tei_doc = colrev.env.tei_parser.TEIParser(tei_path=tei_file)
    return tei_doc


def test_tei_creation(script_loc, tmp_path) -> None:  # type: ignore
    """Test the tei"""

    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")

    tei_file = script_loc.parent.joinpath("data/WagnerLukyanenkoParEtAl2022.tei.xml")
    pdf_path = script_loc.parent.joinpath("data/WagnerLukyanenkoParEtAl2022.pdf")
    baseline = tei_file.read_text()

    generated_tei_file = tmp_path / tei_file.name
    colrev.env.tei_parser.TEIParser(
        pdf_path=pdf_path,
        tei_path=generated_tei_file,
    )

    def normalize_tei_xml(tei_content: str) -> str:
        """Normalize volatile data and TEI namespace prefixes for comparison."""
        tei_namespace = "http://www.tei-c.org/ns/1.0"
        tei_prefixes = re.findall(
            rf'xmlns:([^=\s]+)="{re.escape(tei_namespace)}"', tei_content
        )
        for prefix in tei_prefixes:
            tei_content = re.sub(rf"(<[/]?){re.escape(prefix)}:", r"\1", tei_content)
            namespace_declaration = f'xmlns:{prefix}="{tei_namespace}"'
            if f'xmlns="{tei_namespace}"' in tei_content:
                tei_content = tei_content.replace(namespace_declaration, "", 1)
            else:
                tei_content = tei_content.replace(
                    namespace_declaration, f'xmlns="{tei_namespace}"', 1
                )
        return re.sub(
            r'(ident="GROBID" when=")[^"]+(">)',
            r"\g<1>NA\g<2>",
            tei_content,
        )

    baseline = normalize_tei_xml(baseline)
    generated = normalize_tei_xml(generated_tei_file.read_text())
    if generated != baseline:
        # Write the candidate so GROBID changes are reviewable in git diff, but
        # fail this run to make the change explicit and require review.
        tei_file.write_text(generated)
        diff = unified_diff(
            baseline.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile=str(tei_file),
            tofile="generated TEI",
        )
        pytest.fail(
            "Generated TEI differs from the tracked fixture. Review the fixture "
            "diff and rerun the test after accepting the change.\n" + "".join(diff)
        )
    elif tei_file.read_text() != generated:
        # Keep the fixture's representation canonical even when only normalized
        # details (for example, a namespace prefix) differ.
        tei_file.write_text(generated)


def test_tei_version(tei_doc) -> None:  # type: ignore
    """Test the tei version"""
    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")
    assert "0.9.0" == tei_doc.get_grobid_version()


def test_tei_get_metadata(tei_doc) -> None:  # type: ignore
    """Test the tei version"""
    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")
    assert (
        "Artificial intelligence (AI) is beginning to transform traditional research practices in many areas. In this context, literature reviews stand out because they operate on large and rapidly growing volumes of documents, that is, partially structured (meta)data, and pervade almost every type of paper published in information systems research or related social science disciplines. To familiarize researchers with some of the recent trends in this area, we outline how AI can expedite individual steps of the literature review process. Considering that the use of AI in this context is in an early stage of development, we propose a comprehensive research agenda for AI-based literature reviews (AILRs) in our field. With this agenda, we would like to encourage design science research and a broader constructive discourse on shaping the future of AILRs in research."
        == tei_doc.get_abstract()
    )

    # Note : Journal extraction not (yet) supported well
    # Did not find a journal paper where the journal was extracted correctly
    assert {
        Fields.ENTRYTYPE: ENTRYTYPES.MISC,
        Fields.AUTHOR: (
            "Wagner, Gerit and Lukyanenko, Roman and Par, Guy and Paré, Guy "
            "and Id, Orcid"
        ),
        Fields.DOI: "10.1177/02683962211048201",
        Fields.TITLE: "Artificial intelligence and the conduct of literature reviews",
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
            "email": "guy.pare@hec.ca",
            "orcid": "0000-0001-7425-1994",
        },
        {
            "surname": "Paré",
            "forename": "Guy",
            "orcid": "0000-0001-7425-1994",
        },
        {"surname": "Id", "forename": "Orcid"},
    ] == tei_doc.get_author_details()


def test_tei_reference_extraction(tei_doc) -> None:  # type: ignore
    """Check CoLRev reference adaptation on representative GROBID output.

    Detailed generic reference-extraction coverage belongs in grobid-tei; this
    integration test checks the pinned corpus and CoLRev-facing fields.
    """
    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")

    assert tei_doc.get_grobid_version() == "0.9.0"
    references = tei_doc.get_references(add_intext_citation_count=True)
    references_by_tei_id = {
        reference[Fields.TEI_ID]: reference for reference in references
    }

    assert len(references) == 120
    assert len(references_by_tei_id) == len(references)
    assert references_by_tei_id["b0"] == {
        Fields.ID: "b0",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.TEI_ID: "b0",
        Fields.AUTHOR: "Adams, C. E and Polzmacher, S. and Wolff, A.",
        Fields.TITLE: "Systematic reviews: work that needs to be done and not to be done",
        Fields.YEAR: "2013",
        Fields.JOURNAL: "Journal of Evidence-Based Medicine",
        Fields.VOLUME: "6",
        Fields.NUMBER: "4",
        Fields.PAGES: "232--235",
        Fields.NR_INTEXT_CITATIONS: 1,
    }
    assert references_by_tei_id["b6"] == {
        Fields.ID: "b6",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.TEI_ID: "b6",
        Fields.AUTHOR: "Antons, D. and Breidbach, C. F and Joshi, A. M",
        Fields.TITLE: "Computational literature reviews: method, algorithms, and roadmap",
        Fields.YEAR: "2021",
        Fields.JOURNAL: "Organizational Research Methods",
        Fields.NR_INTEXT_CITATIONS: 2,
    }


def test_tei_citations_per_section(tei_doc, tmp_path) -> None:  # type: ignore
    """Test the tei citations per section method."""

    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")

    assert tei_doc.get_grobid_version() == "0.9.0"
    citations = tei_doc.get_citations_per_section()
    assert citations["introduction"][0] == "b0"
    assert len(citations["introduction"]) == 19
    assert citations["smart search technologies."]
    assert citations["concluding remarks"] == ["b62", "b89", "b117"]


def test_tei_mark_references(tei_doc, tmp_path) -> None:  # type: ignore
    """Test the tei extraction of references"""

    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")
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
    expected = 'xml:id="b118" ID="TEST_ID"'
    assert expected in actual

    expected = 'theoretical rationale <tei:ref type="bibr" target="#b118" ID="TEST_ID">(Whetten, 1989)</tei:ref>, which is critical '
    assert expected in actual

    assert "NO_TITLE" not in actual

    assert "NOT_INCLUDED" not in actual


def test_tei_exception(tmp_path) -> None:  # type: ignore
    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")
    tei_path = tmp_path / Path("erroneous_tei.tei.xml")

    with open(tei_path, "wb") as f:
        f.write(b"[BAD_INPUT_DATA]")

    with pytest.raises(colrev_exceptions.TEIException):
        colrev.env.tei_parser.TEIParser(tei_path=tei_path)


def test_tei_pdf_not_exists() -> None:
    if platform.system() != "Linux":
        pytest.skip("Docker tests only run on Linux runners")

    pdf_path = Path("data/non_existent.pdf")

    with pytest.raises(FileNotFoundError):
        colrev.env.tei_parser.TEIParser(pdf_path=pdf_path)
