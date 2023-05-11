#!/usr/bin/env python
"""Test the exclude_languages prep package"""
from pathlib import Path

import pytest
import requests_mock

import colrev.ops.built_in.search_sources.crossref
import colrev.ops.prep


# pylint: disable=line-too-long


@pytest.fixture(scope="package", name="crossref_prep")
def fixture_crossref_prep(
    prep_operation: colrev.ops.prep.Prep,
) -> colrev.ops.built_in.search_sources.crossref.CrossrefSearchSource:
    """Fixture for crossref prep"""
    settings = {
        "endpoint": "colrev.get_masterdata_from_crossref",
        "filename": Path("data/search/md_crossref.bib"),
        "search_type": colrev.settings.SearchType.DB,
        "search_parameters": {},
        "load_conversion_package_endpoint": {"endpoint": "colrev.bibtex"},
        "comment": "",
    }
    instance = colrev.ops.built_in.search_sources.crossref.CrossrefSearchSource(
        source_operation=prep_operation, settings=settings
    )
    return instance


def test_crossref_query(
    crossref_prep: colrev.ops.built_in.search_sources.crossref.CrossrefSearchSource,
) -> None:
    """Test the crossref query_doi()"""
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            "https://api.crossref.org/works/10.17705/1cais.04607",
            content=rb'{"status":"ok","message-type":"work","message-version":"1.0.0","message":{"indexed":{"date-parts":[[2023,4,21]],"date-time":"2023-04-21T17:18:18Z","timestamp":1682097498127},"reference-count":0,"publisher":"Association for Information Systems","issue":"1","content-domain":{"domain":[],"crossmark-restriction":false},"short-container-title":["CAIS"],"DOI":"10.17705\/1cais.04607","type":"journal-article","created":{"date-parts":[[2020,2,11]],"date-time":"2020-02-11T19:25:35Z","timestamp":1581449135000},"page":"134-186","source":"Crossref","is-referenced-by-count":10,"title":["A Knowledge Development Perspective on Literature Reviews: Validation of a new Typology in the IS Field"],"prefix":"10.17705","volume":"49","author":[{"given":"Guido","family":"Schryen","sequence":"first","affiliation":[]},{"name":"Paderborn University","sequence":"first","affiliation":[]},{"given":"Gerit","family":"Wagner","sequence":"additional","affiliation":[]},{"given":"Alexander","family":"Benlian","sequence":"additional","affiliation":[]},{"given":"Guy","family":"Par\u00e9","sequence":"additional","affiliation":[]},{"name":"University of Regensburg","sequence":"additional","affiliation":[]},{"name":"University of Technology Darmstadt","sequence":"additional","affiliation":[]},{"name":"HEC Montr\u00e9al","sequence":"additional","affiliation":[]}],"member":"7521","published-online":{"date-parts":[[2021]]},"container-title":["Communications of the Association for Information Systems"],"original-title":[],"link":[{"URL":"https:\/\/aisel.aisnet.org\/cgi\/viewcontent.cgi?article=4184&context=cais","content-type":"unspecified","content-version":"vor","intended-application":"similarity-checking"}],"deposited":{"date-parts":[[2022,1,7]],"date-time":"2022-01-07T16:22:32Z","timestamp":1641572552000},"score":1,"resource":{"primary":{"URL":"https:\/\/aisel.aisnet.org\/cais\/vol46\/iss1\/7\/"}},"subtitle":[],"short-title":[],"issued":{"date-parts":[[2021]]},"references-count":0,"journal-issue":{"issue":"1","published-online":{"date-parts":[[2021]]}},"URL":"http:\/\/dx.doi.org\/10.17705\/1cais.04607","relation":{},"ISSN":["1529-3181"],"issn-type":[{"value":"1529-3181","type":"electronic"}],"subject":["Information Systems"],"published":{"date-parts":[[2021]]}}}',  # noqa: E501
        )

        actual = crossref_prep.query_doi(doi="10.17705/1cais.04607")
        expected = colrev.record.PrepRecord(
            data={
                "doi": "10.17705/1CAIS.04607",
                "ENTRYTYPE": "article",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: Validation of a new Typology in the IS Field",  # noqa: E501
                "journal": "Communications of the Association for Information Systems",
                "volume": "49",
                "year": "2021",
                "number": "1",
                "pages": "134--186",
            }
        )

        assert actual.data == expected.data
