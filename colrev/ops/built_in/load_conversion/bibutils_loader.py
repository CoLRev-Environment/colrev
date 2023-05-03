#! /usr/bin/env python
"""Load conversion of ris, end, enl, copac, isi, med based on bibutils"""
from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

import docker
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from docker.errors import DockerException

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class BibutilsLoader(JsonSchemaMixin):

    """Loads bibliography files (based on bibutils)
    Supports ris, end, enl, copac, isi, med"""

    settings_class = colrev.env.package_manager.DefaultSettings

    ci_supported: bool = True

    supported_extensions = ["ris", "end", "enl", "copac", "isi", "med"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)

        # if not load_operation.review_manager.in_ci_environment():
        self.bibutils_image = "colrev/bibutils:latest"
        load_operation.review_manager.environment_manager.build_docker_image(
            imagename=self.bibutils_image
        )

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        def bibutils_convert(script: str, data: str) -> str:
            if script == "xml2bib":
                script = script + " -b -w -sk "
            else:
                script = script + " -i unicode "

            try:
                client = docker.APIClient()
                container = client.create_container(
                    "colrev/bibutils", script, stdin_open=True
                )
            except docker.errors.ImageNotFound as exc:
                raise colrev_exceptions.ImportException(
                    "Docker images for bibutils not found"
                ) from exc
            except DockerException as exc:
                raise colrev_exceptions.ServiceNotAvailableException(
                    f"Docker service not available ({exc}). Please install/start Docker."
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

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[asdict(source)],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )

        return records


if __name__ == "__main__":
    pass
