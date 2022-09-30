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

    GROBID_URL = "http://localhost:8070"

    def __init__(self) -> None:
        pass

    def check_grobid_availability(self, *, wait: bool = True) -> bool:
        i = 0
        while True:
            i += 1
            time.sleep(1)
            try:
                ret = requests.get(self.GROBID_URL + "/api/isalive")
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
        # pylint: disable=consider-using-with

        try:
            res = self.check_grobid_availability(wait=False)
            if res:
                return
        except requests.exceptions.ConnectionError:
            pass

        grobid_image = colrev.env.environment_manager.EnvironmentManager.docker_images[
            "lfoppiano/grobid"
        ]

        logging.info("Running docker container created from %s", grobid_image)

        logging.info("Starting grobid service...")
        start_cmd = (
            f'docker run -t --rm -m "4g" -p 8070:8070 -p 8071:8071 {grobid_image}'
        )
        subprocess.Popen(
            [start_cmd],
            shell=True,
            stdin=None,
            stdout=open(os.devnull, "wb"),
            stderr=None,
            close_fds=True,
        )
        self.check_grobid_availability()


if __name__ == "__main__":
    pass
