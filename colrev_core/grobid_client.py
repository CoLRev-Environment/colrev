#! /usr/bin/env python
import logging
import os
import subprocess
import time

import requests

GROBID_URL = "http://localhost:8070"


def get_grobid_url() -> str:
    return GROBID_URL


def check_grobid_availability() -> None:
    i = 0
    while True:
        i += 1
        time.sleep(1)
        try:
            r = requests.get(GROBID_URL + "/api/isalive")
            if r.text == "true":
                i = -1
        except requests.exceptions.ConnectionError:
            pass
        if i == -1:
            break
        if i > 20:
            raise requests.exceptions.ConnectionError()
    return


def start_grobid() -> None:
    from colrev_core.environment import EnvironmentManager

    try:
        check_grobid_availability()
    except requests.exceptions.ConnectionError:
        pass

        grobid_image = EnvironmentManager.docker_images["lfoppiano/grobid"]

        logging.info(f"Running docker container created from {grobid_image}")

        logging.info("Starting grobid service...")
        start_cmd = (
            f'docker run -t --rm -m "4g" -p 8070:8070 -p 8071:8071 {grobid_image}'
        )
        subprocess.Popen(
            [start_cmd],
            shell=True,
            stdin=None,
            stdout=open(os.devnull, "wb", encoding="utf8"),
            stderr=None,
            close_fds=True,
        )
        check_grobid_availability()
