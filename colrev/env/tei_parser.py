#! /usr/bin/env python
"""Compatibility layer for parsing GROBID TEI documents in CoLRev."""

from __future__ import annotations

import re
import typing
from pathlib import Path
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import register_namespace
from xml.etree.ElementTree import tostring

import grobid_tei
import requests

import colrev.env.grobid_service
import colrev.exceptions as colrev_exceptions
import colrev.record.record
import colrev.record.record_pdf
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldsRegex
from colrev.constants import RecordState


class TEIParser:
    """ColRev-facing TEI API backed by :mod:`grobid_tei`."""

    ns = {
        "tei": "{http://www.tei-c.org/ns/1.0}",
        "w3": "{http://www.w3.org/XML/1998/namespace}",
    }
    nsmap = {
        "tei": "http://www.tei-c.org/ns/1.0",
        "w3": "http://www.w3.org/XML/1998/namespace",
    }
    _FIELD_MAP = {
        "author": Fields.AUTHOR,
        "title": Fields.TITLE,
        "year": Fields.YEAR,
        "pages": Fields.PAGES,
        "doi": Fields.DOI,
        "journal": Fields.JOURNAL,
        "volume": Fields.VOLUME,
        "number": Fields.NUMBER,
        "booktitle": Fields.BOOKTITLE,
        "entrytype": Fields.ENTRYTYPE,
    }

    def _colrev_fields(self, fields: typing.Mapping[str, str]) -> dict:
        """Map generic grobid_tei fields to ColRev field names."""
        converted = {}
        for generic_field, colrev_field in self._FIELD_MAP.items():
            if generic_field not in fields:
                continue
            value = fields[generic_field]
            if generic_field == "author":
                # grobid_tei retains empty-name separators as repeated spaces;
                # the previous parser normalized these while joining names.
                value = " ".join(value.split())
            converted[colrev_field] = value
        entrytype = converted.get(Fields.ENTRYTYPE, ENTRYTYPES.MISC)
        if entrytype != ENTRYTYPES.ARTICLE:
            converted.pop(Fields.JOURNAL, None)
        if entrytype not in {ENTRYTYPES.ARTICLE, ENTRYTYPES.INPROCEEDINGS}:
            converted.pop(Fields.VOLUME, None)
            converted.pop(Fields.NUMBER, None)
        if entrytype != ENTRYTYPES.INPROCEEDINGS:
            converted.pop(Fields.BOOKTITLE, None)
        return converted

    def __init__(
        self,
        *,
        pdf_path: typing.Optional[typing.Union[Path, str]] = None,
        tei_path: typing.Optional[typing.Union[Path, str]] = None,
        consolidate_header: bool = False,
        consolidate_citations: bool = False,
    ):
        """Create TEI from a PDF or read an existing TEI file.

        If both paths are supplied and ``tei_path`` already exists, it is read
        without contacting GROBID, as in the previous ColRev implementation.
        Consolidation flags apply when a PDF is submitted to GROBID.
        """
        if pdf_path is None and tei_path is None:
            raise ValueError("Either pdf_path or tei_path must be provided")
        if pdf_path is not None:
            pdf_path = Path(pdf_path)
            if pdf_path.is_symlink():  # pragma: no cover
                pdf_path = pdf_path.resolve()
        if tei_path is not None:
            tei_path = Path(tei_path)

        self.pdf_path = pdf_path
        self.tei_path = tei_path
        if pdf_path is not None and not pdf_path.is_file():
            raise FileNotFoundError

        if tei_path is not None and tei_path.is_file():
            try:
                self._set_document(grobid_tei.TEIDocument.from_file(tei_path))
            except grobid_tei.TEIParsingError as exc:
                raise colrev_exceptions.TEIException() from exc
        elif pdf_path is not None:
            # Keep GROBID lifecycle and PDF submission in ColRev. The service
            # constructor starts GROBID; the library only parses returned TEI.
            self._create_tei(
                consolidate_header=consolidate_header,
                consolidate_citations=consolidate_citations,
            )
        elif tei_path is not None:
            raise FileNotFoundError(tei_path)

    def _set_document(self, document: grobid_tei.TEIDocument) -> None:
        self.document = document
        # ``root`` was exposed by TEIParser and mark_references() historically
        # returned this Element. Keep that compatibility while delegating all
        # parsing and mutation to grobid_tei.
        # pylint: disable=protected-access
        self.root: Element = document._root

    def _create_tei(
        self, *, consolidate_header: bool = False, consolidate_citations: bool = False
    ) -> None:
        """Create TEI by submitting the PDF to ColRev's GROBID service."""
        grobid_service = colrev.env.grobid_service.GrobidService()

        try:
            assert self.pdf_path is not None
            grobid_client = grobid_tei.GrobidClient(
                service_url=grobid_service.GROBID_URL, timeout=180
            )
            tei_bytes = grobid_client.process_fulltext(
                self.pdf_path,
                consolidate_header=consolidate_header,
                consolidate_citations=consolidate_citations,
            )
            if b"[TIMEOUT]" in tei_bytes:  # pragma: no cover
                raise colrev_exceptions.TEITimeoutException()

            try:
                document = grobid_tei.TEIDocument.from_bytes(tei_bytes)
            except grobid_tei.TEIParsingError as exc:
                raise colrev_exceptions.TEIException() from exc
            self._set_document(document)

            if self.tei_path is not None:
                self.tei_path.parent.mkdir(exist_ok=True, parents=True)
                self.tei_path.write_bytes(self.document.to_bytes())
        except grobid_tei.GrobidServiceError as exc:  # pragma: no cover
            cause = exc.__cause__
            if isinstance(
                cause,
                (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
            ):
                raise colrev_exceptions.TEITimeoutException() from exc
            raise colrev_exceptions.TEIException() from exc

    def get_tei_str(self) -> str:
        """Return the TEI document as a Unicode string."""
        try:
            register_namespace("tei", self.nsmap["tei"])
            return tostring(self.root, encoding="unicode")
        except (TypeError, ValueError) as exc:  # pragma: no cover
            raise colrev_exceptions.TEIException() from exc

    def get_grobid_version(self) -> str:
        """Get the GROBID version recorded in the TEI, or an empty string."""
        return self.document.grobid_version() or ""

    def get_abstract(self) -> str:
        """Get the abstract, using the legacy empty-string value when absent."""
        return self.document.abstract() or ""

    def get_metadata(self) -> dict:
        """Return GROBID metadata using CoLRev's record field names.

        Bibliographic values come from grobid_tei's public metadata API. Page
        ranges and the document TEI ID retain their legacy TEI-specific
        conversion because the generic metadata mapping does not expose them.
        """
        metadata = self.document.metadata()
        record_dict = self._colrev_fields(metadata)
        record_dict.setdefault(Fields.ENTRYTYPE, ENTRYTYPES.MISC)

        source_desc = self.root.find(f".//{self.ns['tei']}sourceDesc")
        source_bibliography = (
            source_desc.find(f".//{self.ns['tei']}biblStruct")
            if source_desc is not None
            else None
        )
        if source_bibliography is not None:
            record_dict.pop(Fields.PAGES, None)
            page_string = self._legacy_page_string(source_bibliography)
            if page_string:
                record_dict[Fields.PAGES] = page_string
            tei_id = source_bibliography.get(self.ns["w3"] + "id")
            if tei_id:
                record_dict[Fields.ID] = tei_id
                record_dict[Fields.TEI_ID] = tei_id
        return {key: value for key, value in record_dict.items() if value != ""}

    def get_paper_keywords(self) -> list:
        """Get document keywords."""
        return self.document.keywords()

    def get_author_details(self) -> list:
        """Return author details in grobid-tei's native dictionary format."""
        return self.document.author_details()

    def get_references(self, *, add_intext_citation_count: bool = False) -> list:
        """Return references as ColRev record dictionaries."""
        references = self.document.references(
            include_citation_counts=add_intext_citation_count
        )
        reference_record_dicts = []
        tei_references = [
            reference_node
            for bibliography in self.root.iter(f"{self.ns['tei']}listBibl")
            for reference_node in bibliography
        ]
        for reference, tei_reference in zip(references, tei_references):
            record_dict = self._colrev_fields(reference.bibliographic_fields)
            # The legacy parser only accepted page-scope ``from``/``to``
            # attributes. grobid_tei also returns free-form page text, so keep
            # ColRev's previous absent-value behavior at this adapter boundary.
            record_dict.pop(Fields.PAGES, None)
            page_string = self._legacy_page_string(tei_reference)
            if page_string:
                record_dict[Fields.PAGES] = page_string
            record_dict.setdefault(Fields.ENTRYTYPE, ENTRYTYPES.MISC)
            if reference.tei_id:
                record_dict[Fields.ID] = reference.tei_id
                record_dict[Fields.TEI_ID] = reference.tei_id
            if add_intext_citation_count:
                record_dict[Fields.NR_INTEXT_CITATIONS] = (
                    reference.in_text_citation_count or 0
                )
            reference_record_dicts.append(record_dict)
        return reference_record_dicts

    def _legacy_page_string(self, reference: Element) -> str:
        """Format attributed page ranges using the historic ColRev convention."""
        page_string = ""
        pages = reference.findall(
            f"{self.ns['tei']}monogr/{self.ns['tei']}imprint/"
            f"{self.ns['tei']}biblScope[@unit='page']"
        )
        for page in pages:
            for name, value in sorted(page.attrib.items()):
                if name == "from":
                    page_string += value
                elif name == "to":
                    page_string += "--" + value
        return page_string

    def get_citations_per_section(self) -> dict:
        """Get section names mapped to their cited TEI IDs."""
        return self.document.citations_by_section()

    def iter_paragraphs(
        self,
        *,
        min_chars: int = 40,
        exclude_sections: typing.Iterable[str] = (
            "references",
            "reference",
            "bibliography",
            "acknowledgment",
            "acknowledgement",
            "appendix",
        ),
    ) -> typing.Iterator[str]:
        """Iterate over document paragraphs using grobid_tei's extraction."""
        return self.document.iter_paragraphs(
            min_chars=min_chars, exclude_sections=tuple(exclude_sections)
        )

    def mark_references(self, *, records: dict) -> Element:
        """Match references using ColRev and annotate the corresponding TEI IDs."""
        record_ids_by_tei_id = {}
        for reference_dict in self.get_references():
            if Fields.TITLE not in reference_dict:
                continue

            max_similarity = 0.9
            max_similarity_record = {}
            for local_record_dict in records.values():
                if local_record_dict[Fields.STATUS] not in [
                    RecordState.rev_included,
                    RecordState.rev_synthesized,
                ]:
                    continue
                similarity = colrev.record.record.Record.get_record_similarity(
                    colrev.record.record.Record(reference_dict),
                    colrev.record.record.Record(local_record_dict),
                )
                if similarity > max_similarity:
                    max_similarity_record = local_record_dict
                    max_similarity = similarity
            if max_similarity_record and reference_dict.get(Fields.TEI_ID):
                record_ids_by_tei_id[reference_dict[Fields.TEI_ID]] = (
                    max_similarity_record[Fields.ID]
                )

        self.document.annotate_reference_ids(record_ids_by_tei_id)
        if self.tei_path is not None:
            self.tei_path.write_bytes(self.document.to_bytes())
        return self.root


def _add_doi_from_pdf_if_not_available(record_dict: dict) -> None:
    try:
        record = colrev.record.record_pdf.PDFRecord(
            record_dict, path=Path("")  # self.review_manager.path
        )
        if Fields.DOI not in record_dict:
            record.set_text_from_pdf(first_pages=True)
            result = re.findall(FieldsRegex.DOI, record.data[Fields.TEXT_FROM_PDF])
            if result:
                record.data[Fields.DOI] = result[0].upper()
        record.data.pop(Fields.TEXT_FROM_PDF, None)
        record.data.pop(Fields.NR_PAGES_IN_FILE, None)
    except colrev_exceptions.InvalidPDFException as exc:
        print(exc)


def get_record_from_pdf(file_path: Path, *, add_doi_from_pdf: bool = False) -> dict:
    """Get a ColRev record dictionary from a PDF file."""
    if file_path.suffix != ".pdf":
        raise ValueError

    record_dict: typing.Dict[str, typing.Any] = {
        Fields.FILE: str(file_path),
        Fields.ENTRYTYPE: ENTRYTYPES.MISC,
    }

    try:
        tei = TEIParser(pdf_path=file_path)
    except (FileNotFoundError, colrev_exceptions.TEITimeoutException):
        return record_dict

    for key, value in tei.get_metadata().items():
        if value:
            record_dict[key] = str(value)
    if Fields.DOI in record_dict:
        record_dict[Fields.DOI] = record_dict[Fields.DOI].upper()

    record_dict[Fields.GROBID_VERSION] = "lfoppiano/grobid:" + tei.get_grobid_version()
    if add_doi_from_pdf:
        _add_doi_from_pdf_if_not_available(record_dict)

    return record_dict
