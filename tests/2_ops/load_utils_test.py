#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import logging
import os
from pathlib import Path

import colrev.ops.load_utils
import colrev.review_manager
import colrev.settings


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""
    os.chdir(tmp_path)

    helpers.retrieve_test_file(
        source=Path("load_utils/") / Path("bib_tests.bib"),
        target=Path("data/search/") / Path("bib_tests.bib"),
    )

    records = colrev.ops.load_utils.load(
        filename=Path("data/search/bib_tests.bib"), logger=logging.getLogger(__name__)
    )
    print(records)
    # raise Exception
