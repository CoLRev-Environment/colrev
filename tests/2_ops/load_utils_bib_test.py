#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils
import colrev.ops.load_utils_bib
import colrev.review_manager
import colrev.settings


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""
    os.chdir(tmp_path)

    Path("non-bib-file.bib").write_text("This is not a bib file.")
    with pytest.raises(colrev_exceptions.UnsupportedImportFormatError):
        colrev.ops.load_utils.load(
            filename=Path("non-bib-file.bib"),
        )

    # only supports bib
    with pytest.raises(colrev_exceptions.ImportException):
        colrev.ops.load_utils.load(
            filename=Path("table.ptvc"),
        )

    # file must exist
    with pytest.raises(colrev_exceptions.ImportException):
        colrev.ops.load_utils.load(
            filename=Path("non-existent.bib"),
        )

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("bib_tests.bib"),
        target=Path("data/search/") / Path("bib_tests.bib"),
    )

    records = colrev.ops.load_utils.load(
        filename=Path("data/search/bib_tests.bib"),
    )

    assert records == {
        "articlewriter_firstrandomword_2020": {
            "ID": "articlewriter_firstrandomword_2020",
            "ENTRYTYPE": "article",
            "doi": "10.3333/XYZ.V4444.04",
            "journal": "Dummy Relations",
            "title": "This is a dummy title",
            "year": "2020",
            "volume": "99",
            "number": "299",
            "pages": "99--123",
            "abstract": "This is a nice abstract.",
            "issn": "07654321",
            "keywords": "Dummy, Template, Void, Example",
            "language": "German",
            "month": "April",
            "url": "https://www.proquest.com/abc/def",
            "author": "Articlewriter, Laura, III",
        },
        "articlewriter_firstrandomword_2020a": {
            "ENTRYTYPE": "article",
            "ID": "articlewriter_firstrandomword_2020a",
            "abstract": "This is a nice abstract.",
            "author": "Articlewriter, Laura",
            "doi": "10.3333/XYZ.V4444.04",
            "issn": "07654321",
            "journal": "Dummy Relations",
            "key_words": "Dummy, Template, Void, Example",
            "language": "German",
            "month": "April",
            "number": "299",
            "pages": "99--123",
            "title": "This is a dummy title",
            "url": "https://www.proquest.com/abc/def",
            "volume": "99",
            "year": "2020",
        },
        "mouse_2015": {
            "ID": "mouse_2015",
            "ENTRYTYPE": "inproceedings",
            "title": "Mouse stories",
            "author": "Mouse, M.",
            "booktitle": "Proceedings of the 34th International Cosmic Ray Conference",
            "year": "2015",
        },
        "mouse2016": {
            "ENTRYTYPE": "inproceedings",
            "ID": "mouse2016",
            "author": "Mouse, M.",
            "crossref": "ICRC2016",
            "title": "Mouse stories two",
        },
    }
