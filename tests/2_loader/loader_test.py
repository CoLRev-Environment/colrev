#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import logging
import os
from pathlib import Path

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.loader.load_utils
import colrev.review_manager
import colrev.settings


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""
    os.chdir(tmp_path)

    with pytest.raises(colrev_exceptions.ImportException):
        colrev.loader.load_utils.load(
            filename=Path("data/search/bib_data.bib"),
            logger=logging.getLogger(__name__),
        )
    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_tests.xy"),
    )
    with pytest.raises(NotImplementedError):
        colrev.loader.load_utils.load(
            filename=Path("data/search/bib_tests.xy"),
            logger=logging.getLogger(__name__),
        )

    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_data.bib"),
    )

    colrev.loader.load_utils.load(
        filename=Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    with pytest.raises(NotImplementedError):
        colrev.loader.load_utils.loads(load_string="content...", implementation="xy")
