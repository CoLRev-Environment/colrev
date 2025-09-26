#!/usr/bin/env python
"""Test the PLOS SearchSource"""
from pathlib import Path

import pytest
import requests_mock

import colrev.record.record_prep
from colrev.packages.plos.src import plos_api

# flake8: noqa


# pylint: disable=line-too-long
@pytest.mark.parametrize(
    "doi, expected_dict",
    [
        (
            "10.1371/journal.pone.0022081",
            {
                "doi": "10.1371/JOURNAL.PONE.0022081",
                "ENTRYTYPE": "article",
                "author": "Burastero, Samuele E. and Frigerio, Barbara and Lopalco, Lucia and Sironi, Francesca and Breda, Daniela and Longhi, Renato and Scarlatti, Gabriella "
                "and Canevari, Silvana and Figini, Mariangela and Lusso, Paolo",
                "journal": "PLoS ONE",
                "title": "Broad-Spectrum Inhibition of HIV-1 by a Monoclonal Antibody Directed against a gp120-Induced Epitope of CD4",
                "abstract": "To penetrate susceptible cells, HIV-1 sequentially interacts with two highly conserved cellular receptors, CD4 and a chemokine receptor like CCR5 or CXCR4."
                " Monoclonal antibodies (MAbs) directed against such receptors are currently under clinical investigation as potential preventive or therapeutic agents."
                " We immunized Balb/c mice with molecular complexes of the native, trimeric HIV-1 envelope (Env) bound to a soluble form of the human CD4 receptor. Sera from "
                "immunized mice were found to contain gp120-CD4 complex-enhanced antibodies and showed broad-spectrum HIV-1-inhibitory activity. A proportion of MAbs derived "
                "from these mice preferentially recognized complex-enhanced epitopes. In particular, a CD4-specific MAb designated DB81 (IgG1Κ) was found to preferentially bind "
                "to a complex-enhanced epitope on the D2 domain of human CD4. MAb DB81 also recognized chimpanzee CD4, but not baboon or macaque CD4, which exhibit sequence divergence "
                "in the D2 domain. Functionally, MAb DB81 displayed broad HIV-1-inhibitory activity, but it did not exert suppressive effects on T-cell activation in vitro. The variable "
                "regions of the heavy and light chains of MAb DB81 were sequenced. Due to its broad-spectrum anti-HIV-1 activity and lack of immunosuppressive effects, a humanized derivative "
                "of MAb DB81 could provide a useful complement to current preventive or therapeutic strategies against HIV-1.",
                "year": "2011",
                "volume": "6",
                "number": "7",
            },
        ),
        (
            "10.1371/journal.pone.0223215",
            {
                "doi": "10.1371/JOURNAL.PONE.0223215",
                "ENTRYTYPE": "article",
                "author": "Kodaira, Masaki and Sawano, Mitsuaki and Kuno, Toshiki and Numasawa, Yohei and Noma, Shigetaka and Suzuki, Masahiro and Imaeda, Shohei and Ueda, Ikuko and Fukuda, Keiichi and Kohsaka, Shun",
                "journal": "PLOS ONE",
                "title": "Outcomes of acute coronary syndrome patients with concurrent extra-cardiac vascular disease in the era of transradial coronary intervention: A retrospective multicenter cohort study",
                "abstract": "Background: Extra-cardiac vascular diseases (ECVDs), such as cerebrovascular disease (CVD) or peripheral arterial disease (PAD), are frequently observed among patients with acute coronary syndrome (ACS). However, it is not clear how these conditions affect patient outcomes in the era of transradial coronary intervention (TRI). Methods and results: Among 7,980 patients with ACS whose data were extracted from the multicenter Japanese percutaneous coronary intervention (PCI) registry between August 2008 and March 2017, 888 (11.1%) had one concurrent ECVD (either PAD [345 patients: 4.3%] or CVD [543 patients; 6.8%]), while 87 patients (1.1%) had both PAD and CVD. Overall, the presence of ECVD was associated with a higher risk of mortality (odds ratio [OR]: 1.728; 95% confidence interval [CI]: 1.183–2.524) and bleeding complications (OR: 1.430; 95% CI: 1.028–2.004). There was evidence of interaction between ECVD severity and procedural access site on bleeding complication on the additive scale (relative excess risk due to interaction: 0.669, 95% CI: -0.563–1.900) and on the multiplicative scale (OR: 2.105; 95% CI: 1.075–4.122). While the incidence of death among patients with ECVD remained constant during the study period, bleeding complications among patients with ECVD rapidly decreased from 2015 to 2017, in association with the increasing number of TRI. Conclusions: Overall, the presence of ECVD was a risk factor for adverse outcomes after PCI for ACS, both mortality and bleeding complications. In the most recent years, the incidence of bleeding complications among patients with ECVD decreased significantly coinciding with the rapid increase of TRI.",
                "year": "2019",
                "volume": "14",
                "number": "10",
            },
        ),
        (
            "10.1371/journal.pone.0252279",
            {
                "doi": "10.1371/JOURNAL.PONE.0252279",
                "ENTRYTYPE": "article",
                "author": "Doe, John A. and Smith, Jane B. and Johnson, Alan R. and Clark, Sarah T.",
                "journal": "PLOS ONE",
                "title": "The Impact of Socioeconomic Status on Health Outcomes in a Rural Population in the United States",
                "abstract": "This study investigates the influence of socioeconomic status (SES) on health outcomes in "
                "rural populations in the United States. The data collected over a five-year period was analyzed to understand "
                "the correlation between SES and common health issues like hypertension, diabetes, and cardiovascular diseases. "
                "Our results indicate that lower SES is significantly correlated with poorer health outcomes, with a particular emphasis "
                "on the lack of access to healthcare in rural areas.",
                "year": "2021",
                "volume": "16",
                "number": "6",
            },
        ),
    ],
)
def test_plos_query(doi: str, expected_dict: dict) -> None:
    """Test the plos query_doi()"""
    api = plos_api.PlosAPI(url="")

    filename = Path(__file__).parent / f"data_plos/{doi.replace('/', '_')}.json"

    with open(filename, encoding="utf-8") as file:
        json_str = file.read()

    with requests_mock.Mocker() as req_mock:
        # https://api.plos.org/solr/examples/
        req_mock.get(
            f"https://api.plos.org/search?q=id:{doi}", content=json_str.encode("utf-8")
        )

        actual = api.query_doi(doi=doi)
        expected = colrev.record.record_prep.PrepRecord(expected_dict)
        assert actual.data == expected.data
