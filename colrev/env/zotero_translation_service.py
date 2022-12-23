#! /usr/bin/env python
"""Service translating between file formats (based on Zotero)."""
from __future__ import annotations

import time

import docker
import requests
from docker.errors import DockerException

import colrev.env.environment_manager
import colrev.exceptions as colrev_exceptions


class ZoteroTranslationService:
    """An environment service based on zotero translators"""

    def __init__(
        self, *, environment_manager: colrev.env.environment_manager.EnvironmentManager
    ) -> None:

        self.image_name = "zotero/translation-server:2.0.4"
        environment_manager.build_docker_image(imagename=self.image_name)

        self.__stop_zotero_if_running()
        if not self.zotero_service_available():
            environment_manager.register_ports(ports=["1969"])

    def __stop_zotero_if_running(self) -> None:
        # Note : the zotero docker service needs to be restarted every time...
        try:
            client = docker.from_env()
            for container in client.containers.list():
                if self.image_name in str(container.image):
                    container.stop()
        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Docker service not available ({exc}). Please install/start Docker."
            ) from exc

    def start_zotero_translators(
        self, *, startup_without_waiting: bool = False
    ) -> None:
        """Start the zotero translation service"""

        # pylint: disable=duplicate-code

        if self.zotero_service_available():
            return

        try:
            client = docker.from_env()
            _ = client.containers.run(
                self.image_name,
                ports={"1969/tcp": ("127.0.0.1", 1969)},
                auto_remove=True,
                detach=True,
            )

        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="Zotero (Docker)", detailed_trace=exc
            ) from exc

        if startup_without_waiting:
            return

        i = 0
        while i < 45:
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
                timeout=30,
            )
            if ret.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        return False


if __name__ == "__main__":
    pass
