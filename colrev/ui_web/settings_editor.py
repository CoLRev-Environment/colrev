#!/usr/bin/env python3
"""Web-UI editor for CoLRev project settings"""
from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask_cors import CORS

# from typing import TYPE_CHECKING

# import colrev.settings

# if TYPE_CHECKING:
#     import colrev.review_manager.ReviewManager


class SettingsEditor:
    # pylint: disable=invalid-name
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    # def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
    def __init__(self) -> None:

        # self.review_manager = review_manager
        # self.package_manager = review_manager.get_package_manager()
        # self.settings_path: Path = self.review_manager.settings_path

        # For testing:
        self.settings_path = Path.cwd() / Path("settings.json")

        # Note : no need for default values (they are already inserted before by the template setup)

    def _open_browser(self) -> None:

        url = "http://127.0.0.1:5000"

        Timer(1, lambda: webbrowser.open_new(url)).start()
        print(f"Open at {url}")

    def open_settings_editor(self):

        app = Flask(__name__, static_url_path="", static_folder="build")
        CORS(app)

        app.config["path"] = str(self.settings_path)

        # print("Settings File Path: ", app.config["path"])

        @app.route("/", defaults={"path": ""})
        def serve(path):  # pylint: disable=unused-argument
            return send_from_directory(app.static_folder, "index.html")

        @app.route("/<path:filename>")
        def base_static(filename):
            return send_from_directory(app.root_path + "/", filename)

        @app.route("/api/getSettings")
        def getSettings():

            with open(self.settings_path, encoding="utf-8") as file:
                json__content = file.read()

            response = app.response_class(
                response=json__content, mimetype="application/json"
            )

            return response

        @app.route("/api/saveSettings", methods=["POST"])
        def saveSettings(create_commit: bool = False):

            with open(self.settings_path, "w", encoding="utf-8") as outfile:
                json_string = json.dumps(request.json, indent=4)
                outfile.write(json_string)
            # if create_commit:
            #     self.review_manager.create_commit(msg="Update settings")
            return "ok"

        @app.route("/api/getOptions")
        def getOptions():

            # Decision: get the whole list of setting_options (not individually)
            # "similarity": {'type': 'float', 'min': 0, 'max': 1}

            # options = colrev.settings.Settings.get_settings_schema()

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
                            "filename",
                            "search_type",
                            "source_name",
                            "source_identifier",
                            "search_parameters",
                            "load_conversion_script",
                        ],
                        "properties": {
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
                            "source_name": {"type": "string"},
                            "source_identifier": {"type": "string"},
                            "search_parameters": {"type": "object"},
                            "load_conversion_script": {
                                "script_type": "load_conversion",
                                "type": "script_item",
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
                            "man_prep_scripts",
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
                            "man_prep_scripts": {
                                "script_type": "prep_man",
                                "type": "script_array",
                            },
                        },
                        "description": "Prep settings",
                    },
                    "PrepRound": {
                        "type": "object",
                        "required": ["name", "similarity", "scripts"],
                        "properties": {
                            "name": {"type": "string"},
                            "similarity": {"type": "number"},
                            "scripts": {"script_type": "prep", "type": "script_array"},
                        },
                        "description": "Prep round settings",
                    },
                    "DedupeSettings": {
                        "type": "object",
                        "required": ["same_source_merges", "scripts"],
                        "properties": {
                            "same_source_merges": {
                                "type": "string",
                                "enum": ["prevent", "apply", "warn"],
                            },
                            "scripts": {
                                "script_type": "dedupe",
                                "type": "script_array",
                            },
                        },
                        "description": "Dedupe settings",
                    },
                    "PrescreenSettings": {
                        "type": "object",
                        "required": ["explanation", "scripts"],
                        "properties": {
                            "explanation": {"type": "string"},
                            "scripts": {
                                "script_type": "prescreen",
                                "type": "script_array",
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
                            "scripts",
                            "man_pdf_get_scripts",
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
                            "scripts": {
                                "script_type": "pdf_get",
                                "type": "script_array",
                            },
                            "man_pdf_get_scripts": {
                                "script_type": "pdf_get_man",
                                "type": "script_array",
                            },
                        },
                        "description": "PDF get settings",
                    },
                    "PDFPrepSettings": {
                        "type": "object",
                        "required": ["scripts", "man_pdf_prep_scripts"],
                        "properties": {
                            "scripts": {
                                "script_type": "pdf_prep",
                                "type": "script_array",
                            },
                            "man_pdf_prep_scripts": {
                                "script_type": "pdf_prep_man",
                                "type": "script_array",
                            },
                        },
                        "description": "PDF prep settings",
                    },
                    "ScreenSettings": {
                        "type": "object",
                        "required": ["criteria", "scripts"],
                        "properties": {
                            "explanation": {"type": "string"},
                            "criteria": {
                                "type": "object",
                                "additionalProperties": {
                                    "$ref": "#/definitions/ScreenCriterion"
                                },
                            },
                            "scripts": {
                                "script_type": "screen",
                                "type": "script_array",
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
                        "required": ["scripts"],
                        "properties": {
                            "scripts": {"script_type": "data", "type": "script_array"}
                        },
                        "description": "Data settings",
                    },
                },
            }

            return jsonify(options)

        @app.route("/api/getScripts")
        def getScripts():
            package_type_string = request.args.get("packageType")

            # package_type = colrev.env.package_manager.PackageType[package_type_string]
            # discovered_packages = self.package_manager.discover_packages(
            #     package_type=package_type
            # )

            if package_type_string != "search_source":
                # For testing:
                # Example: script_type="load"
                # Returns:
                discovered_packages = {
                    "bibtex": {
                        "endpoint": "colrev.ops.built_in.load_conversion.bib_pybtex_loader.BibPybtexLoader",
                        "installed": True,
                        "description": "Loads BibTeX files (based on pybtex)",
                    },
                    "csv": {
                        "endpoint": "colrev.ops.built_in.load_conversion.spreadsheet_loader.CSVLoader",
                        "installed": True,
                        "description": "Loads csv files (based on pandas)",
                    },
                    "excel": {
                        "endpoint": "colrev.ops.built_in.load_conversion.spreadsheet_loader.ExcelLoader",
                        "installed": True,
                        "description": "Loads Excel (xls, xlsx) files (based on pandas)",
                    },
                    "zotero_translate": {
                        "endpoint": "colrev.ops.built_in.load_conversion.zotero_loader.ZoteroTranslationLoader",
                        "installed": True,
                        "description": "Loads bibliography files (based on pandas).\n    Supports ris, rdf, json, mods, xml, marc, txt",
                    },
                    "md_to_bib": {
                        "endpoint": "colrev.ops.built_in.load_conversion.markdown_loader.MarkdownLoader",
                        "installed": True,
                        "description": "Loads reference strings from text (md) files (based on GROBID)",
                    },
                    "bibutils": {
                        "endpoint": "colrev.ops.built_in.load_conversion.bibutils_loader.BibutilsLoader",
                        "installed": True,
                        "description": "Loads bibliography files (based on bibutils)\n    Supports ris, end, enl, copac, isi, med",
                    },
                }

            if package_type_string == "search_source":
                # For testing:
                # Example: script_type="search_source"
                # Returns:
                discovered_packages = {
                    "unknown_source": {
                        "endpoint": "colrev.ops.built_in.search_sources.unknown_source.UnknownSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "crossref": {
                        "endpoint": "colrev.ops.built_in.search_sources.crossref.CrossrefSourceSearchSource",
                        "installed": True,
                        "description": "Performs a search using the Crossref API",
                    },
                    "dblp": {
                        "endpoint": "colrev.ops.built_in.search_sources.dblp.DBLPSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "acm_digital_library": {
                        "endpoint": "colrev.ops.built_in.search_sources.acm_digital_library.ACMDigitalLibrarySearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "pubmed": {
                        "endpoint": "colrev.ops.built_in.search_sources.pubmed.PubMedSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "wiley": {
                        "endpoint": "colrev.ops.built_in.search_sources.wiley.WileyOnlineLibrarySearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "ais_library": {
                        "endpoint": "colrev.ops.built_in.search_sources.aisel.AISeLibrarySearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "google_scholar": {
                        "endpoint": "colrev.ops.built_in.search_sources.google_scholar.GoogleScholarSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "web_of_science": {
                        "endpoint": "colrev.ops.built_in.search_sources.web_of_science.WebOfScienceSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "scopus": {
                        "endpoint": "colrev.ops.built_in.search_sources.scopus.ScopusSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "pdfs_dir": {
                        "endpoint": "colrev.ops.built_in.search_sources.pdfs_dir.PDFSearchSource",
                        "installed": True,
                        "description": None,
                    },
                    "pdf_backward_search": {
                        "endpoint": "colrev.ops.built_in.search_sources.pdf_backward_search.BackwardSearchSource",
                        "installed": True,
                        "description": "Performs a backward search extracting references from PDFs using GROBID\n    Scope: all included papers with colrev_status in (rev_included, rev_synthesized)\n    ",
                    },
                    "colrev_project": {
                        "endpoint": "colrev.ops.built_in.search_sources.colrev_project.ColrevProjectSearchSource",
                        "installed": True,
                        "description": "Performs a search in a CoLRev project",
                    },
                    "local_index": {
                        "endpoint": "colrev.ops.built_in.search_sources.local_index.LocalIndexSearchSource",
                        "installed": True,
                        "description": "Performs a search in the LocalIndex",
                    },
                    "transport_research_international_documentation": {
                        "endpoint": "colrev.ops.built_in.search_sources.transport_research_international_documentation.TransportResearchInternationalDocumentation",
                        "installed": True,
                        "description": None,
                    },
                }

            return jsonify(discovered_packages)

        # pylint: disable=unused-argument
        @app.route("/api/getScriptDetails")
        def getScriptDetails():
            package_type_string = request.args.get("packageType")
            package_identifier = request.args.get("packageIdentifier")
            endpoint_version = request.args.get("endpointVersion")
            # package_type = colrev.env.package_manager.PackageType[package_type_string]
            # package_details = self.package_manager.get_package_details(
            #     package_type=package_type, package_identifier=package_identifier
            # )

            # TODO (GW): use endpoint_version

            if package_type_string != "search_source":
                # For testing:
                # Example: script_type="prescreen", script_name="scope_prescreen"
                # Returns:
                package_details = {
                    "name": "scope_prescreen",
                    "description": "Prescreens records based on predefined rules (scope)",
                    "parameters": {
                        "name": {"required": True, "type": "str"},
                        "TimeScopeFrom": {
                            "required": False,
                            "type": "int",
                            "tooltip": "Lower bound for the time scope",
                            "min": 1900,
                            "max": 2050,
                        },
                        "TimeScopeTo": {
                            "required": False,
                            "type": "int",
                            "tooltip": "Upper bound for the time scope",
                            "min": 1900,
                            "max": 2050,
                        },
                        "LanguageScope": {
                            "required": False,
                            "type": "typing.Optional[list]",
                            "tooltip": "Language scope",
                        },
                        "ExcludeComplementaryMaterials": {
                            "required": False,
                            "type": "bool",
                            "tooltip": "Whether complementary materials (coverpages etc.) are excluded",
                        },
                        "OutletInclusionScope": {
                            "required": False,
                            "type": "typing.Optional[dict]",
                            "tooltip": "Particular outlets that should be included (exclusively)",
                        },
                        "OutletExclusionScope": {
                            "required": False,
                            "type": "typing.Optional[dict]",
                            "tooltip": "Particular outlets that should be excluded",
                        },
                        "ENTRYTYPEScope": {
                            "required": False,
                            "type": "typing.Optional[list]",
                            "tooltip": "Particular ENTRYTYPEs that should be included (exclusively)",
                        },
                    },
                }

            if package_type_string == "search_source":
                # For testing:
                # Example: script_type="search_source", script_name="crossref"
                # Returns:
                package_details = {
                    "type": "object",
                    "required": [
                        "name",
                        "filename",
                        "search_type",
                        "source_name",
                        "source_identifier",
                        "search_parameters",
                        "load_conversion_script",
                    ],
                    "properties": {
                        "name": {"type": "string"},
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
                        "source_name": {"type": "string"},
                        "source_identifier": {"type": "string"},
                        "search_parameters": {"type": "object", "additionalProperties": {}},
                        "load_conversion_script": {
                            "type": "script_array",
                            "script_type": "load_conversion",
                        },
                        "comment": {"type": "string"},
                    },
                    "description": "Search source settings",
                    "$schema": "http://json-schema.org/draft-06/schema#",
                }

            return jsonify(package_details)

        @app.get("/shutdown")
        def shutdown():
            # TODO : when the user clicks on the "Create project" button,
            # the settings should be saved,
            # the webbrowser/window should be closed
            # and flask should be stopped:
            # https://stackoverflow.com/questions/15562446/how-to-stop-flask-application-without-using-ctrl-c
            return "Server shutting down..."

        self._open_browser()
        app.run(host="0.0.0.0", port="5000", debug=True, use_reloader=False)


def main() -> None:
    # dev
    se_instance = SettingsEditor()
    se_instance.open_settings_editor()

    # prod
    # review_manager = colrev.review_manager.ReviewManager()
    # se_instance = SettingsEditor(review_manager=review_manager)
    # se_instance.open_settings_editor()


if __name__ == "__main__":
    main()
