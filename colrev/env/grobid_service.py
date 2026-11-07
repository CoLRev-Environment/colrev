#! /usr/bin/env python
"""GROBID service to extract and annotate PDF contents."""

from __future__ import annotations

import logging
import time

import docker
import requests

import colrev.env.docker_manager

LOGGER = logging.getLogger(__name__)


class GrobidService:
    """An environment service for machine readability/annotation (PDF to TEI conversion)."""

    GROBID_URL = "http://localhost:8070"
    # Important: do not use :latest versions or :SNAPSHOT versions
    # as they may change without notice
    GROBID_IMAGE = "lfoppiano/grobid:0.9.0"
    STARTUP_TIMEOUT = 180
    HEALTHCHECK_TIMEOUT = 5
    HEALTHCHECK_INTERVAL = 1

    def __init__(self) -> None:
        """Initialize the instance."""
        colrev.env.docker_manager.DockerManager.build_docker_image(
            imagename=self.GROBID_IMAGE
        )
        self.start()

    def _ensure_correct_version(self) -> None:
        response = requests.get(self.GROBID_URL + "/api/version", timeout=10)
        running_version = response.json()["version"]
        if running_version != self.GROBID_IMAGE.split(":")[1]:
            LOGGER.warning(
                "GROBID version mismatch. Expected: %s, currently running: %s",
                self.GROBID_IMAGE.split(":")[1],
                running_version,
            )
            raise Exception  # pylint: disable=broad-exception-raised

    def check_grobid_availability(
        self, *, wait: bool = True, timeout: float = STARTUP_TIMEOUT
    ) -> bool:
        """Check GROBID availability, optionally waiting up to ``timeout`` seconds."""
        deadline = time.monotonic() + timeout
        while True:
            try:
                response = requests.get(
                    self.GROBID_URL + "/api/isalive",
                    timeout=self.HEALTHCHECK_TIMEOUT,
                )
                if response.text.strip().lower() == "true":
                    # When GROBID is running, it may not be the same version as expected
                    # in self.GROBID_IMAGE, possibly leading to failing tests.
                    self._ensure_correct_version()
                    return True
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
            ):
                pass
            if not wait:
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise requests.exceptions.ConnectionError(
                    f"GROBID did not become available at {self.GROBID_URL} "
                    f"within {timeout} seconds"
                )
            time.sleep(min(self.HEALTHCHECK_INTERVAL, remaining))

    def start(self) -> None:
        """Start the GROBID service."""
        if self.check_grobid_availability(wait=False):
            return

        client = docker.from_env()
        try:
            LOGGER.info("Running docker container created from %s", self.GROBID_IMAGE)
            LOGGER.info("Starting grobid service...")
            try:
                container = client.containers.run(
                    self.GROBID_IMAGE,
                    auto_remove=True,
                    tty=True,
                    mem_limit="4g",
                    environment={"JAVA_TOOL_OPTIONS": "-XX:-UseContainerSupport"},
                    ports={8070: 8070, 8071: 8071},
                    detach=True,
                )
            except docker.errors.APIError as exc:
                if "port is already allocated" not in str(exc).lower():
                    raise
                LOGGER.info(
                    "GROBID port is already allocated; waiting for the existing "
                    "service to become available"
                )
                try:
                    self.check_grobid_availability(
                        wait=True, timeout=self.STARTUP_TIMEOUT
                    )
                except requests.exceptions.ConnectionError as health_exc:
                    raise exc from health_exc
                return

            try:
                self.check_grobid_availability(wait=True, timeout=self.STARTUP_TIMEOUT)
            except requests.exceptions.ConnectionError:
                try:
                    # ``auto_remove`` only removes the detached container after
                    # it stops. Stop it here so its published ports are freed.
                    container.stop(timeout=10)
                except docker.errors.DockerException:
                    LOGGER.exception("Failed to stop unready GROBID container")
                raise
        finally:
            client.close()
