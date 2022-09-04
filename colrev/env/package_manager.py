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

        if colrev.process.ProcessType.search == process.type:
            from colrev.process import SearchEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomSearch
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    search_operation=process, settings=script["settings"]
                )
                verifyObject(SearchEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.load == process.type:
            from colrev.process import LoadEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomLoad
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    load_operation=process, settings=script["settings"]
                )
                verifyObject(LoadEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.prep == process.type:
            from colrev.process import PrepEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPrep
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    prep_operation=process, settings=script["settings"]
                )
                verifyObject(PrepEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.prep_man == process.type:
            from colrev.process import PrepManEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPrepMan
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    prep_man_operation=process, settings=script["settings"]
                )
                verifyObject(PrepManEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.dedupe == process.type:
            from colrev.process import DedupeEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomDedupe
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    dedupe_operation=process, settings=script["settings"]
                )
                verifyObject(DedupeEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.prescreen == process.type:
            from colrev.process import PrescreenEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPrescreen
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    prescreen_operation=process, settings=script["settings"]
                )
                verifyObject(PrescreenEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_get == process.type:
            from colrev.process import PDFGetEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFGet
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_get_operation=process, settings=script["settings"]
                )
                verifyObject(PDFGetEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_get_man == process.type:
            from colrev.process import PDFGetManEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFGetMan
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_get_man_operation=process, settings=script["settings"]
                )
                verifyObject(PDFGetManEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_prep == process.type:
            from colrev.process import PDFPrepEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFPrep
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_prep_operation=process, settings=script["settings"]
                )
                verifyObject(PDFPrepEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.pdf_prep_man == process.type:
            from colrev.process import PDFPrepManEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomPDFPrepMan
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    pdf_prep_man_operation=process, settings=script["settings"]
                )
                verifyObject(PDFPrepManEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.screen == process.type:
            from colrev.process import ScreenEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomScreen
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    screen_operation=process, settings=script["settings"]
                )
                verifyObject(ScreenEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.data == process.type:
            from colrev.process import DataEndpoint

            for k, val in scripts_dict.items():
                if "custom_flag" in val:
                    scripts_dict[k]["endpoint"] = val["endpoint"].CustomData
                    del scripts_dict[k]["custom_flag"]

            for endpoint_name, script in scripts_dict.items():
                scripts_dict[endpoint_name] = script["endpoint"](
                    data_operation=process, settings=script["settings"]
                )
                verifyObject(DataEndpoint, scripts_dict[endpoint_name])

        elif colrev.process.ProcessType.check == process.type:
            if "SearchSource" == script_type:
                from colrev.process import SearchSourceEndpoint

                for k, val in scripts_dict.items():
                    if "custom_flag" in val:
                        scripts_dict[k]["endpoint"] = val["endpoint"].CustomSearchSource
                        del scripts_dict[k]["custom_flag"]

                for endpoint_name, script in scripts_dict.items():
                    scripts_dict[endpoint_name] = script["endpoint"](
                        settings=script["settings"]
                    )
                    verifyObject(SearchSourceEndpoint, scripts_dict[endpoint_name])
            else:
                print(
                    f"ERROR: process type not implemented: {process.type}/{script_type}"
                )

        else:
            print(f"ERROR: process type not implemented: {process.type}")

        return scripts_dict
