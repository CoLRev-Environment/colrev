#! /usr/bin/env python
"""Creates CoLRev PDF hashes."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import colrev.exceptions as colrev_exceptions
import colrev.ui_cli.cli_colors as colors

if TYPE_CHECKING:
    import colrev.review_manager


class PDFHashService:
    """The PDFHashService calculates hashes to identify PDFs (based on image/layout)"""

    # pylint: disable=too-few-public-methods
    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.pdf_hash_image = "colrev/pdf_hash:latest"
        review_manager.environment_manager.build_docker_image(
            imagename=self.pdf_hash_image
        )
        self.review_manager = review_manager

    def get_pdf_hash(self, *, pdf_path: Path, page_nr: int, hash_size: int = 32) -> str:
        """Get the PDF hash"""

        assert isinstance(page_nr, int)
        assert isinstance(hash_size, int)

        pdf_path = pdf_path.resolve()
        pdf_dir = pdf_path.parents[0]

        if 0 == os.path.getsize(pdf_path):
            self.review_manager.logger.error(
                f"{colors.RED}PDF with size 0: {pdf_path}{colors.END}"
            )
            raise colrev_exceptions.InvalidPDFException(path=pdf_path)

        command = (
            f'docker run --rm -v "{pdf_dir}:/home/docker" '
            f'{self.pdf_hash_image} python app.py "{pdf_path.name}" {page_nr} {hash_size}'
        )

        try:
            ret = subprocess.check_output(
                [command], stderr=subprocess.STDOUT, shell=True
            )
        except subprocess.CalledProcessError as exc:

            raise colrev_exceptions.PDFHashError(path=pdf_path) from exc

        pdf_hash = ret.decode("utf-8").replace("\n", "")

        # when PDFs are not readable, the pdf-hash may consist of 0s
        if len(pdf_hash) * "0" == pdf_hash:
            raise colrev_exceptions.PDFHashError(path=pdf_path)

        return pdf_hash


if __name__ == "__main__":
    pass
