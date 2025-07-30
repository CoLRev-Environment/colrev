#!/usr/bin/env python
"""Tests of the load utils for bib files"""
import logging
import os
from pathlib import Path

import pytest

import colrev.loader.load_utils


def test_load(tmp_path, helpers) -> None:  # type: ignore
    """Test the load utils for bib files"""
    os.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        colrev.loader.load_utils.load(
            filename=Path("data/search/bib_data.bib"),
            logger=logging.getLogger(__name__),
            empty_if_file_not_exists=False,
        )
    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_tests.xy"),
    )
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

    helpers.retrieve_test_file(
        source=Path("2_loader/data/bib_data.bib"),
        target=Path("data/search/bib_data.bib"),
    )

    colrev.loader.bib.run_fix_bib_file(
        Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    colrev.loader.load_utils.load(
        filename=Path("data/search/bib_data.bib"), logger=logging.getLogger(__name__)
    )

    with pytest.raises(NotImplementedError):
        colrev.loader.load_utils.loads(load_string="content...", implementation="xy")
