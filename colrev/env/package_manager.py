#! /usr/bin/env python
from __future__ import annotations

import importlib
import sys
import typing
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

from zope.interface.verify import verifyObject

import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record


if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class PackageManager:
    # pylint: disable=too-few-public-methods

    @classmethod
    def load_packages(
        cls, *, process, scripts, script_type: str = ""
    ) -> typing.Dict[str, typing.Dict[str, typing.Any]]:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=unnecessary-dict-index-lookup
        # Note : when iterating over script_dict.items(),
        # changes to the values (or del k) would not persist

        # avoid changes in the config
        scripts = deepcopy(scripts)
        scripts_dict: typing.Dict = {}
        for script in scripts:
            script_name = script["endpoint"]
            scripts_dict[script_name] = {}

            # 1. Load built-in scripts
            if script_name in process.built_in_scripts:
                scripts_dict[script_name]["settings"] = script
                scripts_dict[script_name]["endpoint"] = process.built_in_scripts[
                    script_name
                ]["endpoint"]

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
            {
                "process_type": colrev.process.ProcessType.data,
                "import_name": "DataEndpoint",
                "custom_class": "CustomData",
                "operation_name": "data_operation",
            },
        ]

        endpoint_details = next(
            item for item in endpoint_overview if item["process_type"] == process.type
        )

        for k, val in scripts_dict.items():
            if "custom_flag" in val:
                # scripts_dict[k]["endpoint"] = val["endpoint"].CustomSearch
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
            # scripts_dict[endpoint_name] = script["endpoint"](
            #     search_operation=process, settings=script["settings"]
            # )
            verifyObject(endpoint_class, scripts_dict[endpoint_name])

        return scripts_dict


if __name__ == "__main__":
    pass
