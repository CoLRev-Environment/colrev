#!/usr/bin/env python
"""Test the colrev project settings"""
import json
import os
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.settings
from colrev.constants import IDPattern
from colrev.constants import PDFPathType
from colrev.constants import ScreenCriterionType
from colrev.constants import SearchType

# flake8: noqa: E501

# expected_printout: in settings-expected-printout.txt


def test_settings_load() -> None:
    """Test the settings_load"""
    settings = colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    )
    settings.sources[0].comment = "user comment"
    settings.screen.criteria = {  # type: ignore
        "test": colrev.settings.ScreenCriterion(
            explanation="Explanation of test",
            comment="",
            criterion_type=ScreenCriterionType.inclusion_criterion,
        )
    }
    settings.data.data_package_endpoints = [{"endpoint": "colrev_export_data"}]
    expected = {
        "project": {
            "title": "",
            "authors": [],
            "keywords": [],
            "protocol": None,
            "review_type": "colrev_literature_review",
            "id_pattern": IDPattern.three_authors_year,
            "share_stat_req": colrev.settings.ShareStatReq.processed,
            "delay_automated_processing": False,
            "colrev_version": "-",
            "auto_upgrade": True,
        },
        "sources": [
            {
                "endpoint": "colrev_files_dir",
                "filename": Path("data/search/files.bib"),
                "search_type": SearchType.FILES,
                "search_parameters": {"scope": {"path": "data/pdfs"}},
                "comment": "user comment",
            }
        ],
        "search": {"retrieve_forthcoming": True},
        "prep": {
            "fields_to_keep": [],
            "defects_to_ignore": [],
            "prep_rounds": [
                {
                    "name": "prep",
                    "prep_package_endpoints": [
                        {"endpoint": "colrev_source_specific_prep"},
                        {"endpoint": "colrev_exclude_non_latin_alphabets"},
                        {"endpoint": "colrev_exclude_collections"},
                        {"endpoint": "colrev_exclude_complementary_materials"},
                        {"endpoint": "colrev_local_index"},
                        {"endpoint": "colrev_exclude_languages"},
                        {"endpoint": "colrev_remove_urls_with_500_errors"},
                        {"endpoint": "colrev_remove_broken_ids"},
                        {"endpoint": "colrev_get_doi_from_urls"},
                        {"endpoint": "colrev_get_year_from_vol_iss_jour"},
                        {"endpoint": "colrev_crossref"},
                        {"endpoint": "colrev_pubmed"},
                        {"endpoint": "colrev_europe_pmc"},
                        {"endpoint": "colrev_dblp"},
                        {"endpoint": "colrev_open_library"},
                    ],
                }
            ],
            "prep_man_package_endpoints": [{"endpoint": "colrev_export_man_prep"}],
        },
        "dedupe": {
            "dedupe_package_endpoints": [
                {"endpoint": "colrev_dedupe"},
            ],
        },
        "prescreen": {
            "explanation": "",
            "prescreen_package_endpoints": [
                {"endpoint": "colrev_cli_prescreen"},
            ],
        },
        "pdf_get": {
            "pdf_path_type": PDFPathType.symlink,
            "pdf_required_for_screen_and_synthesis": True,
            "defects_to_ignore": [],
            "rename_pdfs": True,
            "pdf_get_package_endpoints": [
                {"endpoint": "colrev_local_index"},
                {"endpoint": "colrev_unpaywall"},
                {"endpoint": "colrev_download_from_website"},
            ],
            "pdf_get_man_package_endpoints": [{"endpoint": "colrev_cli_pdf_get_man"}],
        },
        "pdf_prep": {
            "keep_backup_of_pdfs": True,
            "pdf_prep_package_endpoints": [
                {"endpoint": "colrev_ocrmypdf"},
                {"endpoint": "colrev_remove_coverpage"},
                {"endpoint": "colrev_remove_last_page"},
                {"endpoint": "colrev_grobid_tei"},
            ],
            "pdf_prep_man_package_endpoints": [{"endpoint": "colrev_cli_pdf_prep_man"}],
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
            "screen_package_endpoints": [{"endpoint": "colrev_cli_screen"}],
        },
        "data": {"data_package_endpoints": [{"endpoint": "colrev_export_data"}]},
    }
    actual = settings.model_dump()

    print(settings)

    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    if not any("true" == os.getenv(x) for x in identifier_list):
        assert expected == actual

    assert not settings.is_curated_repo()


def test_search_source_error_wrong_path() -> None:
    with open(
        Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    ) as file:
        settings = json.load(file)
    settings["sources"][0]["filename"] = "other_path"

    with pytest.raises(colrev_exceptions.InvalidSettingsError):
        colrev.settings._load_settings_from_dict(loaded_dict=settings)


def test_search_source_error_duplicate_path() -> None:
    with open(
        Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    ) as file:
        settings = json.load(file)
    settings["sources"].append(settings["sources"][0])

    with pytest.raises(colrev_exceptions.InvalidSettingsError):
        colrev.settings._load_settings_from_dict(loaded_dict=settings)


def test_curated_masterdata() -> None:

    settings = colrev.settings.load_settings(
        settings_path=Path(colrev.__file__).parents[0] / Path("ops/init/settings.json")
    )

    settings.data.data_package_endpoints = [
        {
            "endpoint": "colrev_colrev_curation",
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


def test_get_query(
    base_repo_review_manager: colrev.review_manager.ReviewManager,
) -> None:
    query_file = Path(
        base_repo_review_manager.settings.sources[0].search_parameters["query_file"]
    )
    query_file.write_text("test_query")
    assert "test_query" == base_repo_review_manager.settings.sources[0].get_query()
    query_file.unlink()
    with pytest.raises(FileNotFoundError):
        base_repo_review_manager.settings.sources[0].get_query()

    base_repo_review_manager.settings.sources[0].search_parameters.pop("query_file")
    with pytest.raises(KeyError):
        base_repo_review_manager.settings.sources[0].get_query()
