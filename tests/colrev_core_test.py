#!/usr/bin/env python
"""Tests for `colrev_core` package."""
import bibtexparser
import pandas as pd
import pytest
from click.testing import CliRunner

from colrev_core import cli


@pytest.fixture
def response():
    """Sample pytest fixture.

    See more at: http://doc.pytest.org/en/latest/fixture.html
    """
    # import requests
    # return requests.get('https://github.com/audreyr/cookiecutter-pypackage')


def test_content(response):
    """Sample pytest test function with the pytest fixture as an argument."""
    # from bs4 import BeautifulSoup
    # assert 'GitHub' in BeautifulSoup(response.content).title.string


def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "colrev_core.cli.main" in result.output
    help_result = runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert "--help  Show this message and exit." in help_result.output


def test_merge():
    from colrev_core import process_duplicates

    bibtex_str = """@article{Appan2012,
                    author    = {Appan, and Browne,},
                    journal   = {MIS Quarterly},
                    title     = {The Impact of Analyst-Induced Misinformation},
                    year      = {2012},
                    number    = {1},
                    pages     = {85},
                    volume    = {36},
                    doi       = {10.2307/41410407},
                    hash_id   = {300a3700f5440cb37f39b05c866dc0a33cefb78de93c},
                    }

                    @article{Appan2012a,
                    author    = {Appan, Radha and Browne, Glenn J.},
                    journal   = {MIS Quarterly},
                    title     = {The Impact of Analyst-Induced Misinformation},
                    year      = {2012},
                    number    = {1},
                    pages     = {22},
                    volume    = {36},
                    doi       = {10.2307/41410407},
                    hash_id   = {427967442a90d7f27187e66fd5b66fa94ab2d5da1bf9},
                    }"""

    bib_database = bibtexparser.loads(bibtex_str)
    entry_a = bib_database.entries[0]
    entry_b = bib_database.entries[1]
    df_a = pd.DataFrame.from_dict([entry_a])
    df_b = pd.DataFrame.from_dict([entry_b])

    print(process_duplicates.get_similarity(df_a.iloc[0], df_b.iloc[0]))

    return
