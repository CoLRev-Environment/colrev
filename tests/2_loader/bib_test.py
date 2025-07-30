#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import logging
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.loader.bib
import colrev.loader.load_utils

# flake8: noqa


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""
    os.chdir(tmp_path)

    Path("non-bib-file.bib").write_text("This is not a bib file.")
    with pytest.raises(colrev_exceptions.UnsupportedImportFormatError):
        colrev.loader.load_utils.load(
            filename=Path("non-bib-file.bib"),
        )

    # only supports bib
    with pytest.raises(NotImplementedError):
        os.makedirs("data/search", exist_ok=True)
        Path("data/search/bib_tests.xy").touch()
        try:
            colrev.loader.load_utils.load(
                filename=Path("data/search/bib_tests.xy"),
                logger=logging.getLogger(__name__),
            )
        finally:
            Path("data/search/bib_tests.xy").unlink()

    # file must exist
    with pytest.raises(FileNotFoundError):
        colrev.loader.load_utils.load(
            filename=Path("non-existent.bib"),
            empty_if_file_not_exists=False,
        )

    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_data.bib"),
    )

    colrev.loader.bib.run_fix_bib_file(
        Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    records = colrev.loader.load_utils.load(
        filename=Path("data/search/bib_data.bib"),
    )
    colrev.loader.bib.run_resolve_crossref(records, logger=logging.getLogger(__name__))

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
            "doi": "10.3333/XYZ.V4444.04A",
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
            "Author": "Andreica, D and Schmid, H",
            "Title": "Magnetic properties and phase transitions of iron boracites, Fe3B7O13X (X = Cl, Br OR I)",
            "Journal": "FERROELECTRICS",
            "Year": "1997",
        },
    }

    nr_records = colrev.loader.load_utils.get_nr_records(
        Path("data/search/bib_data.bib")
    )
    assert 6 == nr_records

    # if the file does not (yet) exist
    nr_records = colrev.loader.load_utils.get_nr_records(
        Path("data/search/bib_data2.bib")
    )
    assert 0 == nr_records

    Path("data/search/bib_data2.unkonwn").write_text("This is not a bib file.")
    with pytest.raises(NotImplementedError):
        colrev.loader.load_utils.get_nr_records(Path("data/search/bib_data2.unkonwn"))
