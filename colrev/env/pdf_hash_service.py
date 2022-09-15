#! /usr/bin/env python
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import colrev.exceptions as colrev_exceptions


class PDFHashService:
    # pylint: disable=too-few-public-methods
    def __init__(self):
        pass

    def get_pdf_hash(self, *, pdf_path: Path, page_nr: int, hash_size: int = 32) -> str:

        assert isinstance(page_nr, int)
        assert isinstance(hash_size, int)

        pdf_path = pdf_path.resolve()
        pdf_dir = pdf_path.parents[0]

        command = (
            f'docker run --rm -v "{pdf_dir}:/home/docker" '
            f'pdf_hash python app.py "{pdf_path.name}" {page_nr} {hash_size}'
        )

        try:
            ret = subprocess.check_output(
                [command], stderr=subprocess.STDOUT, shell=True
            )
        except subprocess.CalledProcessError as exc:

            if 0 == os.path.getsize(pdf_path):
                print(f"PDF with size 0: {pdf_path}")

            raise colrev_exceptions.InvalidPDFException(path=pdf_path) from exc

        # TODO : raise exception if errors occur

        return ret.decode("utf-8").replace("\n", "")


if __name__ == "__main__":
    pass
