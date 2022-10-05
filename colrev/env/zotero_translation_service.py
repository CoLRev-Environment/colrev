#! /usr/bin/env python
"""Service translating between file formats (based on Zotero)."""
from __future__ import annotations

import time

import docker
import requests
from docker.errors import APIError

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions


class ZoteroTranslationService:
    def __init__(self) -> None:
        pass

    def start_zotero_translators(
        self, *, startup_without_waiting: bool = False
    ) -> None:
        """Start the zotero translation service"""

        if self.zotero_service_available():
            return

        zotero_image = colrev.env.environment_manager.EnvironmentManager.docker_images[
            "zotero/translation-server"
        ]

        client = docker.from_env()
        for container in client.containers.list():
            if zotero_image in str(container.image):
                return
        try:
            container = client.containers.run(
                zotero_image,
                ports={"1969/tcp": ("127.0.0.1", 1969)},
                auto_remove=True,
                detach=True,
            )
        except APIError:
            pass

        if startup_without_waiting:
            return

        i = 0
        while i < 45:
            print("check")
            if self.zotero_service_available():
                return
            time.sleep(1)
            i += 1
        raise colrev_exceptions.ServiceNotAvailableException(
            "Zotero translators (docker) not available"
        )

    def zotero_service_available(self) -> bool:
        """Check whether the zotero translation service is available"""

        url = "https://www.sciencedirect.com/science/article/abs/pii/S096386872100041X"
        content_type_header = {"Content-type": "text/plain"}
        try:
            ret = requests.post(
                "http://127.0.0.1:1969/web",
                headers=content_type_header,
                data=url,
            )
            if ret.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        return False


if __name__ == "__main__":
    pass
