#!/usr/bin/env python
"""Test the eric SearchSource"""
from pathlib import Path

import pytest
import requests_mock

import colrev.ops.built_in.search_sources.eric
import colrev.ops.prep


# pylint: disable=line-too-long


@pytest.fixture(scope="package", name="eric_search_source")
def fixture_eric_search_source(
    prep_operation: colrev.ops.prep.Prep,
) -> colrev.ops.built_in.search_sources.eric.ERICSearchSource:
    """Fixture for eric SearchSource"""
    settings = {
        "endpoint": "colrev.eric",
        "filename": Path("data/search/eric.bib"),
        "search_type": colrev.settings.SearchType.DB,
        "search_parameters": {"query": "blockchain"},
        "load_conversion_package_endpoint": {"endpoint": "colrev.bibtex"},
        "comment": "",
    }
    instance = colrev.ops.built_in.search_sources.eric.ERICSearchSource(
        source_operation=prep_operation, settings=settings
    )
    return instance


def test_eric(  # type: ignore
    eric_search_source: colrev.ops.built_in.search_sources.eric.ERICSearchSource,
    helpers,
) -> None:
    """Test eric"""

    json_str = helpers.retrieve_test_file_content(
        source=Path("api_output/eric/blockchain.json")
    )
    expected_record = colrev.record.Record(
        data={
            "ENTRYTYPE": "article",
            "ID": "EJ1286736",
            "author": "Çulha, Davut",
            "title": "Competition-Based Learning of Blockchain Programming",
            "year": "2021",
            "subject": "Competition, Teaching Methods, Programming, Technology, Monetary Systems, Foreign Countries, Instructional Effectiveness, Cooperative Learning",
            "peerreviewed": "T",
            "issn": "2618-6586",
            "language": "eng",
            "publisher": "Journal of Educational Technology and Online Learning. Necatibey Faculty of Education, Balikesir University, Balikesir, 10100, Turkey. Web site: dergipark.org.tr/en/pub/jetol",
            "abstract": "Blockchain, which is a disruptive technology, affects many technologies, and it will affect many other technologies. Main property of blockchain technologies is assuring trust without central authorization. This is achieved through immutable data and decentralization. Moreover, blockchain is founded on the principles of cryptography, which provides the required infrastructure for the trust. First application of the blockchain technologies is Bitcoin cryptocurrency. After the birth of Bitcoin, cryptocurrencies began to change financial systems. Learning of blockchain is difficult because blockchain and its related technologies are strange for most of the people. In order to figure out blockchain technologies, the concepts like cryptography, cryptocurrency, immutable data and decentralization should have been understood. Therefore, blockchain and its related technologies should be learned through efficient learning mechanisms. Project-based learning, team-based learning, active learning and competition-based learning can be used for efficient teaching of blockchain. Competition-based learning has been used in many areas successfully for years. Smart contract development is the programming part of blockchain technologies. In this paper, competition-based learning is applied to blockchain programming to increase learning efficiency. In addition, a methodology is presented to apply competition-based learning to blockchain programming.",
        }
    )
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            "https://api.ies.ed.gov/eric/?search=blockchain&format=json&start=0&rows=2000",
            content=json_str.encode("utf-8"),
        )

        for actual_record in eric_search_source.get_query_return():
            assert actual_record == expected_record
