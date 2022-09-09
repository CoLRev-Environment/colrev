#! /usr/bin/env python
from __future__ import annotations

import importlib
import json
import sys
import typing
from copy import deepcopy
from pathlib import Path

from zope.interface.verify import verifyObject

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record


class PackageManager:

    endpoint_overview = [
        {
            "process_type": colrev.process.ProcessType.search,
            "import_name": "SearchEndpoint",
            "custom_class": "CustomSearch",
            "operation_name": "search_operation",
        },
        {
            "process_type": colrev.process.ProcessType.load,
            "import_name": "LoadEndpoint",
            "custom_class": "CustomLoad",
            "operation_name": "load_operation",
        },
        {
            "process_type": colrev.process.ProcessType.check,
            "import_name": "SearchSourceEndpoint",
            "custom_class": "CustomSearchSource",
            "operation_name": "check_operation",
        },
        {
            "process_type": colrev.process.ProcessType.prep,
            "import_name": "PrepEndpoint",
            "custom_class": "CustomPrep",
            "operation_name": "prep_operation",
        },
        {
            "process_type": colrev.process.ProcessType.prep_man,
            "import_name": "PrepManEndpoint",
            "custom_class": "CustomPrepMan",
            "operation_name": "prep_man_operation",
        },
        {
            "process_type": colrev.process.ProcessType.dedupe,
            "import_name": "DedupeEndpoint",
            "custom_class": "CustomDedupe",
            "operation_name": "dedupe_operation",
        },
        {
            "process_type": colrev.process.ProcessType.prescreen,
            "import_name": "PrescreenEndpoint",
            "custom_class": "CustomPrescreen",
            "operation_name": "prescreen_operation",
        },
        {
            "process_type": colrev.process.ProcessType.pdf_get,
            "import_name": "PDFGetEndpoint",
            "custom_class": "CustomPDFGet",
            "operation_name": "pdf_get_operation",
        },
        {
            "process_type": colrev.process.ProcessType.pdf_get_man,
            "import_name": "PDFGetManEndpoint",
            "custom_class": "CustomPDFGetMan",
            "operation_name": "pdf_get_man_operation",
        },
        {
            "process_type": colrev.process.ProcessType.pdf_prep,
            "import_name": "PDFPrepEndpoint",
            "custom_class": "CustomPDFPrep",
            "operation_name": "pdf_prep_operation",
        },
        {
            "process_type": colrev.process.ProcessType.pdf_prep_man,
            "import_name": "PDFPrepManEndpoint",
            "custom_class": "CustomPDFPrepMan",
            "operation_name": "pdf_prep_man_operation",
        },
        {
            "process_type": colrev.process.ProcessType.screen,
            "import_name": "ScreenEndpoint",
            "custom_class": "CustomScreen",
            "operation_name": "screen_operation",
        },
        {
            "process_type": colrev.process.ProcessType.data,
            "import_name": "DataEndpoint",
            "custom_class": "CustomData",
            "operation_name": "data_operation",
        },
    ]

    package: typing.Dict[str, typing.Dict[str, typing.Dict]]

    def __init__(
        self,
    ) -> None:

        self.packages = self.load_package_index()
        self.__flag_installed_packages()

    def load_package_index(self):

        # TODO : the list of packages should be curated
        # (like CRAN: packages that meet *minimum* requirements)
        # We should not load any package that matches the colrev* on PyPI
        # (security/quality issues...)

        # We can start by using/updating the following dictionary/json-file.
        # At some point, we may decide to move it to a separate repo/index.

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/packages.json")
        )
        if not filedata:
            raise colrev_exceptions.CoLRevException(
                "Package index not available (colrev/template/packages.json)"
            )

        package_dict = json.loads(filedata.decode("utf-8"))

        # TODO : testing: validate the structure of packages.json
        # and whether all endpoints are available

        # Note : parsing to a dataclass may not have many advantages
        # because the discover_packages and load_packages access the
        # packages through strings anyway

        return package_dict

    def __flag_installed_packages(self) -> None:
        for script_type, package in self.packages.items():
            for script_name, discovered_package in package.items():
                try:
                    self.load_package_endpoint(
                        script_type=script_type, script_name=script_name
                    )
                    discovered_package["installed"] = True
                except (AttributeError, ModuleNotFoundError):
                    discovered_package["installed"] = False

    def discover_packages(
        self, *, script_type: str, installed_only: bool = False
    ) -> typing.Dict:

        discovered_packages = self.packages[script_type]
        if installed_only:
            discovered_packages = {
                script_name: package
                for script_name, package in discovered_packages.items()
                if package["installed"]
            }

        return discovered_packages

    def load_package_endpoint(self, *, script_type: str, script_name: str):
        package_str = self.packages[script_type][script_name]["endpoint"]
        script_module = package_str.rsplit(".", 1)[0]
        script_class = package_str.rsplit(".", 1)[-1]
        imported_package = importlib.import_module(script_module)
        package_class = getattr(imported_package, script_class)  # type: ignore
        return package_class

    def load_packages(
        self, *, process: colrev.process.Process, scripts: list, script_type: str = ""
    ) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=unnecessary-dict-index-lookup
        # Note : when iterating over script_dict.items(),
        # changes to the values (or del k) would not persist

        # TODO : generally change from process.type to script_name
        # (each process can involve different endpoints)

        if "" == script_type:
            script_type = str(process.type)

        # avoid changes in the config
        scripts = deepcopy(scripts)
        scripts_dict: typing.Dict = {}
        for script in scripts:
            script_name = script["endpoint"]
            scripts_dict[script_name] = {}

            # 1. Load built-in scripts
            # if script_name in cls.packages[process.type]
            if script_name in self.packages[script_type]:
                if self.packages[script_type][script_name]["installed"]:
                    scripts_dict[script_name]["settings"] = script
                    scripts_dict[script_name]["endpoint"] = self.load_package_endpoint(
                        script_type=script_type, script_name=script_name
                    )

            # 2. Load module scripts
            # TODO : test the module prep_scripts
            elif not Path(script_name + ".py").is_file():
                try:
                    scripts_dict[script_name]["settings"] = script
                    scripts_dict[script_name]["endpoint"] = importlib.import_module(
                        script_name
                    )
                    scripts_dict[script_name]["custom_flag"] = True
                except ModuleNotFoundError as exc:
                    raise colrev_exceptions.MissingDependencyError(
                        "Dependency " + f"{script_name} not found. "
                        "Please install it\n  pip install "
                        f"{script_name}"
                    ) from exc

            # 3. Load custom scripts in the directory
            elif Path(script_name + ".py").is_file():
                sys.path.append(".")  # to import custom scripts from the project dir
                scripts_dict[script_name]["settings"] = script
                scripts_dict[script_name]["endpoint"] = importlib.import_module(
                    script_name, "."
                )
                scripts_dict[script_name]["custom_flag"] = True
            else:
                print(f"Could not load {script}")
                continue
            scripts_dict[script_name]["settings"]["name"] = scripts_dict[script_name][
                "settings"
            ]["endpoint"]
            del scripts_dict[script_name]["settings"]["endpoint"]

        endpoint_details = next(
            item
            for item in self.endpoint_overview
            if item["process_type"] == process.type
        )

        for k, val in scripts_dict.items():
            if "custom_flag" in val:
                scripts_dict[k]["endpoint"] = getattr(  # type: ignore
                    val["endpoint"], endpoint_details["custom_class"]
                )
                del scripts_dict[k]["custom_flag"]

        endpoint_class = getattr(colrev.process, endpoint_details["import_name"])  # type: ignore
        for endpoint_name, script in scripts_dict.items():
            params = {
                endpoint_details["operation_name"]: process,
                "settings": script["settings"],
            }
            if "SearchSource" == script_type:
                del params["check_operation"]

            scripts_dict[endpoint_name] = script["endpoint"](**params)
            verifyObject(endpoint_class, scripts_dict[endpoint_name])

        return scripts_dict


if __name__ == "__main__":
    pass
