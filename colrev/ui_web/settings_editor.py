#!/usr/bin/env python3
from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from threading import Timer
from typing import TYPE_CHECKING

from flask import Flask
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask_cors import CORS

import colrev.ops.load
import colrev.process
import colrev.settings

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class SettingsEditor:
    # pylint: disable=invalid-name

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager
        self.package_manager = review_manager.get_package_manager()
        self.settings_path: Path = self.review_manager.settings_path

        # For testing:
        # self.settings_path = Path.cwd()

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
            if create_commit:
                self.review_manager.create_commit(msg="Update settings")
            return "ok"

        @app.route("/api/getOptions")
        def getOptions():

            # Decision: get the whole list of setting_options (not individually)
            # "similarity": {'type': 'float', 'min': 0, 'max': 1}

            # options = {
            #     "$schema": "http://json-schema.org/draft-06/schema#",
            #     "definitions": {
            #         "Author": {
            #             "description": "Author of the review",
            #             "properties": {
            #                 "affiliations": {"type": "string"},
            #                 "contributions": {
            #                     "default": [],
            #                     "items": {"type": "string"},
            #                     "type": "array",
            #                 },
            #                 "email": {"type": "string"},
            #                 "funding": {
            #                     "default": [],
            #                     "items": {"type": "string"},
            #                     "type": "array",
            #                 },
            #                 "identifiers": {
            #                     "default": [],
            #                     "items": {"type": "string"},
            #                     "type": "array",
            #                 },
            #                 "initials": {"type": "string"},
            #                 "name": {"type": "string"},
            #                 "orcid": {"type": "string"},
            #             },
            #             "required": ["name", "initials", "email"],
            #             "type": "object",
            #         },
            #         "DataSettings": {
            #             "description": "Data settings",
            #             "properties": {
            #                 "scripts": {"script_type": "data", "type": "script_array"}
            #             },
            #             "required": ["scripts"],
            #             "type": "object",
            #         },
            #         "DedupeSettings": {
            #             "description": "Dedupe settings",
            #             "properties": {
            #                 "same_source_merges": {
            #                     "enum": ["prevent", "apply", "warn"],
            #                     "type": "string",
            #                 },
            #                 "scripts": {
            #                     "script_type": "dedupe",
            #                     "type": "script_array",
            #                 },
            #             },
            #             "required": ["same_source_merges", "scripts"],
            #             "type": "object",
            #         },
            #         "LoadSettings": {
            #             "description": "Load settings",
            #             "properties": {},
            #             "type": "object",
            #         },
            #         "PDFGetSettings": {
            #             "description": "PDF get settings",
            #             "properties": {
            #                 "man_pdf_get_scripts": {
            #                     "script_type": "pdf_get_man",
            #                     "type": "script_array",
            #                 },
            #                 "pdf_path_type": {
            #                     "enum": ["symlink", "copy"],
            #                     "type": "string",
            #                 },
            #                 "pdf_required_for_screen_and_synthesis": {
            #                     "type": "boolean"
            #                 },
            #                 "rename_pdfs": {"type": "boolean"},
            #                 "scripts": {
            #                     "script_type": "pdf_get",
            #                     "type": "script_array",
            #                 },
            #             },
            #             "required": [
            #                 "pdf_path_type",
            #                 "pdf_required_for_screen_and_synthesis",
            #                 "rename_pdfs",
            #                 "scripts",
            #                 "man_pdf_get_scripts",
            #             ],
            #             "type": "object",
            #         },
            #         "PDFPrepSettings": {
            #             "description": "PDF prep settings",
            #             "properties": {
            #                 "man_pdf_prep_scripts": {
            #                     "script_type": "pdf_prep_man",
            #                     "type": "script_array",
            #                 },
            #                 "scripts": {
            #                     "script_type": "pdf_prep",
            #                     "type": "script_array",
            #                 },
            #             },
            #             "required": ["scripts", "man_pdf_prep_scripts"],
            #             "type": "object",
            #         },
            #         "PrepRound": {
            #             "description": "Prep round settings",
            #             "properties": {
            #                 "name": {"type": "string"},
            #                 "scripts": {"type": "array"},
            #                 "similarity": {"type": "number"},
            #             },
            #             "required": ["name", "similarity", "scripts"],
            #             "type": "object",
            #         },
            #         "PrepSettings": {
            #             "description": "Prep settings",
            #             "properties": {
            #                 "PrepSettings": {
            #                     "script_type": "prep_man",
            #                     "type": "script_array",
            #                 },
            #                 "fields_to_keep": {
            #                     "items": {"type": "string"},
            #                     "type": "array",
            #                 },
            #                 "man_prep_scripts": {"type": "array"},
            #                 "prep_rounds": {
            #                     "items": {"$ref": "#/definitions/PrepRound"},
            #                     "type": "array",
            #                 },
            #             },
            #             "required": [
            #                 "fields_to_keep",
            #                 "prep_rounds",
            #                 "man_prep_scripts",
            #             ],
            #             "type": "object",
            #         },
            #         "PrescreenSettings": {
            #             "description": "Prescreen settings",
            #             "properties": {
            #                 "explanation": {"type": "string"},
            #                 "scripts": {
            #                     "script_type": "prescreen",
            #                     "type": "script_array",
            #                 },
            #             },
            #             "required": ["explanation", "scripts"],
            #             "type": "object",
            #         },
            #         "ProjectSettings": {
            #             "description": "Project settings",
            #             "properties": {
            #                 "authors": {
            #                     "items": {"$ref": "#/definitions/Author"},
            #                     "type": "array",
            #                 },
            #                 "colrev_version": {"type": "string"},
            #                 "curated_fields": {
            #                     "items": {"type": "string"},
            #                     "type": "array",
            #                 },
            #                 "curated_masterdata": {"type": "boolean"},
            #                 "curation_url": {"type": "string"},
            #                 "delay_automated_processing": {"type": "boolean"},
            #                 "id_pattern": {
            #                     "enum": ["first_author_year", "three_authors_year"],
            #                     "type": "string",
            #                 },
            #                 "keywords": {"items": {"type": "string"}, "type": "array"},
            #                 "protocol": {"$ref": "#/definitions/Protocol"},
            #                 "review_type": {
            #                     "enum": [
            #                         "curated_masterdata",
            #                         "realtime",
            #                         "literature_review",
            #                         "narrative_review",
            #                         "descriptive_review",
            #                         "scoping_review",
            #                         "critical_review",
            #                         "theoretical_review",
            #                         "conceptual_review",
            #                         "qualitative_systematic_review",
            #                         "meta_analysis",
            #                         "scientometric",
            #                         "peer_review",
            #                     ],
            #                     "type": "string",
            #                 },
            #                 "share_stat_req": {
            #                     "enum": ["none", "processed", "screened", "completed"],
            #                     "type": "string",
            #                 },
            #                 "title": {"type": "string"},
            #             },
            #             "required": [
            #                 "title",
            #                 "authors",
            #                 "keywords",
            #                 "review_type",
            #                 "id_pattern",
            #                 "share_stat_req",
            #                 "delay_automated_processing",
            #                 "curated_masterdata",
            #                 "curated_fields",
            #                 "colrev_version",
            #             ],
            #             "type": "object",
            #         },
            #         "Protocol": {
            #             "description": "Review protocol",
            #             "properties": {"url": {"type": "string"}},
            #             "required": ["url"],
            #             "type": "object",
            #         },
            #         "ScreenCriterion": {
            #             "description": "Screen criterion",
            #             "properties": {
            #                 "comment": {"type": "string"},
            #                 "criterion_type": {
            #                     "enum": ["inclusion_criterion", "exclusion_criterion"],
            #                     "type": "string",
            #                 },
            #                 "explanation": {"type": "string"},
            #             },
            #             "required": ["explanation", "criterion_type"],
            #             "type": "object",
            #         },
            #         "ScreenSettings": {
            #             "description": "Screen settings",
            #             "properties": {
            #                 "criteria": {
            #                     "additionalProperties": {
            #                         "$ref": "#/definitions/ScreenCriterion"
            #                     },
            #                     "type": "object",
            #                 },
            #                 "explanation": {"type": "string"},
            #                 "scripts": {
            #                     "script_type": "screen",
            #                     "type": "script_array",
            #                 },
            #             },
            #             "required": ["criteria", "scripts"],
            #             "type": "object",
            #         },
            #         "SearchSettings": {
            #             "description": "Search settings",
            #             "properties": {"retrieve_forthcoming": {"type": "boolean"}},
            #             "required": ["retrieve_forthcoming"],
            #             "type": "object",
            #         },
            #         "SearchSource": {
            #             "description": "Search source settings",
            #             "properties": {
            #                 "comment": {"type": "string"},
            #                 "conversion_script": {
            #                     "script_type": "conversion",
            #                     "type": "script_item",
            #                 },
            #                 "filename": {},
            #                 "search_parameters": {"type": "string"},
            #                 "search_script": {
            #                     "script_type": "search",
            #                     "type": "script_item",
            #                 },
            #                 "search_type": {
            #                     "enum": [
            #                         "DB",
            #                         "TOC",
            #                         "BACKWARD_SEARCH",
            #                         "FORWARD_SEARCH",
            #                         "PDFS",
            #                         "OTHER",
            #                     ],
            #                     "type": "string",
            #                 },
            #                 "source_identifier": {"type": "string"},
            #                 "source_name": {"type": "string"},
            #                 "source_prep_scripts": {
            #                     "script_type": "source_prep_script",
            #                     "type": "script_array",
            #                 },
            #             },
            #             "required": [
            #                 "filename",
            #                 "search_type",
            #                 "source_name",
            #                 "source_identifier",
            #                 "search_parameters",
            #                 "search_script",
            #                 "conversion_script",
            #                 "source_prep_scripts",
            #             ],
            #             "type": "object",
            #         },
            #     },
            #     "description": "CoLRev project settings",
            #     "properties": {
            #         "data": {"$ref": "#/definitions/DataSettings"},
            #         "dedupe": {"$ref": "#/definitions/DedupeSettings"},
            #         "load": {"$ref": "#/definitions/LoadSettings"},
            #         "pdf_get": {"$ref": "#/definitions/PDFGetSettings"},
            #         "pdf_prep": {"$ref": "#/definitions/PDFPrepSettings"},
            #         "prep": {"$ref": "#/definitions/PrepSettings"},
            #         "prescreen": {"$ref": "#/definitions/PrescreenSettings"},
            #         "project": {"$ref": "#/definitions/ProjectSettings"},
            #         "screen": {"$ref": "#/definitions/ScreenSettings"},
            #         "search": {"$ref": "#/definitions/SearchSettings"},
            #         "sources": {
            #             "items": {"$ref": "#/definitions/SearchSource"},
            #             "type": "array",
            #         },
            #     },
            #     "required": [
            #         "project",
            #         "sources",
            #         "search",
            #         "load",
            #         "prep",
            #         "dedupe",
            #         "prescreen",
            #         "pdf_get",
            #         "pdf_prep",
            #         "screen",
            #         "data",
            #     ],
            #     "type": "object",
            # }

            return jsonify(colrev.settings.Settings.get_settings_schema())

        @app.route("/api/getScripts")
        def getScripts(script_type):

            script_options = self.package_manager.discover_packages(
                script_type=script_type
            )

            # For testing:
            # Example: script_type="load"
            # Returns:
            # script_options = {
            #     "bibtex": {
            #         "endpoint": "colrev.ops.built_in.load.BibPybtexLoader",
            #         "installed": True,
            #     },
            #     "csv": {
            #         "endpoint": "colrev.ops.built_in.load.CSVLoader",
            #         "installed": True,
            #     },
            #     "excel": {
            #         "endpoint": "colrev.ops.built_in.load.ExcelLoader",
            #         "installed": True,
            #     },
            #     "zotero_translate": {
            #         "endpoint": "colrev.ops.built_in.load.ZoteroTranslationLoader",
            #         "installed": True,
            #     },
            #     "md_to_bib": {
            #         "endpoint": "colrev.ops.built_in.load.MarkdownLoader",
            #         "installed": True,
            #     },
            #     "bibutils": {
            #         "endpoint": "colrev.ops.built_in.load.BibutilsLoader",
            #         "installed": True,
            #     },
            # }

            return jsonify(script_options)

        # pylint: disable=unused-argument
        @app.route("/api/getScriptDetails")
        def getScriptDetails(script_type, script_name, endpoint_version):

            package_details = self.package_manager.get_package_details(
                script_type=script_type, script_name=script_name
            )

            # TODO (GW): use endpoint_version

            # For testing:
            # Example: script_type="prescreen", script_name="scope_prescreen"
            # Returns:
            # package_details = {
            #     "description": "Prescreens records based on predefined rules (scope)",
            #     "name": "scope_prescreen",
            #     "parameters": {
            #         "ENTRYTYPEScope": {
            #             "options": ["article", "booktitle"],
            #             "required": False,
            #             "tooltip": "Particular ENTRYTYPEs that should be included (exclusively)",
            #             "type": "typing.Optional[list]",
            #         },
            #         "TimeScopeFrom": {
            #             "max": 2050,
            #             "min": 1900,
            #             "required": False,
            #             "tooltip": "Lower bound for the time scope",
            #             "type": "int",
            #         },
            #         "TimeScopeTo": {
            #             "required": False,
            #             "tooltip": "Upper bound for the time scope",
            #             "type": "int",
            #         },
            #         "name": {"required": True, "type": "str"},
            #     },
            # }

            # Example: script_type="prescreen", script_name="spreadsheet_prescreen"
            # Returns:
            # package_details = {
            #     "description": "Prescreen based on a spreadsheet (exported and imported)",
            #     "name": "spreadsheet_prescreen",
            #     "parameters": {},
            # }

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
