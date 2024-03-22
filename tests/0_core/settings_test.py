#!/usr/bin/env python
"""Test the colrev project settings"""
import os
from dataclasses import asdict
from pathlib import Path

import colrev.env.utils
import colrev.settings
from colrev.constants import IDPattern
from colrev.constants import PDFPathType
from colrev.constants import ScreenCriterionType
from colrev.constants import SearchType

# expected_printout: in settings-expected-printout.txt


def test_settings_load() -> None:
    """Test the settings_load"""
    settings = colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0]
        / Path("template/init/settings.json")
    )
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
        "sources": [
            {
                "endpoint": "colrev.files_dir",
                "filename": Path("data/search/files.bib"),
                "search_type": SearchType.FILES,
                "search_parameters": {"scope": {"path": "data/pdfs"}},
                "comment": "",
            }
        ],
        "search": {"retrieve_forthcoming": True},
        "prep": {
            "fields_to_keep": [],
            "defects_to_ignore": ["inconsistent-with-url-metadata"],
            "prep_rounds": [
                {
                    "name": "prep",
                    "similarity": 0.8,
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
                {"endpoint": "colrev.website_screenshot"},
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
            "criteria": {},
            "screen_package_endpoints": [{"endpoint": "colrev.colrev_cli_screen"}],
        },
        "data": {"data_package_endpoints": []},
    }
    actual = asdict(settings)

    print(settings)

    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    if not any("true" == os.getenv(x) for x in identifier_list):
        assert expected == actual

    assert not settings.is_curated_repo()


def test_id_pattern() -> None:
    pattern = IDPattern("first_author_year")
    print(pattern)
    assert pattern.get_options() == ["first_author_year", "three_authors_year"]


def test_sharing_req() -> None:
    assert colrev.settings.ShareStatReq.get_options() == [
        "none",
        "processed",
        "screened",
        "completed",
    ]


def test_search_type() -> None:
    assert set(SearchType.get_options()) == {
        "MD",
        "API",
        "OTHER",
        "FORWARD_SEARCH",
        "DB",
        "TOC",
        "FILES",
        "BACKWARD_SEARCH",
    }


def test_pdf_path_type() -> None:
    assert PDFPathType.get_options() == ["symlink", "copy"]


def test_screen_criterion_type() -> None:
    assert ScreenCriterionType.get_options() == [
        "inclusion_criterion",
        "exclusion_criterion",
    ]
