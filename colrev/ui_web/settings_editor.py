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

            return jsonify(colrev.settings.Configuration.get_options())

        @app.route("/api/getTootip")
        def getTootip():

            # Note: do not include cases where we don't need tooltips

            # setting_tooltips = {
            #     "project": {"review_type": "This is the type of review"},
            # }

            return jsonify(colrev.settings.Configuration.get_tooltips())

        @app.route("/api/getRequired")
        def getRequired():

            # TODO: add documentation/comments
            setting_required = {
                "project": {"review_type": True},
            }
            return jsonify(setting_required)

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

        @app.route("/api/getScriptsParametersOptions")
        def getScriptsParametersOptions(script_type, endpoint_name, endpoint_version):
            # TODO : generate based on script discovery
            if "prep_script" == script_type:
                if "crossref_prep" == endpoint_name:
                    if "1.0.0" == endpoint_version:
                        script_options = {
                            "retrieval_similarity": {
                                "type": "float",
                                "min": 0,
                                "max": 1,
                            }
                        }
            return jsonify(script_options)

        @app.route("/api/getScriptsParametersTooltip")
        def getScriptsParametersTooltip(script_type, endpoint_name, endpoint_version):
            # TODO : generate based on script discovery
            if "prep_script" == script_type:
                if "crossref_prep" == endpoint_name:
                    if "1.0.0" == endpoint_version:
                        script_tooltip = {
                            "retrieval_similarity": "The similarity threshold for matching records."
                        }
            return jsonify(script_tooltip)

        @app.route("/api/getScriptsParametersRequired")
        def getScriptsParametersRequired(script_type, endpoint_name, endpoint_version):
            # TODO : generate based on script discovery
            if "prep_script" == script_type:
                if "crossref_prep" == endpoint_name:
                    if "1.0.0" == endpoint_version:
                        script_required = {"retrieval_similarity": True}
            return jsonify(script_required)

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
