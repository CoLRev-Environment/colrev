#! /usr/bin/env python
"""Load conversion of ris, end, enl, copac, isi, med based on bibutils"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.LoadConversionPackageInterface)
@dataclass
class BibutilsLoader(JsonSchemaMixin):

    """Loads bibliography files (based on bibutils)
    Supports ris, end, enl, copac, isi, med"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["ris", "end", "enl", "copac", "isi", "med"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ):
        def bibutils_convert(script: str, data: str) -> str:

            if "xml2bib" == script:
                script = script + " -b -w -sk "
            else:
                script = script + " -i unicode "

            client = docker.APIClient()
            try:
                container = client.create_container("bibutils", script, stdin_open=True)
            except docker.errors.ImageNotFound as exc:
                raise colrev_exceptions.ImportException(
                    "Docker images for bibutils not found"
                ) from exc

            sock = client.attach_socket(
                container, params={"stdin": 1, "stdout": 1, "stderr": 1, "stream": 1}
            )
            client.start(container)

            # pylint: disable=protected-access
            sock._sock.send(data.encode())
            sock._sock.close()
            sock.close()

            client.wait(container)
            stdout = client.logs(container, stderr=False).decode()
            client.remove_container(container)

            return stdout

        with open(source.filename, encoding="utf-8") as reader:
            data = reader.read()

        filetype = Path(source.filename).suffix.replace(".", "")

        if filetype in ["enl", "end"]:
            data = bibutils_convert("end2xml", data)
        elif filetype in ["copac"]:
            data = bibutils_convert("copac2xml", data)
        elif filetype in ["isi"]:
            data = bibutils_convert("isi2xml", data)
        elif filetype in ["med"]:
            data = bibutils_convert("med2xml", data)
        elif filetype in ["ris"]:
            data = bibutils_convert("ris2xml", data)
        else:
            raise colrev_exceptions.ImportException(
                f"Filetype {filetype} not supported by bibutils"
            )

        data = bibutils_convert("xml2bib", data)

        records = load_operation.review_manager.dataset.load_records_dict(load_str=data)

        if source.source_name in load_operation.search_sources.packages:
            search_source_package = load_operation.search_sources.packages[
                source.source_name
            ]
            records = search_source_package.load_fixes(
                self, source=source, records=records
            )
        else:
            load_operation.review_manager.logger.info(
                "No custom source load_fixes for %s", source.source_name
            )
        return records


if __name__ == "__main__":
    pass
