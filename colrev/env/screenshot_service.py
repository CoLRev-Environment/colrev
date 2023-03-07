#! /usr/bin/env python
"""Service creating screenshots from urls (online ENTRYTYPES)."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import docker
import requests
from docker.errors import DockerException

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record


class ScreenshotService:
    """Environment service for website screenshots"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.chrome_browserless_image = "browserless/chrome:latest"
        self.review_manager = review_manager
        self.review_manager.environment_manager.build_docker_image(
            imagename=self.chrome_browserless_image
        )

    def start_screenshot_service(self) -> None:
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

    def add_screenshot(
        self, *, record: colrev.record.Record, pdf_filepath: Path
    ) -> colrev.record.Record:
        """Add a PDF screenshot to the record"""

        if "url" not in record.data:
            return record

        urldate = datetime.today().strftime("%Y-%m-%d")

        json_val = {
            "url": record.data["url"],
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
                key="file",
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


if __name__ == "__main__":
    pass
