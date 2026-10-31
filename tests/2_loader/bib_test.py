#!/usr/bin/env python
"""Tests of the load utils for bib files"""

import logging
import os
from pathlib import Path

import pytest
from bibliography_io import get_nr_records
from bibliography_io import load_raw
from bibliography_io.exceptions import ParseError
from bibliography_io.exceptions import UnsupportedFormatError

import colrev.loader.load_utils_formatter

# flake8: noqa


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test direct bibliography-io BibTeX loading and CoLRev fix helpers."""
    os.chdir(tmp_path)

    Path("non-bib-file.bib").write_text("This is not a bib file.")
    with pytest.raises(ParseError):
        load_raw(Path("non-bib-file.bib"))

    # only supports bib
    with pytest.raises(UnsupportedFormatError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/bib_tests.xy").touch()
        try:
            load_raw(Path("data/search/bib_tests.xy"))
        finally:
            Path("data/search/bib_tests.xy").unlink()

    # file must exist
    with pytest.raises(FileNotFoundError):
        load_raw(Path("non-existent.bib"))

    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_data.bib"),
    )

    colrev.loader.load_utils_formatter.run_fix_bib_file(
        Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    records_list = load_raw(Path("data/search/bib_data.bib"))
    records = {record["ID"]: record for record in records_list}
    colrev.loader.load_utils_formatter.run_resolve_crossref(
        records, logger=logging.getLogger(__name__)
    )

    print(records)
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
            "abstract": "This is a nice \n   abstract.",
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
            "doi": "10.3333/XYZ.V4444.04a",
            "issn": "07654321a",
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
            "title": "Mouse stories two",
            "crossref": "ICRC2016",
        },
        "WOS:000072095400011": {
            "ID": "WOS:000072095400011",
            "ENTRYTYPE": "article",
            "author": "Andreica, D and\n   Schmid, H",
            "title": "Magnetic properties and phase transitions of iron boracites,\n   Fe3B7O13X (X = Cl, Br OR I)",
            "journal": "FERROELECTRICS",
            "year": "1997",
        },
    }

    nr_records = get_nr_records(Path("data/search/bib_data.bib"))
    assert 6 == nr_records

    # A missing file has no records.
    nr_records = get_nr_records(Path("data/search/bib_data2.bib"))
    assert 0 == nr_records

    Path("data/search/bib_data2.unkonwn").write_text("This is not a bib file.")
    with pytest.raises(UnsupportedFormatError):
        get_nr_records(Path("data/search/bib_data2.unkonwn"))
