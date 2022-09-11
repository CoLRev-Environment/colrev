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

            # setting_options = {
            #     "project": {
            #         "review_type": colrev.settings.ReviewType.getOptions(),
            #         "id_pattern": colrev.settings.IDPpattern.getOptions(),
            #     },
            # }

            # options = {
            #     "project": {
            #         "title": "str",
            #         "authors": [
            #             {
            #                 "name": "str",
            #                 "initials": "str",
            #                 "email": "str",
            #                 "orcid": ["str", "optional"],
            #                 "contributions": [[], "optional"],
            #                 "affiliations": [[], "optional"],
            #                 "funding": [[], "optional"],
            #                 "identifiers": [[], "optional"],
            #             }
            #         ],
            #         "keywords": ["str"],
            #         "protocol": [{"url": "str"}, "optional"],
            #         "review_type": [
            #             "curated_masterdata",
            #             "realtime",
            #             "literature_review",
            #             "narrative_review",
            #             "descriptive_review",
            #             "scoping_review",
            #             "critical_review",
            #             "theoretical_review",
            #             "conceptual_review",
            #             "qualitative_systematic_review",
            #             "meta_analysis",
            #             "scientometric",
            #             "peer_review",
            #         ],
            #         "id_pattern": ["first_author_year", "three_authors_year"],
            #         "share_stat_req": ["none", "processed", "screened", "completed"],
            #         "delay_automated_processing": "bool",
            #         "curation_url": ["str", "optional"],
            #         "curated_masterdata": "bool",
            #         "curated_fields": ["str"],
            #         "colrev_version": "str",
            #     },
            #     "sources": {},
            #     "search": {"retrieve_forthcoming": "bool"},
            #     "load": {},
            #     "prep": {
            #         "fields_to_keep": ["str"],
            #         "prep_rounds": [
            #             {"name": "str", "similarity": "float", "scripts": []}
            #         ],
            #         "man_prep_scripts": [],
            #     },
            #     "dedupe": {
            #         "same_source_merges": ["prevent", "apply", "warn"],
            #         "scripts": [],
            #     },
            #     "prescreen": {"explanation": "str", "scripts": []},
            #     "pdf_get": {
            #         "pdf_path_type": "str",
            #         "pdf_required_for_screen_and_synthesis": "bool",
            #         "rename_pdfs": "bool",
            #         "scripts": [],
            #         "man_pdf_get_scripts": [],
            #     },
            #     "pdf_prep": {"scripts": [], "man_pdf_prep_scripts": []},
            #     "screen": {
            #         "explanation": ["str", "optional"],
            #         "criteria": {
            #             "str": {
            #                 "explanation": "str",
            #                 "comment": ["str", "optional"],
            #                 "criterion_type": [
            #                     "inclusion_criterion",
            #                     "exclusion_criterion",
            #                 ],
            #             }
            #         },
            #         "scripts": [],
            #     },
            #     "data": {"scripts": []},
            # }

            # options = {
            #     "data": {
            #         "properties": {
            #             "scripts": {
            #                 "list": True,
            #                 "script_type": "data",
            #                 "type": "script_multiple_selector",
            #             }
            #         },
            #         "type": "object",
            #     },
            #     "dedupe": {
            #         "properties": {
            #             "same_source_merges": {
            #                 "options": ["prevent", "apply", "warn"],
            #                 "tooltip": "Policy for applying merges within the same search source",
            #                 "type": "selection",
            #             },
            #             "scripts": {
            #                 "list": True,
            #                 "script_type": "dedupe",
            #                 "type": "script_multiple_selector",
            #             },
            #         },
            #         "type": "object",
            #     },
            #     "load": {"properties": {}, "type": "object"},
            #     "pdf_get": {
            #         "properties": {
            #             "man_pdf_get_scripts": {
            #                 "list": True,
            #                 "script_type": "pdf_get_man",
            #                 "type": "script_multiple_selector",
            #             },
            #             "pdf_path_type": {
            #                 "options": ["symlink", "copy"],
            #                 "tooltip": "Policy for handling PDFs (create symlinks or copy files)",
            #                 "type": "selection",
            #             },
            #             "pdf_required_for_screen_and_synthesis": {"type": "bool"},
            #             "rename_pdfs": {"type": "bool"},
            #             "scripts": {
            #                 "list": True,
            #                 "script_type": "pdf_get",
            #                 "type": "script_multiple_selector",
            #             },
            #         },
            #         "type": "object",
            #     },
            #     "pdf_prep": {
            #         "properties": {
            #             "man_pdf_prep_scripts": {
            #                 "list": True,
            #                 "script_type": "pdf_prep_man",
            #                 "type": "script_multiple_selector",
            #             },
            #             "scripts": {
            #                 "list": True,
            #                 "script_type": "pdf_prep",
            #                 "type": "script_multiple_selector",
            #             },
            #         },
            #         "type": "object",
            #     },
            #     "prep": {
            #         "properties": {
            #             "fields_to_keep": {"list": True, "type": "str"},
            #             "man_prep_scripts": {
            #                 "list": True,
            #                 "script_type": "prep_man",
            #                 "type": "script_multiple_selector",
            #             },
            #             "prep_rounds": {
            #                 "list": True,
            #                 "properties": {
            #                     "name": {"type": "str"},
            #                     "scripts": {
            #                         "list": True,
            #                         "script_type": "prep",
            #                         "type": "script_multiple_selector",
            #                     },
            #                     "similarity": {"type": "float"},
            #                 },
            #                 "type": "object",
            #             },
            #         },
            #         "type": "object",
            #     },
            #     "prescreen": {
            #         "properties": {
            #             "explanation": {"type": "str"},
            #             "scripts": {
            #                 "list": True,
            #                 "script_type": "prescreen",
            #                 "type": "script_multiple_selector",
            #             },
            #         },
            #         "type": "object",
            #     },
            #     "project": {
            #         "properties": {
            #             "authors": {
            #                 "list": True,
            #                 "properties": {
            #                     "affiliations": {"type": "str"},
            #                     "contributions": {"list": True, "type": "str"},
            #                     "email": {"type": "str"},
            #                     "funding": {"list": True, "type": "str"},
            #                     "identifiers": {"list": True, "type": "str"},
            #                     "initials": {"type": "str"},
            #                     "name": {"type": "str"},
            #                     "orcid": {"type": "str"},
            #                 },
            #                 "type": "object",
            #             },
            #             "colrev_version": {"type": "str"},
            #             "curated_fields": {"list": True, "type": "str"},
            #             "curated_masterdata": {"type": "bool"},
            #             "curation_url": {"type": "str"},
            #             "delay_automated_processing": {"type": "bool"},
            #             "id_pattern": {
            #                 "options": ["first_author_year", "three_authors_year"],
            #                 "tooltip": "The pattern for generating record IDs",
            #                 "type": "selection",
            #             },
            #             "keywords": {"list": True, "type": "str"},
            #             "protocol": {"type": {"url": {"type": "str"}}},
            #             "review_type": {
            #                 "options": [
            #                     "curated_masterdata",
            #                     "realtime",
            #                     "literature_review",
            #                     "narrative_review",
            #                     "descriptive_review",
            #                     "scoping_review",
            #                     "critical_review",
            #                     "theoretical_review",
            #                     "conceptual_review",
            #                     "qualitative_systematic_review",
            #                     "meta_analysis",
            #                     "scientometric",
            #                     "peer_review",
            #                 ],
            #                 "tooltip": "The type of review",
            #                 "type": "selection",
            #             },
            #             "share_stat_req": {
            #                 "options": ["none", "processed", "screened", "completed"],
            #                 "tooltip": "Record status requirements for sharing",
            #                 "type": "selection",
            #             },
            #             "title": {"tooltip": "The title of the review", "type": "str"},
            #         },
            #         "type": "object",
            #     },
            #     "screen": {
            #         "properties": {
            #             "criteria": {
            #                 "custom_dict_key": {
            #                     "comment": {"type": "str"},
            #                     "criterion_type": {
            #                         "options": [
            #                             "inclusion_criterion",
            #                             "exclusion_criterion",
            #                         ],
            #                         "tooltip": "Type of screening criterion",
            #                         "type": "selection",
            #                     },
            #                     "explanation": {"type": "str"},
            #                 }
            #             },
            #             "explanation": {"type": "str"},
            #             "scripts": {
            #                 "list": True,
            #                 "script_type": "screen",
            #                 "type": "script_multiple_selector",
            #             },
            #         },
            #         "type": "object",
            #     },
            #     "search": {
            #         "properties": {"retrieve_forthcoming": {"type": "bool"}},
            #         "type": "object",
            #     },
            #     "sources": {
            #         "properties": {
            #             "conversion_script": {
            #                 "list": False,
            #                 "script_type": "conversion",
            #                 "type": "script_selector",
            #             },
            #             "list": True,
            #             "properties": {
            #                 "comment": {"type": "str"},
            #                 "conversion_script": {"properties": {}},
            #                 "filename": {"type": "Path"},
            #                 "search_parameters": {"type": "str"},
            #                 "search_script": {"properties": {}},
            #                 "search_type": {
            #                     "options": [
            #                         "DB",
            #                         "TOC",
            #                         "BACKWARD_SEARCH",
            #                         "FORWARD_SEARCH",
            #                         "PDFS",
            #                         "OTHER",
            #                     ],
            #                     "tooltip": "Type of search source",
            #                     "type": "selection",
            #                 },
            #                 "source_identifier": {"type": "str"},
            #                 "source_name": {"type": "str"},
            #                 "source_prep_scripts": {"properties": "List"},
            #             },
            #             "search_script": {
            #                 "list": False,
            #                 "script_type": "search",
            #                 "type": "script_selector",
            #             },
            #             "source_prep_scripts": {
            #                 "list": True,
            #                 "script_type": "source_prep_script",
            #                 "type": "script_multiple_selector",
            #             },
            #             "type": "object",
            #         },
            #         "type": "object",
            #     },
            # }

            return jsonify(colrev.settings.Configuration.get_settings_schema())

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
