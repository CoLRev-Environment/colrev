#! /usr/bin/env python
"""Creates CoLRev PDF hashes."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import fitz
import imagehash
from PIL import Image

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


class PDFHashService:
    """The PDFHashService calculates hashes to identify PDFs (based on image/layout)"""

    # pylint: disable=too-few-public-methods
    def __init__(self, *, logger: logging.Logger) -> None:
        # self.pdf_hash_image = "colrev/pdf_hash:latest"
        # colrev.env.environment_manager.EnvironmentManager.build_docker_image(
        #     imagename=self.pdf_hash_image
        # )
        self.logger = logger

    def get_pdf_hash(self, *, pdf_path: Path, page_nr: int, hash_size: int = 32) -> str:
        """Get the PDF hash"""

        assert page_nr > 0
        assert hash_size in [16, 32]
        pdf_path = pdf_path.resolve()

        if 0 == os.path.getsize(pdf_path):
            self.logger.error(f"{colors.RED}PDF with size 0: {pdf_path}{colors.END}")
            raise colrev_exceptions.InvalidPDFException(path=pdf_path)

        doc: fitz.Document = fitz.open(pdf_path)
        img = get_image(doc, page_nr)
        res = imagehash.average_hash(img, hash_size=int(hash_size))
        as_str = str(res).replace("\n", "")
        if len(as_str) * "0" == as_str:
            raise colrev_exceptions.PDFHashError(path=pdf_path)
        return as_str


def get_image(doc, page_nr):
    file_name = f"page-{page_nr}.png"
    with tempfile.TemporaryDirectory() as tp:
        page_no = 0
        for page in doc:
            pix = page.get_pixmap(dpi=200)
            pix.save(file_name)  # store image as a PNG
            page_no += 1
            if page_no == page_nr:
                return Image.open(file_name)


if __name__ == "__main__":
    pass
