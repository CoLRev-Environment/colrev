#! /usr/bin/env python
"""Functionality for PDF handling."""
from __future__ import annotations

import io
import logging
import os
import tempfile
import typing
from pathlib import Path

import fitz
import imagehash
import pdfminer
from pdfminer.converter import TextConverter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfparser import PDFSyntaxError
from PIL import Image
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Colors
from colrev.constants import Fields
from colrev.constants import RecordState


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

        # https://stackoverflow.com/questions/49457443/python-pdfminer-converts-pdf-file-into-one-chunk-of-string-with-no-spaces-betwee
        laparams = pdfminer.layout.LAParams()
        setattr(laparams, "all_texts", True)

        with open(pdf_path, "rb") as pdf_file:
            try:
                for page in PDFPage.get_pages(
                    pdf_file,
                    pagenos=pages,  # note: maybe skip potential cover pages?
                    caching=True,
                    check_extractable=True,
                ):
                    resource_manager = PDFResourceManager()
                    fake_file_handle = io.StringIO()
                    converter = TextConverter(
                        resource_manager, fake_file_handle, laparams=laparams
                    )
                    page_interpreter = PDFPageInterpreter(resource_manager, converter)
                    page_interpreter.process_page(page)

                    text = fake_file_handle.getvalue()
                    text_list += text

                    # close open handles
                    converter.close()
                    fake_file_handle.close()
            except (
                TypeError,
                KeyError,
                PDFSyntaxError,
            ):  # pragma: no cover
                pass
        return "".join(text_list)

    def set_nr_pages_in_pdf(self) -> None:
        """Set the pages_in_file field based on the PDF"""
        pdf_path = Path(self.data[Fields.FILE]).absolute()
        try:
            with open(pdf_path, "rb") as file:
                parser = PDFParser(file)
                document = PDFDocument(parser)
                pages_in_file = resolve1(document.catalog["Pages"])["Count"]
            self.data[Fields.NR_PAGES_IN_FILE] = pages_in_file
        except PDFSyntaxError:  # pragma: no cover
            self.data.pop(Fields.NR_PAGES_IN_FILE, None)

    def set_text_from_pdf(self) -> None:
        """Set the text_from_pdf field based on the PDF"""
        self.data[Fields.TEXT_FROM_PDF] = ""
        try:
            self.set_nr_pages_in_pdf()
            text = self.extract_text_by_page(pages=[0, 1, 2])
            text_from_pdf = text.replace("\n", " ").replace("\x0c", "")
            self.data[Fields.TEXT_FROM_PDF] = text_from_pdf

        except PDFSyntaxError:  # pragma: no cover
            self.add_field_provenance_note(key=Fields.FILE, note="pdf_reader_error")
            # pylint: disable=colrev-direct-status-assign
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
        except PDFTextExtractionNotAllowed:  # pragma: no cover
            self.add_field_provenance_note(key=Fields.FILE, note="pdf_protected")
            # pylint: disable=colrev-direct-status-assign
            self.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)

    def extract_pages(
        self,
        *,
        pages: list,
        project_path: Path,
        save_to_path: typing.Optional[Path] = None,
    ) -> None:  # pragma: no cover
        """Extract pages from the PDF (saveing them to the save_to_path)"""
        pdf_path = project_path / Path(self.data[Fields.FILE])
        pdf_reader = PdfFileReader(str(pdf_path), strict=False)
        writer = PdfFileWriter()
        for i in range(0, len(pdf_reader.pages)):
            if i in pages:
                continue
            writer.addPage(pdf_reader.getPage(i))
        with open(pdf_path, "wb") as outfile:
            writer.write(outfile)

        if save_to_path:
            writer_cp = PdfFileWriter()
            for page in pages:
                writer_cp.addPage(pdf_reader.getPage(page))
            filepath = Path(pdf_path)
            with open(save_to_path / filepath.name, "wb") as outfile:
                writer_cp.write(outfile)

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
                doc: fitz.Document = fitz.open(pdf_path)
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
            except fitz.fitz.FileDataError as exc:
                raise colrev_exceptions.InvalidPDFException(path=pdf_path) from exc
            except RuntimeError as exc:
                raise colrev_exceptions.PDFHashError(path=pdf_path) from exc
