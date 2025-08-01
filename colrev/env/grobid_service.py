#! /usr/bin/env python
"""GROBID service to extract and annotate PDF contents."""
from __future__ import annotations

import logging
import time

import docker
import requests

import colrev.env.docker_manager


class GrobidService:
    """An environment service for machine readability/annotation (PDF to TEI conversion)"""

    GROBID_URL = "http://localhost:8070"
    # Important: do not use :latest versions or :SNAPSHOT versions
    # as they may change without notice
    GROBID_IMAGE = "lfoppiano/grobid:0.8.2"

    def __init__(self) -> None:
        colrev.env.docker_manager.DockerManager.build_docker_image(
            imagename=self.GROBID_IMAGE
        )
        self.start()
        self.check_grobid_availability()

    def _ensure_correct_version(self) -> None:
        response = requests.get(self.GROBID_URL + "/api/version", timeout=10)
        running_version = response.json()["version"]
        if running_version != self.GROBID_IMAGE.split(":")[1]:
            logging.warning(
                "GROBID version mismatch. Expected: %s, currently running: %s",
                self.GROBID_IMAGE.split(":")[1],
                running_version,
            )
            raise Exception

    def check_grobid_availability(self, *, wait: bool = True) -> bool:
        """Check whether the GROBID service is available"""
        i = 0
        while True:
            i += 1
            time.sleep(1)
            try:
                ret = requests.get(self.GROBID_URL + "/api/isalive", timeout=30)
                if ret.text == "true":
                    # When GROBID is running, it may not be the same version as expected
                    # in self.GROBID_IMAGE, possibly leading to failing tests.
                    self._ensure_correct_version()
                    return True
            except requests.exceptions.ConnectionError:
                pass
            if not wait:
                return False
            if i == -1:
                break
            if i > 20:
                raise requests.exceptions.ConnectionError()
        return True

    def start(self) -> None:
        """Start the GROBID service"""
        # pylint: disable=consider-using-with

        try:
            res = self.check_grobid_availability(wait=False)
            if res:
                return
        except requests.exceptions.ConnectionError:
            pass

        client = docker.from_env()
        logging.info("Running docker container created from %s", self.GROBID_IMAGE)
        logging.info("Starting grobid service...")
        client.containers.run(
            self.GROBID_IMAGE,
            auto_remove=True,
            tty=True,
            mem_limit="4g",
            ports={8070: 8070, 8071: 8071},
            detach=True,
        )

        self.check_grobid_availability()
