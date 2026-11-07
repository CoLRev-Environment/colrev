"""Tests for the ColRev-facing grobid_tei compatibility API."""

from pathlib import Path
from typing import Any

import pytest
import requests

import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import RecordState

TEI_XML = b"""<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc><sourceDesc><biblStruct xml:id="paper-id">
      <analytic>
        <author><persName>
          <forename type="first">J</forename>
          <forename type="middle">B</forename><surname>Writer</surname>
        </persName><email>j@example.org</email>
        <idno type="ORCID">0000-0000</idno></author>
        <title>Paper Title (Completed paper)</title>
      </analytic>
      <monogr><imprint><date when="2025-03"/></imprint></monogr>
      <idno type="DOI">10.1000/paper</idno>
    </biblStruct></sourceDesc></fileDesc>
    <profileDesc>
      <abstract><p>A descriptive abstract with enough text to cover the test case.</p></abstract>
      <textClass><keywords><term>keyword one</term><term>keyword two</term></keywords></textClass>
    </profileDesc>
    <encodingDesc><appInfo><application version="0.9.0"/></appInfo></encodingDesc>
  </teiHeader>
  <text><body><div><head>Introduction</head>
    <p>This is a sufficiently long paragraph that includes a citation to a work.</p>
    <ref type="bibr" target="#ref-1">(Writer, 2020)</ref>
  </div></body><back><listBibl>
    <biblStruct xml:id="ref-1">
      <analytic>
        <author><persName><forename type="first">A</forename>
          <surname>Author</surname></persName></author>
        <title>An article title</title>
      </analytic>
      <monogr><title level="j">Journal of Tests</title><imprint>
        <date when="2020-06-01"/><biblScope unit="volume">5</biblScope>
        <biblScope unit="issue">2</biblScope><biblScope unit="page" from="1" to="9"/>
      </imprint></monogr><idno type="DOI">10.1000/ref</idno>
    </biblStruct>
    <biblStruct><analytic><title>Untyped reference</title></analytic></biblStruct>
  </listBibl></back></text>
</TEI>"""
MINIMAL_TEI = b"""<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><sourceDesc><biblStruct>
    <analytic><author><persName><surname>OnlySurname</surname></persName></author>
      <title>Minimal document</title></analytic>
  </biblStruct></sourceDesc></fileDesc></teiHeader>
</TEI>"""


def test_tei_constructor_and_colrev_field_adaptation(tmp_path: Path) -> None:
    """Existing TEI files expose ColRev field names and legacy empty values."""
    tei_path = tmp_path / "paper.tei.xml"
    tei_path.write_bytes(TEI_XML)

    parser = colrev.env.tei_parser.TEIParser(tei_path=tei_path)

    assert parser.get_grobid_version() == "0.9.0"
    assert parser.get_abstract() == (
        "A descriptive abstract with enough text to cover the test case."
    )
    assert parser.get_metadata() == {
        Fields.ENTRYTYPE: ENTRYTYPES.MISC,
        Fields.AUTHOR: "Writer, J. B",
        Fields.TITLE: "Paper Title",
        Fields.YEAR: "2025",
        Fields.DOI: "10.1000/paper",
        Fields.ID: "paper-id",
        Fields.TEI_ID: "paper-id",
    }
    assert parser.get_paper_keywords() == ["keyword one", "keyword two"]
    assert parser.get_author_details() == [
        {
            "surname": "Writer",
            "forename": "J",
            "middlename": "B",
            "email": "j@example.org",
            "orcid": "0000-0000",
        }
    ]
    assert list(parser.iter_paragraphs()) == [
        "This is a sufficiently long paragraph that includes a citation to a work."
    ]


def test_absent_metadata_values_use_library_author_details(
    tmp_path: Path,
) -> None:
    """Absent author fields follow grobid-tei's native return shape."""
    tei_path = tmp_path / "minimal.tei.xml"
    tei_path.write_bytes(MINIMAL_TEI)
    parser = colrev.env.tei_parser.TEIParser(tei_path=tei_path)

    assert parser.get_grobid_version() == ""
    assert parser.get_abstract() == ""
    assert parser.get_paper_keywords() == []
    assert parser.get_author_details() == parser.document.author_details()
    assert parser.get_metadata()[Fields.ENTRYTYPE] == ENTRYTYPES.MISC


