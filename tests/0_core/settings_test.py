#!/usr/bin/env python
import os
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.review_manager
import colrev.settings


expected_printout = """Review (literature_review):
Search
 - retrieve_forthcoming: True
Sources
colrev.pdfs_dir (type: PDFS, filename: data/search/pdfs.bib)
   search parameters:   {'scope': {'path': 'data/pdfs'}}
Load
 - TODO
Preparation
 - prep_rounds:
   - prep (colrev.resolve_crossrefs,colrev.source_specific_prep,colrev.exclude_non_latin_alphabets,...)
 - fields_to_keep: []
Dedupe
 - same_source_merges: SameSourceMergePolicy.prevent
 - colrev.active_learning_training,colrev.active_learning_automated
Prescreen
Prescreen package endoints: colrev.scope_prescreen,colrev.colrev_cli_prescreen
PDF get
 - pdf_path_type: PDFPathType.symlink - colrev.local_index,colrev.unpaywall,colrev.website_screenshot
PDF prep
 - colrev.pdf_check_ocr,colrev.remove_coverpage,colrev.remove_last_page,colrev.validate_pdf_metadata,colrev.validate_completeness,colrev.create_tei
Screen
 -
Data
 - """


def test_settings_load() -> None:
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
            "id_pattern": colrev.settings.IDPattern.three_authors_year,
            "share_stat_req": colrev.settings.ShareStatReq.processed,
            "delay_automated_processing": False,
            "colrev_version": "-",
            "auto_upgrade": True,
        },
        "sources": [
            {
                "endpoint": "colrev.pdfs_dir",
                "filename": Path("data/search/pdfs.bib"),
                "search_type": colrev.settings.SearchType.PDFS,
                "search_parameters": {"scope": {"path": "data/pdfs"}},
                "load_conversion_package_endpoint": {"endpoint": "colrev.bibtex"},
                "comment": "",
            }
        ],
        "search": {"retrieve_forthcoming": True},
        "load": {},
        "prep": {
            "fields_to_keep": [],
            "prep_rounds": [
                {
                    "name": "prep",
                    "similarity": 0.8,
                    "prep_package_endpoints": [
                        {"endpoint": "colrev.resolve_crossrefs"},
                        {"endpoint": "colrev.source_specific_prep"},
                        {"endpoint": "colrev.exclude_non_latin_alphabets"},
                        {"endpoint": "colrev.exclude_collections"},
                        {"endpoint": "colrev.exclude_complementary_materials"},
                        {"endpoint": "colrev.get_masterdata_from_local_index"},
                        {"endpoint": "colrev.exclude_languages"},
                        {"endpoint": "colrev.remove_urls_with_500_errors"},
                        {"endpoint": "colrev.remove_broken_ids"},
                        {"endpoint": "colrev.global_ids_consistency_check"},
                        {"endpoint": "colrev.get_doi_from_urls"},
                        {"endpoint": "colrev.get_year_from_vol_iss_jour"},
                        {"endpoint": "colrev.get_masterdata_from_crossref"},
                        {"endpoint": "colrev.get_masterdata_from_pubmed"},
                        {"endpoint": "colrev.get_masterdata_from_europe_pmc"},
                        {"endpoint": "colrev.get_masterdata_from_dblp"},
                        {"endpoint": "colrev.get_masterdata_from_open_library"},
                    ],
                }
            ],
            "prep_man_package_endpoints": [{"endpoint": "colrev.export_man_prep"}],
        },
        "dedupe": {
            "same_source_merges": colrev.settings.SameSourceMergePolicy.prevent,
            "dedupe_package_endpoints": [
                {"endpoint": "colrev.active_learning_training"},
                {"endpoint": "colrev.active_learning_automated"},
            ],
        },
        "prescreen": {
            "explanation": "",
            "prescreen_package_endpoints": [
                {
                    "endpoint": "colrev.scope_prescreen",
                    "LanguageScope": ["eng"],
                },
                {"endpoint": "colrev.colrev_cli_prescreen"},
            ],
        },
        "pdf_get": {
            "pdf_path_type": colrev.settings.PDFPathType.symlink,
            "pdf_required_for_screen_and_synthesis": True,
            "rename_pdfs": True,
            "pdf_get_package_endpoints": [
                {"endpoint": "colrev.local_index"},
                {"endpoint": "colrev.unpaywall"},
                {"endpoint": "colrev.website_screenshot"},
            ],
            "pdf_get_man_package_endpoints": [
                {"endpoint": "colrev.colrev_cli_pdf_get_man"}
            ],
        },
        "pdf_prep": {
            "keep_backup_of_pdfs": True,
            "pdf_prep_package_endpoints": [
                {"endpoint": "colrev.pdf_check_ocr"},
                {"endpoint": "colrev.remove_coverpage"},
                {"endpoint": "colrev.remove_last_page"},
                {"endpoint": "colrev.validate_pdf_metadata"},
                {"endpoint": "colrev.validate_completeness"},
                {"endpoint": "colrev.create_tei"},
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

    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    if not any("true" == os.getenv(x) for x in identifier_list):
        assert expected == actual

    assert not settings.is_curated_repo()


def test_settings_schema() -> None:
    expected = {
        "type": "object",
        "required": [
            "project",
            "sources",
            "search",
            "load",
            "prep",
            "dedupe",
            "prescreen",
            "pdf_get",
            "pdf_prep",
            "screen",
            "data",
        ],
        "properties": {
            "project": {"$ref": "#/definitions/ProjectSettings"},
            "sources": {
                "type": "array",
                "items": {"$ref": "#/definitions/SearchSource"},
            },
            "search": {"$ref": "#/definitions/SearchSettings"},
            "load": {"$ref": "#/definitions/LoadSettings"},
            "prep": {"$ref": "#/definitions/PrepSettings"},
            "dedupe": {"$ref": "#/definitions/DedupeSettings"},
            "prescreen": {"$ref": "#/definitions/PrescreenSettings"},
            "pdf_get": {"$ref": "#/definitions/PDFGetSettings"},
            "pdf_prep": {"$ref": "#/definitions/PDFPrepSettings"},
            "screen": {"$ref": "#/definitions/ScreenSettings"},
            "data": {"$ref": "#/definitions/DataSettings"},
        },
        "description": "CoLRev project settings",
        "$schema": "http://json-schema.org/draft-06/schema#",
        "definitions": {
            "ProjectSettings": {
                "type": "object",
                "required": [
                    "title",
                    "authors",
                    "keywords",
                    "review_type",
                    "id_pattern",
                    "share_stat_req",
                    "delay_automated_processing",
                    "colrev_version",
                    "auto_upgrade",
                ],
                "properties": {
                    "title": {"type": "string"},
                    "authors": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/Author"},
                    },
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "protocol": {"$ref": "#/definitions/Protocol"},
                    "review_type": {"type": "string"},
                    "id_pattern": {
                        "type": "string",
                        "enum": ["first_author_year", "three_authors_year"],
                    },
                    "share_stat_req": {
                        "type": "string",
                        "enum": ["none", "processed", "screened", "completed"],
                    },
                    "delay_automated_processing": {"type": "boolean"},
                    "colrev_version": {"type": "string"},
                    "auto_upgrade": {"type": "boolean"},
                },
                "description": "Project settings",
            },
            "Author": {
                "type": "object",
                "required": ["name", "initials", "email"],
                "properties": {
                    "name": {"type": "string"},
                    "initials": {"type": "string"},
                    "email": {"type": "string"},
                    "orcid": {"type": "string"},
                    "contributions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "affiliations": {"type": "string"},
                    "funding": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "identifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
                "description": "Author of the review",
            },
            "Protocol": {
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string"}},
                "description": "Review protocol",
            },
            "SearchSource": {
                "type": "object",
                "required": [
                    "endpoint",
                    "filename",
                    "search_type",
                    "search_parameters",
                    "load_conversion_package_endpoint",
                ],
                "properties": {
                    "endpoint": {"type": "string"},
                    "filename": {"type": "path"},
                    "search_type": {
                        "type": "string",
                        "enum": [
                            "DB",
                            "TOC",
                            "BACKWARD_SEARCH",
                            "FORWARD_SEARCH",
                            "PDFS",
                            "OTHER",
                        ],
                    },
                    "search_parameters": {"type": "object", "additionalProperties": {}},
                    "load_conversion_package_endpoint": {
                        "package_endpoint_type": "load_conversion",
                        "type": "package_endpoint",
                    },
                    "comment": {"type": "string"},
                },
                "description": "Search source settings",
            },
            "SearchSettings": {
                "type": "object",
                "required": ["retrieve_forthcoming"],
                "properties": {"retrieve_forthcoming": {"type": "boolean"}},
                "description": "Search settings",
            },
            "LoadSettings": {
                "type": "object",
                "properties": {},
                "description": "Load settings",
            },
            "PrepSettings": {
                "type": "object",
                "required": [
                    "fields_to_keep",
                    "prep_rounds",
                    "prep_man_package_endpoints",
                ],
                "properties": {
                    "fields_to_keep": {"type": "array", "items": {"type": "string"}},
                    "prep_rounds": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/PrepRound"},
                    },
                    "prep_man_package_endpoints": {
                        "package_endpoint_type": "prep_man",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "Prep settings",
            },
            "PrepRound": {
                "type": "object",
                "required": ["name", "similarity", "prep_package_endpoints"],
                "properties": {
                    "name": {"type": "string"},
                    "similarity": {"type": "number"},
                    "prep_package_endpoints": {
                        "package_endpoint_type": "prep",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "Prep round settings",
            },
            "DedupeSettings": {
                "type": "object",
                "required": ["same_source_merges", "dedupe_package_endpoints"],
                "properties": {
                    "same_source_merges": {
                        "type": "string",
                        "enum": ["prevent", "warn", "apply"],
                    },
                    "dedupe_package_endpoints": {
                        "package_endpoint_type": "dedupe",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "Dedupe settings",
            },
            "PrescreenSettings": {
                "type": "object",
                "required": ["explanation", "prescreen_package_endpoints"],
                "properties": {
                    "explanation": {"type": "string"},
                    "prescreen_package_endpoints": {
                        "package_endpoint_type": "prescreen",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "Prescreen settings",
            },
            "PDFGetSettings": {
                "type": "object",
                "required": [
                    "pdf_path_type",
                    "pdf_required_for_screen_and_synthesis",
                    "rename_pdfs",
                    "pdf_get_package_endpoints",
                    "pdf_get_man_package_endpoints",
                ],
                "properties": {
                    "pdf_path_type": {"type": "string", "enum": ["symlink", "copy"]},
                    "pdf_required_for_screen_and_synthesis": {"type": "boolean"},
                    "rename_pdfs": {"type": "boolean"},
                    "pdf_get_package_endpoints": {
                        "package_endpoint_type": "pdf_get",
                        "type": "package_endpoint_array",
                    },
                    "pdf_get_man_package_endpoints": {
                        "package_endpoint_type": "pdf_get_man",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "PDF get settings",
            },
            "PDFPrepSettings": {
                "type": "object",
                "required": [
                    "keep_backup_of_pdfs",
                    "pdf_prep_package_endpoints",
                    "pdf_prep_man_package_endpoints",
                ],
                "properties": {
                    "keep_backup_of_pdfs": {"type": "boolean"},
                    "pdf_prep_package_endpoints": {
                        "package_endpoint_type": "pdf_prep",
                        "type": "package_endpoint_array",
                    },
                    "pdf_prep_man_package_endpoints": {
                        "package_endpoint_type": "pdf_prep_man",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "PDF prep settings",
            },
            "ScreenSettings": {
                "type": "object",
                "required": ["criteria", "screen_package_endpoints"],
                "properties": {
                    "explanation": {"type": "string"},
                    "criteria": {
                        "type": "object",
                        "additionalProperties": {
                            "$ref": "#/definitions/ScreenCriterion"
                        },
                    },
                    "screen_package_endpoints": {
                        "package_endpoint_type": "screen",
                        "type": "package_endpoint_array",
                    },
                },
                "description": "Screen settings",
            },
            "ScreenCriterion": {
                "type": "object",
                "required": ["explanation", "criterion_type"],
                "properties": {
                    "explanation": {"type": "string"},
                    "comment": {"type": "string"},
                    "criterion_type": {
                        "type": "string",
                        "enum": ["inclusion_criterion", "exclusion_criterion"],
                    },
                },
                "description": "Screen criterion",
            },
            "DataSettings": {
                "type": "object",
                "required": ["data_package_endpoints"],
                "properties": {
                    "data_package_endpoints": {
                        "package_endpoint_type": "data",
                        "type": "package_endpoint_array",
                    }
                },
                "description": "Data settings",
            },
        },
    }

    identifier_list = ["GITHUB_ACTIONS", "CIRCLECI", "TRAVIS", "GITLAB_CI"]
    if not any("true" == os.getenv(x) for x in identifier_list):
        actual = colrev.settings.Settings.get_settings_schema()
        assert expected == actual
