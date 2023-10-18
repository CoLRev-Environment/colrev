#! /usr/bin/env python
"""Creation of screenshots (PDFs) for online ENTRYTYPES"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from docker.errors import DockerException

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.record
from colrev.constants import Fields

# pylint: disable=duplicate-code

if TYPE_CHECKING:
    import colrev.ops.pdf_get

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PDFGetPackageEndpointInterface)
@dataclass
class WebsiteScreenshot(JsonSchemaMixin):
    """Get PDFs from website screenshot (for "online" ENTRYTYPES)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self,
        *,
        pdf_get_operation: colrev.ops.pdf_get.PDFGet,
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.chrome_browserless_image = "browserless/chrome:latest"
        self.review_manager = pdf_get_operation.review_manager
        self.review_manager.environment_manager.build_docker_image(
            imagename=self.chrome_browserless_image
        )

    def get_pdf(
        self, pdf_get_operation: colrev.ops.pdf_get.PDFGet, record: colrev.record.Record
    ) -> colrev.record.Record:
        """Get a PDF of the website (screenshot)"""

        if record.data[Fields.ENTRYTYPE] != "online":
            return record

        self.__start_screenshot_service()

        pdf_filepath = pdf_get_operation.review_manager.PDF_DIR_RELATIVE / Path(
            f"{record.data['ID']}.pdf"
        )
        record = self.__add_screenshot(record=record, pdf_filepath=pdf_filepath)

        if Fields.FILE in record.data:
            pdf_get_operation.import_pdf(record=record)

        return record

    def __start_screenshot_service(self) -> None:
        """Start the screenshot service"""

        # pylint: disable=duplicate-code

        if self.screenshot_service_available():
            return

        self.review_manager.environment_manager.register_ports(ports=["3000"])

        try:
            client = docker.from_env()

            running_containers = [
                str(container.image) for container in client.containers.list()
            ]
            if self.chrome_browserless_image not in running_containers:
                client.containers.run(
                    self.chrome_browserless_image,
                    ports={"3000/tcp": ("127.0.0.1", 3000)},
                    auto_remove=True,
                    detach=True,
                )
        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Docker service not available ({exc}). Please install/start Docker."
            ) from exc

        i = 0
        while i < 45:
            if self.screenshot_service_available():
                break
            time.sleep(1)
            i += 1
        return

    def screenshot_service_available(self) -> bool:
        """Check if the screenshot service is available"""

        content_type_header = {"Content-type": "text/plain"}

        browserless_chrome_available = False
        try:
            ret = requests.get(
                "http://127.0.0.1:3000/",
                headers=content_type_header,
                timeout=30,
            )
            browserless_chrome_available = ret.status_code == 200

        except requests.exceptions.ConnectionError:
            pass

        if browserless_chrome_available:
            return True
        return False

    def __add_screenshot(
        self, *, record: colrev.record.Record, pdf_filepath: Path
    ) -> colrev.record.Record:
        """Add a PDF screenshot to the record"""

        if Fields.URL not in record.data:
            return record

        urldate = datetime.today().strftime("%Y-%m-%d")

        json_val = {
            Fields.URL: record.data[Fields.URL],
            "options": {
                "displayHeaderFooter": True,
                "printBackground": False,
                "format": "A2",
            },
        }

        ret = requests.post("http://127.0.0.1:3000/pdf", json=json_val, timeout=30)

        if 200 == ret.status_code:
            with open(pdf_filepath, "wb") as file:
                file.write(ret.content)

            record.update_field(
                key=Fields.FILE,
                value=str(pdf_filepath),
                source="chrome (browserless) screenshot",
            )
            record.data.update(
                colrev_status=colrev.record.RecordState.rev_prescreen_included
            )
            record.update_field(
                key="urldate", value=urldate, source="chrome (browserless) screenshot"
            )

        else:
            print(
                "URL screenshot retrieval error "
                f"{ret.status_code}/{record.data['url']}"
            )

        return record
