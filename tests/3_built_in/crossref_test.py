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


@pytest.mark.parametrize(
    "doi, expected_dict",
    [
        (
            "10.17705/1cais.04607",
            {
                "doi": "10.17705/1CAIS.04607",
                "ENTRYTYPE": "article",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: Validation of a new Typology in the IS Field",  # noqa: E501
                "journal": "Communications of the Association for Information Systems",
                "volume": "49",
                "year": "2021",
                "number": "1",
                "pages": "134--186",
            },
        ),
        (
            "10.1177/02683962211048201",
            {
                "doi": "10.1177/02683962211048201",
                "ENTRYTYPE": "article",
                "abstract": "Artificial intelligence (AI) is beginning to transform traditional "
                + "research practices in many areas. In this context, literature "
                + "reviews stand out because they operate on large and rapidly "
                + "growing volumes of documents, that is, partially structured "
                + "(meta)data, and pervade almost every type of paper published in "
                + "information systems research or related social science "
                + "disciplines. To familiarize researchers with some of the recent "
                + "trends in this area, we outline how AI can expedite individual "
                + "steps of the literature review process. Considering that the use "
                + "of AI in this context is in an early stage of development, we "
                + "propose a comprehensive research agenda for AI-based literature "
                + "reviews (AILRs) in our field. With this agenda, we would like to "
                + "encourage design science research and a broader constructive "
                + "discourse on shaping the future of AILRs in research.",
                "author": "Wagner, Gerit and Lukyanenko, Roman and Paré, Guy",
                "doi": "10.1177/02683962211048201",
                "fulltext": "http://journals.sagepub.com/doi/pdf/10.1177/02683962211048201",
                "journal": "Journal of Information Technology",
                "language": "en",
                "number": "2",
                "pages": "209--226",
                "title": "Artificial intelligence and the conduct of literature reviews",
                "volume": "37",
                "year": "2022",
            },
        ),
    ],
)
def test_crossref_query(  # type: ignore
    doi: str,
    expected_dict: dict,
    crossref_prep: colrev.ops.built_in.search_sources.crossref.CrossrefSearchSource,
    helpers,
) -> None:
    """Test the crossref query_doi()"""
    # note: replace the / in filenames by _
    json_str = helpers.retrieve_test_file_content(
        source=Path(f"api_output/crossref/{doi.replace('/', '_')}.json")
    )
    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"https://api.crossref.org/works/{doi}", content=json_str.encode("utf-8")
        )

        actual = crossref_prep.query_doi(doi=doi)
        expected = colrev.record.PrepRecord(data=expected_dict)

        assert actual.data == expected.data
