#!/usr/bin/env python3
"""Web-UI editor for CoLRev project settings"""
from __future__ import annotations

import json
import os
import signal
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask
from flask import jsonify
from flask import request
from flask import Response
from flask import send_from_directory
from flask_cors import CORS

import colrev.env.package_manager
import colrev.review_manager
import colrev.settings


class SettingsEditor:
    """A web-based editor for CoLRev settings"""

    # pylint: disable=invalid-name
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods

    settings_path: Path
    review_manager: colrev.review_manager.ReviewManager

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:

        self.review_manager = review_manager
        self.package_manager = self.review_manager.get_package_manager()
        self.settings_path = self.review_manager.settings_path

        # Note : no need for default values (they are already inserted before by the template setup)

    def _open_browser(self) -> None:

        url = "http://127.0.0.1:5000"

        Timer(1, lambda: webbrowser.open_new(url)).start()
        print(f"Open at {url}")

    def open_settings_editor(self) -> None:
        """Open the settings editor"""

        app = Flask(__name__, static_url_path="", static_folder="build")
        CORS(app)

        app.config["path"] = str(self.settings_path)

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

            with open(self.settings_path, "w", encoding="utf-8") as outfile:
                json_string = json.dumps(request.json, indent=4)
                outfile.write(json_string)
            if commit_selected:
                self.review_manager.dataset.add_changes(path=self.settings_path)
                self.review_manager.create_commit(msg="Update settings")

            return "ok"

        @app.route("/api/getOptions")
        def getOptions() -> Response:

            # Decision: get the whole list of setting_options (not individually)
            # "similarity": {'type': 'float', 'min': 0, 'max': 1}
            options = self.review_manager.settings.get_settings_schema()

            return jsonify(options)

        @app.route("/api/getPackages")
        def getPackages() -> Response:
            package_type_string = request.args.get("PackageEndpointType")

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
            # endpoint_version = request.args.get("EndpointVersion")

            package_type = colrev.env.package_manager.PackageEndpointType[
                package_type_string
            ]
            package_details = self.package_manager.get_package_details(
                package_type=package_type, package_identifier=package_identifier
            )

            return jsonify(package_details)

        @app.get("/api/shutdown")
        def shutdown() -> str:
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

    review_manager = colrev.review_manager.ReviewManager()
    se_instance = SettingsEditor(review_manager=review_manager)
    se_instance.open_settings_editor()


if __name__ == "__main__":
    main()
