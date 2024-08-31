#!/usr/bin/env python
"""Test the crossref SearchSource"""
from pathlib import Path

import pytest
import requests_mock

import colrev.ops.prep
import colrev.packages.crossref.src.crossref_search_source
from colrev.packages.crossref.src import crossref_api

# pylint: disable=line-too-long


@pytest.mark.parametrize(
    "doi, expected_dict",
    [
        (
            "10.2196/22081",
            {
                "doi": "10.2196/22081",
                "ENTRYTYPE": "article",
                "author": "Grenier Ouimet, Antoine and Wagner, Gerit and Raymond, Louis and "
                "Pare, Guy",
                "journal": "Journal of Medical Internet Research",
                "language": "en",
                "number": "11",
                "pages": "e22081",
                "title": "Investigating Patients’ Intention to Continue Using "
                "Teleconsultation to Anticipate Postcrisis Momentum: Survey Study",
                "abstract": "Background The COVID-19 crisis has drastically changed care "
                "delivery with teleconsultation platforms experiencing "
                "substantial spikes in demand, helping patients and care "
                "providers avoid infections and maintain health care services. "
                "Beyond the current pandemic, teleconsultation is considered a "
                "significant opportunity to address persistent health system "
                "challenges, including accessibility, continuity, and cost of "
                "care, while ensuring quality. Objective This study aims at "
                "identifying the determinants of patients’ intention to continue "
                "using a teleconsultation platform. It extends prior research on "
                "information technology use continuance intention and "
                "teleconsultation services. Methods Data was collected in "
                "November 2018 and May 2019 with Canadian patients who had access "
                "to a teleconsultation platform. Measures included patients’ "
                "intention to continue their use; teleconsultation usefulness; "
                "teleconsultation quality; patients’ trust toward the digital "
                "platform, its provider. and health care professionals; and "
                "confirmation of patients’ expectations toward teleconsultation. "
                "We used structural equation modeling employing the partial least "
                "squares component-based technique to test our research model and "
                "hypotheses. Results We analyzed a sample of 178 participants who "
                "had used teleconsultation services. Our findings revealed that "
                "confirmation of expectations had the greatest influence on "
                "continuance intention (total effects=0.722; P<.001), followed by "
                "usefulness (total effects=0.587; P<.001) and quality (total "
                "effects=0.511; P<.001). Usefulness (β=.60; P<.001) and quality "
                "(β=.34; P=.01) had direct effects on the dependent variable. The "
                "confirmation of expectations had direct effects both on "
                "usefulness (β=.56; P<.001) and quality (β=.75; P<.001) in "
                "addition to having an indirect effect on usefulness (indirect "
                "effects=0.282; P<.001). Last, quality directly influenced "
                "usefulness (β=.34; P=.002) and trust (β=.88; P<.001). Trust does "
                "not play a role in the context under study. Conclusions "
                "Teleconsultation is central to care going forward, and it "
                "represents a significant lever for an improved, digital delivery "
                "of health care in the future. We believe that our findings will "
                "help drive long-term teleconsultation adoption and use, "
                "including in the aftermath of the current COVID-19 crisis, so "
                "that general care improvement and greater preparedness for "
                "exceptional situations can be achieved.",
                "volume": "22",
                "year": "2020",
            },
        ),
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
) -> None:
    """Test the crossref query_doi()"""

    api = crossref_api.CrossrefAPI(params={})

    # replace the / in filenames by _
    filename = Path(__file__).parent / f"data/{doi.replace('/', '_')}.json"
    with open(filename, encoding="utf-8") as file:
        json_str = file.read()

    with requests_mock.Mocker() as req_mock:
        req_mock.get(
            f"https://api.crossref.org/works/{doi}", content=json_str.encode("utf-8")
        )

        actual = api.query_doi(doi=doi)
        expected = colrev.record.record_prep.PrepRecord(expected_dict)

        assert actual.data == expected.data
