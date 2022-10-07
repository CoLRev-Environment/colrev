#!/usr/bin/env python3
"""Web-UI editor for CoLRev project settings"""
from __future__ import annotations

import json
import os
import signal
import webbrowser
from pathlib import Path
from threading import Timer
from typing import TYPE_CHECKING

from flask import Flask
from flask import jsonify
from flask import request
from flask import Response
from flask import send_from_directory
from flask_cors import CORS

DEV = True

if not DEV:
    import colrev.env.package_manager
    import colrev.settings

if not DEV:
    if TYPE_CHECKING:
        import colrev.review_manager.ReviewManager


class SettingsEditor:
    """A web-based editor for CoLRev settings"""

    # pylint: disable=invalid-name
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    def __init__(self, *, review_manager: any = None) -> None:

        if DEV:
            self.settings_path = Path.cwd() / Path("settings.json")
        else:
            self.review_manager = review_manager
            self.package_manager = self.review_manager.get_package_manager()
            self.settings_path: Path = self.review_manager.settings_path

        # Note : no need for default values (they are already inserted before by the template setup)

    def _open_browser(self) -> None:

        url = "http://127.0.0.1:5000"

        Timer(1, lambda: webbrowser.open_new(url)).start()
        print(f"Open at {url}")

    def open_settings_editor(self) -> None:
        """Open the settings editor"""

        # pylint: disable=too-many-statements

        app = Flask(__name__, static_url_path="", static_folder="build")
        CORS(app)

        app.config["path"] = str(self.settings_path)

        # print("Settings File Path: ", app.config["path"])

        @app.route("/", defaults={"path": ""})
        def serve(path: str) -> Response:  # pylint: disable=unused-argument
            assert app.static_folder
            return send_from_directory(Path(app.static_folder), "index.html")

        @app.route("/<path:filename>")
        def base_static(filename: str) -> Response:
            return send_from_directory(app.root_path + "/", filename)

        @app.route("/api/getSettings")
        def getSettings() -> Response:

            with open(self.settings_path, encoding="utf-8") as file:
                json__content = file.read()

            response = app.response_class(
                response=json__content, mimetype="application/json"
            )

            return response

        @app.route("/api/saveSettings", methods=["POST"])
        def saveSettings() -> str:
            commit_selected = request.args.get("commitSelected")

            # print("saveSettings.commit_selected", commit_selected)

            with open(self.settings_path, "w", encoding="utf-8") as outfile:
                json_string = json.dumps(request.json, indent=4)
                outfile.write(json_string)
            if commit_selected:
                if DEV:
                    print("save with commit")
                else:
                    self.review_manager.dataset.add_changes(path=self.settings_path)
                    self.review_manager.create_commit(msg="Update settings")

            return "ok"

        @app.route("/api/getOptions")
        def getOptions() -> Response:

            # Decision: get the whole list of setting_options (not individually)
            # "similarity": {'type': 'float', 'min': 0, 'max': 1}

            options = {}

            if DEV:
                options = {
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
                                "curated_masterdata",
                                "curated_fields",
                                "colrev_version",
                            ],
                            "properties": {
                                "title": {"type": "string"},
                                "authors": {
                                    "type": "array",
                                    "items": {"$ref": "#/definitions/Author"},
                                },
                                "keywords": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "protocol": {"$ref": "#/definitions/Protocol"},
                                "review_type": {"type": "string"},
                                "id_pattern": {
                                    "type": "string",
                                    "enum": ["first_author_year", "three_authors_year"],
                                },
                                "share_stat_req": {
                                    "type": "string",
                                    "enum": [
                                        "none",
                                        "processed",
                                        "screened",
                                        "completed",
                                    ],
                                },
                                "delay_automated_processing": {"type": "boolean"},
                                "curation_url": {"type": "string"},
                                "curated_masterdata": {"type": "boolean"},
                                "curated_fields": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "colrev_version": {"type": "string"},
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
                                "source_identifier",
                                "search_parameters",
                                "load_conversion_package_endpoint",
                            ],
                            "properties": {
                                "endpoint": {"type": "string"},
                                "filename": {},
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
                                "source_identifier": {"type": "string"},
                                "search_parameters": {
                                    "type": "object",
                                    "additionalProperties": {},
                                },
                                "load_conversion_package_endpoint": {
                                    "package_endpoint_type": "load_conversion",
                                    "type": "package_endpoint_array_item",
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
                                "fields_to_keep": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "prep_rounds": {
                                    "type": "array",
                                    "items": {"$ref": "#/definitions/PrepRound"},
                                },
                                "prep_man_package_endpoints": {
                                    "package_endpoint_type": "prep_man",
                                    "type": "package_endpoint_array_array",
                                },
                            },
                            "description": "Prep settings",
                        },
                        "PrepRound": {
                            "type": "object",
                            "required": [
                                "name",
                                "similarity",
                                "prep_package_endpoints",
                            ],
                            "properties": {
                                "name": {"type": "string"},
                                "similarity": {"type": "number"},
                                "prep_package_endpoints": {
                                    "package_endpoint_type": "prep",
                                    "type": "package_endpoint_array_array",
                                },
                            },
                            "description": "Prep round settings",
                        },
                        "DedupeSettings": {
                            "type": "object",
                            "required": [
                                "same_source_merges",
                                "dedupe_package_endpoints",
                            ],
                            "properties": {
                                "same_source_merges": {
                                    "type": "string",
                                    "enum": ["prevent", "warn", "apply"],
                                },
                                "dedupe_package_endpoints": {
                                    "package_endpoint_type": "dedupe",
                                    "type": "package_endpoint_array_array",
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
                                    "type": "package_endpoint_array_array",
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
                                "pdf_path_type": {
                                    "type": "string",
                                    "enum": ["symlink", "copy"],
                                },
                                "pdf_required_for_screen_and_synthesis": {
                                    "type": "boolean"
                                },
                                "rename_pdfs": {"type": "boolean"},
                                "pdf_get_package_endpoints": {
                                    "package_endpoint_type": "pdf_get",
                                    "type": "package_endpoint_array_array",
                                },
                                "pdf_get_man_package_endpoints": {
                                    "package_endpoint_type": "pdf_get_man",
                                    "type": "package_endpoint_array_array",
                                },
                            },
                            "description": "PDF get settings",
                        },
                        "PDFPrepSettings": {
                            "type": "object",
                            "required": [
                                "pdf_prep_package_endpoints",
                                "pdf_prep_man_package_endpoints",
                            ],
                            "properties": {
                                "pdf_prep_package_endpoints": {
                                    "package_endpoint_type": "pdf_prep",
                                    "type": "package_endpoint_array_array",
                                },
                                "pdf_prep_man_package_endpoints": {
                                    "package_endpoint_type": "pdf_prep_man",
                                    "type": "package_endpoint_array_array",
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
                                    "type": "package_endpoint_array_array",
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
                                    "enum": [
                                        "inclusion_criterion",
                                        "exclusion_criterion",
                                    ],
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
                                    "type": "package_endpoint_array_array",
                                }
                            },
                            "description": "Data settings",
                        },
                    },
                }
            else:
                options = colrev.settings.Settings.get_settings_schema()

            return jsonify(options)

        @app.route("/api/getPackages")
        def getPackages() -> Response:
            package_type_string = request.args.get("PackageEndpointType")

            discovered_packages = {}

            if DEV:
                if package_type_string == "data":
                    discovered_packages = {
                        "colrev_built_in.manuscript": {
                            "endpoint": "colrev.ops.built_in.data.manuscript.Manuscript",
                            "installed": True,
                            "description": "Synthesize the literature in a manuscript\n\n    The manuscript (paper.md) is created automatically.\n    Records are added for synthesis after the <!-- NEW_RECORD_SOURCE -->\n    Once records are moved to other parts of the manuscript (cited or in comments)\n    they are assumed to be synthesized in the manuscript.\n    Once they are synthesized in all data endpoints,\n    CoLRev sets their status to rev_synthesized.\n    The data operation also builds the manuscript (using pandoc, csl and a template).\n    ",
                        },
                        "colrev_built_in.structured": {
                            "endpoint": "colrev.ops.built_in.data.structured.StructuredData",
                            "installed": True,
                            "description": "Summarize the literature in a structured data extraction (a table)",
                        },
                        "colrev_built_in.bibliography_export": {
                            "endpoint": "colrev.ops.built_in.data.bibliography_export.BibliographyExport",
                            "installed": True,
                            "description": "Export the sample references in Endpoint format",
                        },
                        "colrev_built_in.prisma": {
                            "endpoint": "colrev.ops.built_in.data.prisma.PRISMA",
                            "installed": True,
                            "description": "Create a PRISMA diagram",
                        },
                        "colrev_built_in.github_pages": {
                            "endpoint": "colrev.ops.built_in.data.github_pages.GithubPages",
                            "installed": True,
                            "description": "Export the literature review into a Github Page",
                        },
                        "colrev_built_in.zettlr": {
                            "endpoint": "colrev.ops.built_in.data.zettlr.Zettlr",
                            "installed": True,
                            "description": "Export the sample into a Zettlr database",
                        },
                    }

                if package_type_string == "load_conversion":
                    discovered_packages = {
                        "colrev_built_in.bibtex": {
                            "endpoint": "colrev.ops.built_in.load_conversion.bib_pybtex_loader.BibPybtexLoader",
                            "installed": True,
                            "description": "Loads BibTeX files (based on pybtex)",
                        },
                        "colrev_built_in.csv": {
                            "endpoint": "colrev.ops.built_in.load_conversion.table_loader.CSVLoader",
                            "installed": True,
                            "description": "Loads csv files (based on pandas)",
                        },
                        "colrev_built_in.excel": {
                            "endpoint": "colrev.ops.built_in.load_conversion.table_loader.ExcelLoader",
                            "installed": True,
                            "description": "Loads Excel (xls, xlsx) files (based on pandas)",
                        },
                        "colrev_built_in.zotero_translate": {
                            "endpoint": "colrev.ops.built_in.load_conversion.zotero_loader.ZoteroTranslationLoader",
                            "installed": True,
                            "description": "Loads bibliography files (based on pandas).\n    Supports ris, rdf, json, mods, xml, marc, txt",
                        },
                        "colrev_built_in.md_to_bib": {
                            "endpoint": "colrev.ops.built_in.load_conversion.markdown_loader.MarkdownLoader",
                            "installed": True,
                            "description": "Loads reference strings from text (md) files (based on GROBID)",
                        },
                        "colrev_built_in.bibutils": {
                            "endpoint": "colrev.ops.built_in.load_conversion.bibutils_loader.BibutilsLoader",
                            "installed": True,
                            "description": "Loads bibliography files (based on bibutils)\n    Supports ris, end, enl, copac, isi, med",
                        },
                    }

                if package_type_string == "search_source":
                    discovered_packages = {
                        "colrev_built_in.unknown_source": {
                            "endpoint": "colrev.ops.built_in.search_sources.unknown_source.UnknownSearchSource",
                            "installed": True,
                            "description": "UnknownSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.crossref": {
                            "endpoint": "colrev.ops.built_in.search_sources.crossref.CrossrefSourceSearchSource",
                            "installed": True,
                            "description": "Performs a search using the Crossref API",
                        },
                        "colrev_built_in.dblp": {
                            "endpoint": "colrev.ops.built_in.search_sources.dblp.DBLPSearchSource",
                            "installed": True,
                            "description": "DBLPSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.acm_digital_library": {
                            "endpoint": "colrev.ops.built_in.search_sources.acm_digital_library.ACMDigitalLibrarySearchSource",
                            "installed": True,
                            "description": "ACMDigitalLibrarySearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.pubmed": {
                            "endpoint": "colrev.ops.built_in.search_sources.pubmed.PubMedSearchSource",
                            "installed": True,
                            "description": "PubMedSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.wiley": {
                            "endpoint": "colrev.ops.built_in.search_sources.wiley.WileyOnlineLibrarySearchSource",
                            "installed": True,
                            "description": "WileyOnlineLibrarySearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.ais_library": {
                            "endpoint": "colrev.ops.built_in.search_sources.aisel.AISeLibrarySearchSource",
                            "installed": True,
                            "description": "AISeLibrarySearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.google_scholar": {
                            "endpoint": "colrev.ops.built_in.search_sources.google_scholar.GoogleScholarSearchSource",
                            "installed": True,
                            "description": "GoogleScholarSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.web_of_science": {
                            "endpoint": "colrev.ops.built_in.search_sources.web_of_science.WebOfScienceSearchSource",
                            "installed": True,
                            "description": "WebOfScienceSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.scopus": {
                            "endpoint": "colrev.ops.built_in.search_sources.scopus.ScopusSearchSource",
                            "installed": True,
                            "description": "ScopusSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.pdfs_dir": {
                            "endpoint": "colrev.ops.built_in.search_sources.pdfs_dir.PDFSearchSource",
                            "installed": True,
                            "description": "PDFSearchSource(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                        "colrev_built_in.pdf_backward_search": {
                            "endpoint": "colrev.ops.built_in.search_sources.pdf_backward_search.BackwardSearchSource",
                            "installed": True,
                            "description": "Performs a backward search extracting references from PDFs using GROBID\n    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)\n    ",
                        },
                        "colrev_built_in.colrev_project": {
                            "endpoint": "colrev.ops.built_in.search_sources.colrev_project.ColrevProjectSearchSource",
                            "installed": True,
                            "description": "Performs a search in a CoLRev project",
                        },
                        "colrev_built_in.local_index": {
                            "endpoint": "colrev.ops.built_in.search_sources.local_index.LocalIndexSearchSource",
                            "installed": True,
                            "description": "Performs a search in the LocalIndex",
                        },
                        "colrev_built_in.transport_research_international_documentation": {
                            "endpoint": "colrev.ops.built_in.search_sources.transport_research_international_documentation.TransportResearchInternationalDocumentation",
                            "installed": True,
                            "description": "TransportResearchInternationalDocumentation(*, source_operation: 'colrev.operation.CheckOperation', settings: 'dict') -> 'None'",
                        },
                    }
            else:
                package_type = colrev.env.package_manager.PackageEndpointType[
                    package_type_string
                ]
                discovered_packages = self.package_manager.discover_packages(
                    package_type=package_type
                )

            return jsonify(discovered_packages)

        # pylint: disable=unused-argument
        @app.route("/api/getPackageDetails")
        def getPackageDetails() -> Response:
            package_type_string = request.args.get("PackageEndpointType")
            package_identifier = request.args.get("PackageIdentifier")
            endpoint_version = request.args.get("EndpointVersion")

            package_details = {}

            # TODO (GW): use endpoint_version

            if DEV:
                if package_type_string == "data":
                    # Example: package_identifier="colrev_built_in.manuscript"
                    package_details = {
                        "type": "object",
                        "required": [
                            "endpoint",
                            "version",
                            "word_template",
                            "csl_style",
                        ],
                        "properties": {
                            "endpoint": {"type": "string"},
                            "version": {"type": "string"},
                            "word_template": {
                                "tooltip": "Path to the word template (for Pandoc)",
                                "type": "path",
                            },
                            "csl_style": {"type": "string"},
                            "paper_path": {
                                "default": "paper.md",
                                "tooltip": "Path for the paper (markdown source document)",
                                "type": "path",
                            },
                            "paper_output": {"default": "paper.docx", "type": "path"},
                        },
                        "description": "Manuscript settings",
                        "$schema": "http://json-schema.org/draft-06/schema#",
                    }

                if package_type_string == "prescreen":
                    # Example: package_identifier="colrev_built_in.scope_prescreen"
                    package_details = {
                        "type": "object",
                        "required": ["endpoint"],
                        "properties": {
                            "endpoint": {"type": "string"},
                            "TimeScopeFrom": {
                                "type": "integer",
                                "tooltip": "Lower bound for the time scope",
                                "min": 1900,
                                "max": 2050,
                            },
                            "TimeScopeTo": {
                                "type": "integer",
                                "tooltip": "Upper bound for the time scope",
                                "min": 1900,
                                "max": 2050,
                            },
                            "LanguageScope": {
                                "type": "array",
                                "items": {},
                                "tooltip": "Language scope",
                            },
                            "ExcludeComplementaryMaterials": {
                                "type": "boolean",
                                "tooltip": "Whether complementary materials (coverpages etc.) are excluded",
                            },
                            "OutletInclusionScope": {
                                "type": "object",
                                "additionalProperties": {},
                                "tooltip": "Particular outlets that should be included (exclusively)",
                            },
                            "OutletExclusionScope": {
                                "type": "object",
                                "additionalProperties": {},
                                "tooltip": "Particular outlets that should be excluded",
                            },
                            "ENTRYTYPEScope": {
                                "type": "array",
                                "items": {},
                                "tooltip": "Particular ENTRYTYPEs that should be included (exclusively)",
                            },
                        },
                        "description": "ScopePrescreenSettings",
                        "$schema": "http://json-schema.org/draft-06/schema#",
                    }

                if package_type_string == "search_source":
                    package_details = {
                        "type": "object",
                        "required": [
                            "endpoint",
                            "filename",
                            "search_type",
                            "source_identifier",
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
                            "source_identifier": {"type": "string"},
                            "search_parameters": {
                                "type": "object",
                                "additionalProperties": {},
                            },
                            "load_conversion_package_endpoint": {
                                "type": "package_endpoint",
                                "package_endpoint_type": "load_conversion",
                            },
                            "comment": {"type": "string"},
                        },
                        "description": "Search source settings",
                        "$schema": "http://json-schema.org/draft-06/schema#",
                    }

            else:
                package_type = colrev.env.package_manager.PackageEndpointType[
                    package_type_string
                ]
                package_details = self.package_manager.get_package_details(
                    package_type=package_type, package_identifier=package_identifier
                )

            return jsonify(package_details)

        @app.get("/api/shutdown")
        def shutdown() -> str:
            # func = request.environ.get("werkzeug.server.shutdown")
            # if func is None:
            #     return {"error": "Not running with the Werkzeug Server"}
            # func()
            # return "Server shutting down..."

            timer = Timer(3.0, terminate_process)
            timer.start()  # after 3 seconds
            return "ok"

        def terminate_process() -> None:
            pid = os.getpid()
            os.kill(pid, signal.SIGTERM)

        self._open_browser()
        app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)


def main() -> None:
    """Main entrypoint for the settings editor"""

    if DEV:
        se_instance = SettingsEditor()
        se_instance.open_settings_editor()
    else:
        review_manager = colrev.review_manager.ReviewManager()
        se_instance = SettingsEditor(review_manager=review_manager)
        se_instance.open_settings_editor()


if __name__ == "__main__":
    main()
