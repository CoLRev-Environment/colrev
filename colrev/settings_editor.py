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

        print("Settings File Path: ", app.config["path"])

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

            # TODO : get options individually (path as a parameter of getOptions)
            # TODO : add getRequiredFields() (e.g., title, ...)
            setting_options = {
                "project": {
                    "review_type": colrev.settings.ReviewType.get_options(),
                    "id_pattern": colrev.settings.IDPpattern.get_options(),
                },
            }

            return jsonify(setting_options)

        @app.route("/api/getScripts")
        def getScripts(script_type):
            script_options = []
            if "source_conversion_script" == script_type:
                script_options = list(colrev.load.Loader.built_in_scripts.keys())

            return jsonify(script_options)

        self._open_browser()
        app.run(host="0.0.0.0", port="5000", debug=True, use_reloader=False)