def test_reference_conversion_and_optional_citation_counts(tmp_path: Path) -> None:
    """TEIReference data becomes ColRev records with counts only on request."""
    tei_path = tmp_path / "paper.tei.xml"
    tei_path.write_bytes(TEI_XML)
    parser = colrev.env.tei_parser.TEIParser(tei_path=tei_path)

    references = parser.get_references()
    assert references[0] == {
        Fields.ID: "ref-1",
        Fields.TEI_ID: "ref-1",
        Fields.ENTRYTYPE: ENTRYTYPES.ARTICLE,
        Fields.AUTHOR: "Author, A.",
        Fields.TITLE: "An article title",
        Fields.YEAR: "2020",
        Fields.JOURNAL: "Journal of Tests",
        Fields.VOLUME: "5",
        Fields.NUMBER: "2",
        Fields.PAGES: "1--9",
        Fields.DOI: "10.1000/ref",
    }
    assert Fields.NR_INTEXT_CITATIONS not in references[0]
    counted_references = parser.get_references(add_intext_citation_count=True)
    assert counted_references[0][Fields.NR_INTEXT_CITATIONS] == 1
    assert counted_references[1][Fields.NR_INTEXT_CITATIONS] == 0
    assert Fields.ID not in counted_references[1]
    assert parser.get_citations_per_section() == {"introduction": ["ref-1"]}


def test_mark_references_annotates_and_persists_library_document(
    tmp_path: Path, mocker: Any
) -> None:
    """ColRev performs matching, then grobid_tei annotates and serializes IDs."""
    tei_path = tmp_path / "paper.tei.xml"
    tei_path.write_bytes(TEI_XML)
    parser = colrev.env.tei_parser.TEIParser(tei_path=tei_path)
    mocker.patch("colrev.record.record.Record.get_record_similarity", return_value=0.95)
    records = {
        "LOCAL": {
            Fields.ID: "LOCAL",
            Fields.STATUS: RecordState.rev_included,
            Fields.TITLE: "An article title",
        },
        "EXCLUDED": {
            Fields.ID: "EXCLUDED",
            Fields.STATUS: RecordState.rev_prescreen_excluded,
            Fields.TITLE: "An article title",
        },
    }

    returned_root = parser.mark_references(records=records)

    assert returned_root is parser.root
    serialized = tei_path.read_bytes()
    assert b'<biblStruct xml:id="ref-1" ID="LOCAL">' in serialized
    assert b'target="#ref-1" ID="LOCAL"' in serialized
    assert b"EXCLUDED" not in serialized
    reparsed = colrev.env.tei_parser.grobid_tei.TEIDocument.from_file(tei_path)
    assert reparsed.references()[0].tei_id == "ref-1"


def test_pdf_constructor_keeps_grobid_service_in_colrev(
    tmp_path: Path, mocker: Any
) -> None:
    """PDF construction submits to ColRev's service and persists returned TEI."""
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"pdf data")
    tei_path = tmp_path / "nested" / "paper.tei.xml"
    service = mocker.patch("colrev.env.grobid_service.GrobidService")
    service.return_value.GROBID_URL = "http://grobid.test"
    client = mocker.patch("colrev.env.tei_parser.grobid_tei.GrobidClient")
    client.return_value.process_fulltext.return_value = TEI_XML

    parser = colrev.env.tei_parser.TEIParser(
        pdf_path=pdf_path,
        tei_path=tei_path,
        consolidate_header=True,
        consolidate_citations=True,
    )

    assert parser.get_metadata()[Fields.TITLE] == "Paper Title"
    assert tei_path.is_file()
    service.assert_called()
    client.assert_called_once_with(service_url="http://grobid.test", timeout=180)
    client.return_value.process_fulltext.assert_called_once_with(
        pdf_path, consolidate_header=True, consolidate_citations=True
    )
    assert b"paper-id" in tei_path.read_bytes()


def test_pdf_consolidation_options_default_to_false(
    tmp_path: Path, mocker: Any
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"pdf data")
    service = mocker.patch("colrev.env.grobid_service.GrobidService")
    service.return_value.GROBID_URL = "http://grobid.test"
    client = mocker.patch("colrev.env.tei_parser.grobid_tei.GrobidClient")
    client.return_value.process_fulltext.return_value = TEI_XML

    colrev.env.tei_parser.TEIParser(pdf_path=pdf_path)

    client.return_value.process_fulltext.assert_called_once_with(
        pdf_path, consolidate_header=False, consolidate_citations=False
    )


def test_existing_tei_takes_precedence_over_pdf(tmp_path: Path, mocker: Any) -> None:
    """An existing TEI is loaded without starting GROBID, even with a PDF path."""
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"pdf data")
    tei_path = tmp_path / "paper.tei.xml"
    tei_path.write_bytes(MINIMAL_TEI)
    service = mocker.patch("colrev.env.grobid_service.GrobidService")
    client = mocker.patch("colrev.env.tei_parser.grobid_tei.GrobidClient")

    parser = colrev.env.tei_parser.TEIParser(pdf_path=pdf_path, tei_path=tei_path)

    assert parser.get_metadata()[Fields.TITLE] == "Minimal document"
    service.assert_not_called()
    client.assert_not_called()


