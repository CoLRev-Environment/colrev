#! /usr/bin/env python
"""Service translating between file formats (based on Zotero)."""
from __future__ import annotations

import time

import docker
import requests
from docker.errors import DockerException

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions

# https://github.com/zotero/translators/
# https://www.zotero.org/support/dev/translators
# https://github.com/zotero/translation-server/blob/master/src/formats.js


class ZoteroTranslationService:
    """An environment service based on zotero translators"""

    def __init__(
        self, *, environment_manager: colrev.env.environment_manager.EnvironmentManager
    ) -> None:
        self.image_name = "zotero/translation-server:2.0.4"
        environment_manager.build_docker_image(imagename=self.image_name)

    def stop(self) -> None:
        """Stop the zotero translation service"""

        try:
            client = docker.from_env()
            for container in client.containers.list():
                if self.image_name in str(container.image):
                    container.stop()
        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="Zotero (Docker)", detailed_trace=exc
            ) from exc

    def start(self) -> None:
        """Start the zotero translation service"""

        # pylint: disable=duplicate-code

        try:
            self.stop()

            client = docker.from_env()
            _ = client.containers.run(
                self.image_name,
                ports={"1969/tcp": ("127.0.0.1", 1969)},
                auto_remove=True,
                detach=True,
            )

            tries = 0
            while tries < 10:
                try:
                    headers = {"Content-type": "text/plain"}
                    requests.post(
                        "http://127.0.0.1:1969/import",
                        headers=headers,
                        data=b"%T Paper title\n\n",
                        timeout=10,
                    )

                except requests.ConnectionError:
                    time.sleep(5)
                    continue
                return

            raise colrev_exceptions.ServiceNotAvailableException(
                dep="Zotero (Docker)", detailed_trace=""
            )

        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="Zotero (Docker)", detailed_trace=exc
            ) from exc


if __name__ == "__main__":
    pass
