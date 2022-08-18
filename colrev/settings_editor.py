#!/usr/bin/env python3
import json
from pathlib import Path

from flask import Flask
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask_cors import CORS

import colrev.load
import colrev.process
import colrev.settings


class Settings(colrev.process.Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev.process.ProcessType.explore,
        )

    def _open_browser(self) -> None:

        import webbrowser
        from threading import Timer

        url = "http://127.0.0.1:5000"

        Timer(1, lambda: webbrowser.open_new(url)).start()
        print(f"Open at {url}")

    def open_settings_editor(self):

        SETTINGS_FILE_PATH = self.REVIEW_MANAGER.path / Path("settings.json")

        app = Flask(__name__, static_url_path="", static_folder="frontend/build")
        CORS(app)

        app.config["path"] = str(self.REVIEW_MANAGER.path / Path("settings.json"))

        # print("Settings File Path: ", app.config["path"])

        @app.route("/", defaults={"path": ""})
        def serve(path):
            return send_from_directory(app.static_folder, "index.html")

        @app.route("/<path:filename>")
        def base_static(filename):
            return send_from_directory(app.root_path + "/", filename)

        @app.route("/api/getSettings")
        def getSettings():

            with open(SETTINGS_FILE_PATH, encoding="utf-8") as file:
                json__content = file.read()

            response = app.response_class(
                response=json__content, mimetype="application/json"
            )

            return response

        @app.route("/api/saveSettings", methods=["POST"])
        def saveSettings():

            with open(SETTINGS_FILE_PATH, "w", encoding="utf-8") as outfile:
                json_string = json.dumps(request.json, indent=4)
                outfile.write(json_string)

            return "ok"

        @app.route("/api/getOptions")
        def getOptions():

            # Decision: get the whole list of setting_options (not individually)
            # "similarity": {'type': 'flot', 'min': 0, 'max': 1}

            # setting_options = {
            #     "project": {
            #         "review_type": colrev.settings.ReviewType.getOptions(),
            #         "id_pattern": colrev.settings.IDPpattern.getOptions(),
            #     },
            # }

            return jsonify(colrev.settings.Configuration.getOptions())

        @app.route("/api/getTootip")
        def getTootip():

            # TODO : develop
            # Note: do not include cases where we don't need tooltips
            setting_tooltips = {
                "project": {"review_type": "This is the type of review"},
            }
            return jsonify(setting_tooltips)

        @app.route("/api/getRequired")
        def getRequired():

            # TODO: add documentation/comments
            setting_required = {
                "project": {"review_type": True},
            }
            return jsonify(setting_required)

        @app.route("/api/getScripts")
        def getScripts(script_type):
            script_options = []
            if "source_conversion_script" == script_type:
                script_options = list(colrev.load.Loader.built_in_scripts.keys())

            if "prep_script" == script_type:
                # TODO : generate list based on script discovery
                script_options = [
                    {
                        "endpoint": "crossref_prep",
                        "description": "The script retrieves metadata from Crossref ...",
                    }
                ]

            return jsonify(script_options)

        @app.route("/api/getScriptsParametersOptions")
        def getScriptsParametersOptions(script_type, endpoint_name, endpoint_version):
            # TODO : generate based on script discovery
            if "prep_script" == script_type:
                if "crossref_prep" == endpoint_name:
                    if "1.0.0" == endpoint_version:
                        script_options = {
                            "retrieval_similarity": {"type": "flot", "min": 0, "max": 1}
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

        self._open_browser()
        app.run(host="0.0.0.0", port="5000", debug=True, use_reloader=False)
