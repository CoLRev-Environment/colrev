#! /usr/bin/env python
"""GROBID service to extract and annotate PDF contents."""
from __future__ import annotations

import logging
import os
import subprocess
import time

import requests

import colrev.env.environment_manager


class GrobidService:
    """An environment service for machine readability/annotation (PDF to TEI conversion)"""

    GROBID_URL = "http://localhost:8070"

    def __init__(
        self, *, environment_manager: colrev.env.environment_manager.EnvironmentManager
    ) -> None:
        self.grobid_image = "lfoppiano/grobid:0.7.2"
        environment_manager.build_docker_image(imagename=self.grobid_image)
        self.start()
        if not self.check_grobid_availability():
            environment_manager.register_ports(ports=["8070", "8071"])

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

    def start(self) -> None:
        """Start the GROBID service"""
        # pylint: disable=consider-using-with

        try:
            res = self.check_grobid_availability(wait=False)
            if res:
                return
        except requests.exceptions.ConnectionError:
            pass

        logging.info("Running docker container created from %s", self.grobid_image)

        logging.info("Starting grobid service...")
        start_cmd = [
            "docker",
            "run",
            "-t",
            "--rm",
            "-m",
            "4g",
            "-p",
            "8070:8070",
            "-p",
            "8071:8071",
            self.grobid_image,
        ]
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            subprocess.Popen(start_cmd, shell=False, stdout=devnull)

        self.check_grobid_availability()


if __name__ == "__main__":
    pass
