#! /usr/bin/env python
"""Service creating screenshots from urls (online ENTRYTYPES)."""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import docker
import requests

import colrev.env.environment_manager
import colrev.operation
import colrev.record


class ScreenshotService:
    def __init__(self) -> None:
        pass

    def start_screenshot_service(self) -> None:

        if self.screenshot_service_available():
            return

        environment_manager = colrev.env.environment_manager.EnvironmentManager()
        environment_manager.build_docker_images()

        chrome_browserless_image = (
            colrev.env.environment_manager.EnvironmentManager.docker_images[
                "browserless/chrome"
            ]
        )

        client = docker.from_env()

        running_containers = [
            str(container.image) for container in client.containers.list()
        ]
        if chrome_browserless_image not in running_containers:
            client.containers.run(
                chrome_browserless_image,
                ports={"3000/tcp": ("127.0.0.1", 3000)},
                auto_remove=True,
                detach=True,
            )

        i = 0
        while i < 45:
            if self.screenshot_service_available():
                break
            time.sleep(1)
            i += 1
        return

    def screenshot_service_available(self) -> bool:

        content_type_header = {"Content-type": "text/plain"}

        browserless_chrome_available = False
        try:
            ret = requests.get(
                "http://127.0.0.1:3000/",
                headers=content_type_header,
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

        ret = requests.post("http://127.0.0.1:3000/pdf", json=json_val)

        if 200 == ret.status_code:
            with open(pdf_filepath, "wb") as file:
                file.write(ret.content)

            record.update_field(
                key="file",
                value=str(pdf_filepath),
                source="browserless/chrome screenshot",
            )
            record.data.update(
                colrev_status=colrev.record.RecordState.rev_prescreen_included
            )
            record.update_field(
                key="urldate", value=urldate, source="browserless/chrome screenshot"
            )

        else:
            print(
                "URL screenshot retrieval error "
                f"{ret.status_code}/{record.data['url']}"
            )

        return record


if __name__ == "__main__":
    pass
