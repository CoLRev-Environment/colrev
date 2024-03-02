#! /usr/bin/env python
"""Creates CoLRev PDF hashes."""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import fitz
import imagehash
from PIL import Image

import colrev.exceptions as colrev_exceptions
from colrev.constants import Colors

# pylint: disable=duplicate-code


def create_colrev_pdf_id(*, pdf_path: Path, cpid_version: str = "cpid2") -> str:
    """Get the PDF hash"""

    if cpid_version == "cpid2":
        hash_size = 32
        pdf_path = pdf_path.resolve()
        if 0 == os.path.getsize(pdf_path):
            logging.error("%sPDF with size 0: %s %s", Colors.RED, pdf_path, Colors.END)
            raise colrev_exceptions.InvalidPDFException(path=pdf_path)

        try:
            doc: fitz.Document = fitz.open(pdf_path)
        except fitz.fitz.FileDataError as exc:
            raise colrev_exceptions.InvalidPDFException(path=pdf_path) from exc

        img = None
        with tempfile.NamedTemporaryFile(suffix=".png") as temp_file:
            file_name = temp_file.name
        page_no = 0
        try:
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                pix.save(file_name)  # store image as a PNG
                page_no += 1
                if page_no == 1:
                    img = Image.open(file_name)
                    break
        except RuntimeError as exc:
            Path(file_name).unlink(missing_ok=True)
            raise colrev_exceptions.PDFHashError(path=pdf_path) from exc
        average_hash = imagehash.average_hash(img, hash_size=int(hash_size))
        Path(file_name).unlink()
        average_hash_str = str(average_hash).replace("\n", "")
        if len(average_hash_str) * "0" == average_hash_str:
            raise colrev_exceptions.PDFHashError(path=pdf_path)

        return "cpid2:" + average_hash_str

    raise NotImplementedError
