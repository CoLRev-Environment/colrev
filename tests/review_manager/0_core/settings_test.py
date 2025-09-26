#!/usr/bin/env python
"""Test the colrev project settings"""
import os
from pathlib import Path

import colrev.settings
from colrev.constants import IDPattern
from colrev.constants import PDFPathType
from colrev.constants import ScreenCriterionType

# flake8: noqa: E501

# expected_printout: in settings-expected-printout.txt


def test_settings_load() -> None:
    """Test the settings_load"""
    settings = colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    )
    settings.screen.criteria = {  # type: ignore
        "test": colrev.settings.ScreenCriterion(
            explanation="Explanation of test",
            comment="",
            criterion_type=ScreenCriterionType.inclusion_criterion,
        )
    }
    settings.data.data_package_endpoints = [{"endpoint": "colrev.export_data"}]
    expected = {
        "project": {
            "title": "",
            "authors": [],
            "keywords": [],
            "protocol": None,
            "review_type": "literature_review",
            "id_pattern": IDPattern.three_authors_year,
            "share_stat_req": colrev.settings.ShareStatReq.processed,
            "delay_automated_processing": False,
            "colrev_version": "-",
            "auto_upgrade": True,
        },
        "sources": [],
        "search": {"retrieve_forthcoming": True},
        "prep": {
            "fields_to_keep": [],
            "defects_to_ignore": [],
            "prep_rounds": [
                {
                    "name": "prep",
                    "prep_package_endpoints": [
                        {"endpoint": "colrev.source_specific_prep"},
                        {"endpoint": "colrev.exclude_non_latin_alphabets"},
                        {"endpoint": "colrev.exclude_collections"},
                        {"endpoint": "colrev.exclude_complementary_materials"},
                        {"endpoint": "colrev.local_index"},
                        {"endpoint": "colrev.exclude_languages"},
                        {"endpoint": "colrev.remove_urls_with_500_errors"},
                        {"endpoint": "colrev.remove_broken_ids"},
                        {"endpoint": "colrev.get_doi_from_urls"},
                        {"endpoint": "colrev.get_year_from_vol_iss_jour"},
                        {"endpoint": "colrev.crossref"},
                        {"endpoint": "colrev.pubmed"},
                        {"endpoint": "colrev.europe_pmc"},
                        {"endpoint": "colrev.dblp"},
                        {"endpoint": "colrev.open_library"},
                    ],
                }
            ],
            "prep_man_package_endpoints": [{"endpoint": "colrev.export_man_prep"}],
        },
        "dedupe": {
            "dedupe_package_endpoints": [
                {"endpoint": "colrev.dedupe"},
            ],
        },
        "prescreen": {
            "explanation": "",
            "prescreen_package_endpoints": [
                {"endpoint": "colrev.colrev_cli_prescreen"},
            ],
        },
        "pdf_get": {
            "pdf_path_type": PDFPathType.symlink,
            "pdf_required_for_screen_and_synthesis": True,
            "defects_to_ignore": [],
            "rename_pdfs": True,
            "pdf_get_package_endpoints": [
                {"endpoint": "colrev.local_index"},
                {"endpoint": "colrev.unpaywall"},
                {"endpoint": "colrev.download_from_website"},
            ],
            "pdf_get_man_package_endpoints": [
                {"endpoint": "colrev.colrev_cli_pdf_get_man"}
            ],
        },
        "pdf_prep": {
            "keep_backup_of_pdfs": True,
            "pdf_prep_package_endpoints": [
                {"endpoint": "colrev.ocrmypdf"},
                {"endpoint": "colrev.remove_coverpage"},
                {"endpoint": "colrev.remove_last_page"},
                {"endpoint": "colrev.grobid_tei"},
            ],
            "pdf_prep_man_package_endpoints": [
                {"endpoint": "colrev.colrev_cli_pdf_prep_man"}
            ],
        },
        "screen": {
            "explanation": None,
            "criteria": {
                "test": {
                    "explanation": "Explanation of test",
                    "comment": "",
                    "criterion_type": ScreenCriterionType.inclusion_criterion,
                }
            },
            "screen_package_endpoints": [{"endpoint": "colrev.colrev_cli_screen"}],
        },
        "data": {"data_package_endpoints": [{"endpoint": "colrev.export_data"}]},
    }
    actual = settings.model_dump()

    print(settings)

    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    if not any("true" == os.getenv(x) for x in identifier_list):
        assert expected == actual

    assert not settings.is_curated_repo()


# def test_search_source_error_wrong_path() -> None:
#     with open(
#         Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
#     ) as file:
#         settings = json.load(file)
#     settings["sources"][0]["filepath"] = "other_path"

#     with pytest.raises(colrev_exceptions.InvalidSettingsError):
#         colrev.settings._load_settings_from_dict(loaded_dict=settings)


def test_curated_masterdata() -> None:

    settings = colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    )

    settings.data.data_package_endpoints = [
        {
            "endpoint": "colrev.colrev_curation",
            "curation_url": "https://github.com/CoLRev-curations/the-journal-of-strategic-information-systems",
            "curated_masterdata": True,
            "masterdata_restrictions": {
                "1991": {
                    "ENTRYTYPE": "article",
                    "volume": True,
                    "number": True,
                    "journal": "The Journal of Strategic Information Systems",
                }
            },
            "curated_fields": ["doi", "url", "dblp_key"],
        }
    ]

    assert settings.is_curated_masterdata_repo()
