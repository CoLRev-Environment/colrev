#! /usr/bin/env python
"""Functionality for PDF handling."""
from __future__ import annotations

import logging
import os
import tempfile
import typing
from pathlib import Path

import imagehash
import pymupdf
from PIL import Image

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Colors
from colrev.constants import Fields


class PDFRecord(colrev.record.record.Record):
    """The PDFRecord class provides a range of convenience functions for PDF handling"""

    def extract_text_by_page(
        self,
        *,
        pages: typing.Optional[list] = None,
    ) -> str:
        """Extract the text from the PDF for a given number of pages"""
        text_list: list = []
        pdf_path = Path(self.data[Fields.FILE]).absolute()

        with pymupdf.open(pdf_path) as doc:
            for i, page in enumerate(doc):
                if pages is None or i in pages:
                    text = page.get_text()
                    text_list.append(text)

        text_all = "".join(text_list)
        text_all = (
            text_all.replace("´\ne", "é").replace("ˆ\no", "ô").replace("´\na", "á")
        )
        # does not work with newlines?!
        # text_list = unicodedata.normalize('NFKD', text_all)

        return text_all

    def set_nr_pages_in_pdf(self) -> None:
        """Set the pages_in_file field based on the PDF"""
        pdf_path = Path(self.data[Fields.FILE]).absolute()
        # try:
        with pymupdf.open(pdf_path) as doc:
            pages_in_file = doc.page_count
        self.data[Fields.NR_PAGES_IN_FILE] = pages_in_file
        # except PDFSyntaxError:  # pragma: no cover
        #     self.data.pop(Fields.NR_PAGES_IN_FILE, None)

    def set_text_from_pdf(self) -> None:
        """Set the text_from_pdf field based on the PDF"""
        self.data[Fields.TEXT_FROM_PDF] = ""
        # try:
        self.set_nr_pages_in_pdf()
        text = self.extract_text_by_page(pages=[0, 1, 2])
        text_from_pdf = text.replace("\n", " ").replace("\x0c", "")
        self.data[Fields.TEXT_FROM_PDF] = text_from_pdf

        # TODO : errors from pdfminer (replaced by pymupdf)
        # except PDFSyntaxError:  # pragma: no cover
        #     self.add_field_provenance_note(key=Fields.FILE, note="pdf_reader_error")
        #     # pylint: disable=colrev-direct-status-assign
        #     self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
        # except PDFTextExtractionNotAllowed:  # pragma: no cover
        #     self.add_field_provenance_note(key=Fields.FILE, note="pdf_protected")
        #     # pylint: disable=colrev-direct-status-assign
        #     self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)

    @classmethod
    def extract_pages_from_pdf(
        cls,
        *,
        pages: list,
        pdf_path: Path,
        save_to_path: typing.Optional[Path] = None,
    ) -> None:  # pragma: no cover
        """Extract pages from the PDF"""
        doc = pymupdf.Document(pdf_path)
        all_pages_list = list(range(doc.page_count))

        saved_pdf_pages = []

        for page in pages:
            all_pages_list.remove(page)
            saved_pdf_pages.append(page)

        doc.select(all_pages_list)
        doc.save(pdf_path)
        doc.close()

        if save_to_path:
            doc = pymupdf.Document(pdf_path)
            doc.select(saved_pdf_pages)
            doc.save(save_to_path / Path(pdf_path).name)
            doc.close()

    def extract_pages(
        self,
        *,
        pages: list,
        project_path: Path,
        save_to_path: typing.Optional[Path] = None,
    ) -> None:  # pragma: no cover
        """Extract pages from the PDF"""
        pdf_path = project_path / Path(self.data[Fields.FILE])
        self.extract_pages_from_pdf(
            pages=pages, pdf_path=pdf_path, save_to_path=save_to_path
        )

    def get_pdf_hash(self, *, page_nr: int, hash_size: int = 32) -> str:
        """Get the PDF image hash"""
        assert page_nr > 0
        assert hash_size in [16, 32]

        if Fields.FILE not in self.data or not Path(self.data[Fields.FILE]).is_file():
            raise colrev_exceptions.InvalidPDFException(path=self.data[Fields.ID])

        pdf_path = Path(self.data[Fields.FILE]).resolve()
        if 0 == os.path.getsize(pdf_path):
            logging.error("%sPDF with size 0: %s %s", Colors.RED, pdf_path, Colors.END)
            raise colrev_exceptions.InvalidPDFException(path=pdf_path)

        with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
            file_name = temp_file.name
            try:
                doc: pymupdf.Document = pymupdf.open(pdf_path)
                # Starting with page 1
                for page_no, page in enumerate(doc, 1):
                    if page_no == page_nr:
                        pix = page.get_pixmap(dpi=200)
                        pix.save(file_name)  # store image as a PNG
                        with Image.open(file_name) as img:
                            average_hash = imagehash.average_hash(
                                img, hash_size=hash_size
                            )
                            average_hash_str = str(average_hash).replace("\n", "")
                            if len(average_hash_str) * "0" == average_hash_str:
                                raise colrev_exceptions.PDFHashError(path=pdf_path)
                            return average_hash_str
                # Page not found
                raise colrev_exceptions.PDFHashError(path=pdf_path)  # pragma: no cover
            except pymupdf.FileDataError as exc:
                raise colrev_exceptions.InvalidPDFException(path=pdf_path) from exc
            except RuntimeError as exc:
                raise colrev_exceptions.PDFHashError(path=pdf_path) from exc
