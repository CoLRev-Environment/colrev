#! /usr/bin/env python
from __future__ import annotations

import subprocess
from pathlib import Path


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
        ret = subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

        # TODO : raise exception if errors occur

        return ret.decode("utf-8").replace("\n", "")


if __name__ == "__main__":
    pass
