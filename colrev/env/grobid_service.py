#! /usr/bin/env python
"""GROBID service to extract and annotate PDF contents."""
from __future__ import annotations

import logging
import time
import typing

import docker
import requests

import colrev.env.docker_manager
import colrev.env.environment_manager


class GrobidService:
    """An environment service for machine readability/annotation (PDF to TEI conversion)"""

    GROBID_URL = "http://localhost:8070"
    GROBID_IMAGE = "lfoppiano/grobid:0.8.0"

    def __init__(
        self,
        *,
        environment_manager: typing.Optional[
            colrev.env.environment_manager.EnvironmentManager
        ] = None,
    ) -> None:
        colrev.env.docker_manager.DockerManager.build_docker_image(
            imagename=self.GROBID_IMAGE
        )
        self.start(environment_manager)
        self.check_grobid_availability()

    def check_grobid_availability(self, *, wait: bool = True) -> bool:
        """Check whether the GROBID service is available"""
        i = 0
        while True:
            i += 1
            time.sleep(1)
            try:
                ret = requests.get(self.GROBID_URL + "/api/isalive", timeout=30)
                if ret.text == "true":
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

    def start(
        self,
        environment_manager: typing.Optional[
            colrev.env.environment_manager.EnvironmentManager
        ] = None,
    ) -> None:
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
        if environment_manager:
            environment_manager.register_ports(["8070", "8071"])

        self.check_grobid_availability()