@pytest.mark.parametrize(
    ("response_content", "expected_exception"),
    [
        (b"[TIMEOUT]", colrev_exceptions.TEITimeoutException),
        (b"[BAD_INPUT_DATA]", colrev_exceptions.TEIException),
        (b"not xml", colrev_exceptions.TEIException),
    ],
)
def test_pdf_grobid_response_errors(
    tmp_path: Path,
    mocker: Any,
    response_content: bytes,
    expected_exception: type[Exception],
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"pdf data")
    service = mocker.patch("colrev.env.grobid_service.GrobidService")
    service.return_value.GROBID_URL = "http://grobid.test"
    client = mocker.patch("colrev.env.tei_parser.grobid_tei.GrobidClient")
    client.return_value.process_fulltext.return_value = response_content

    with pytest.raises(expected_exception):
        colrev.env.tei_parser.TEIParser(pdf_path=pdf_path)


def test_pdf_connection_failure_maps_to_tei_timeout(
    tmp_path: Path, mocker: Any
) -> None:
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"pdf data")
    service = mocker.patch("colrev.env.grobid_service.GrobidService")
    service.return_value.GROBID_URL = "http://grobid.test"
    service_error = colrev.env.tei_parser.grobid_tei.GrobidServiceError(
        "service unavailable"
    )
    service_error.__cause__ = requests.exceptions.ConnectionError("service unavailable")
    client = mocker.patch("colrev.env.tei_parser.grobid_tei.GrobidClient")
    client.return_value.process_fulltext.side_effect = service_error

    with pytest.raises(colrev_exceptions.TEITimeoutException):
        colrev.env.tei_parser.TEIParser(pdf_path=pdf_path)


def test_tei_file_errors_and_missing_pdf(tmp_path: Path) -> None:
    """Malformed TEI and missing PDF files keep ColRev's public exceptions."""
    tei_path = tmp_path / "bad.tei.xml"
    tei_path.write_bytes(b"<not valid")
    with pytest.raises(colrev_exceptions.TEIException):
        colrev.env.tei_parser.TEIParser(tei_path=tei_path)
    with pytest.raises(FileNotFoundError):
        colrev.env.tei_parser.TEIParser(pdf_path=tmp_path / "missing.pdf")
    with pytest.raises(ValueError, match="Either pdf_path or tei_path"):
        colrev.env.tei_parser.TEIParser()


def test_pdf_record_optional_doi_extraction(mocker: Any, tmp_path: Path) -> None:
    """Optional DOI extraction is still invoked and modifies the record."""
    pdf_path = tmp_path / "paper.pdf"
    tei_parser = mocker.Mock()
    tei_parser.get_metadata.return_value = {Fields.TITLE: "PDF title"}
    tei_parser.get_grobid_version.return_value = "0.9.0"
    mocker.patch("colrev.env.tei_parser.TEIParser", return_value=tei_parser)

    def make_pdf_record(data: dict, *, path: Path) -> Any:
        pdf_record = mocker.Mock()
        pdf_record.data = data
        pdf_record.set_text_from_pdf.side_effect = lambda **_: pdf_record.data.update(
            {Fields.TEXT_FROM_PDF: "DOI 10.1234/example", Fields.NR_PAGES_IN_FILE: 3}
        )
        return pdf_record

    mocker.patch(
        "colrev.env.tei_parser.colrev.record.record_pdf.PDFRecord",
        side_effect=make_pdf_record,
    )

    result = colrev.env.tei_parser.get_record_from_pdf(pdf_path, add_doi_from_pdf=True)

    assert result[Fields.DOI] == "10.1234/EXAMPLE"
    assert Fields.TEXT_FROM_PDF not in result
    assert Fields.NR_PAGES_IN_FILE not in result


def test_pdf_timeout_returns_minimal_record(mocker: Any, tmp_path: Path) -> None:
    """The helper still returns a minimal PDF record when GROBID times out."""
    pdf_path = tmp_path / "paper.pdf"
    mocker.patch(
        "colrev.env.tei_parser.TEIParser",
        side_effect=colrev_exceptions.TEITimeoutException,
    )

    assert colrev.env.tei_parser.get_record_from_pdf(pdf_path) == {
        Fields.FILE: str(pdf_path),
        Fields.ENTRYTYPE: ENTRYTYPES.MISC,
    }
