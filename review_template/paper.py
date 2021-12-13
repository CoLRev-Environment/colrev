#! /usr/bin/env python
import logging
import os
from pathlib import Path

import requests

import docker

report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")


def main(REVIEW_MANAGER) -> None:

    if not REVIEW_MANAGER.paths["PAPER"].is_file():
        logger.error("File paper.md does not exist.")
        logger.info("Complete processing and use review_template data")
        return

    REVIEW_MANAGER.build_docker_images()

    uid = os.stat(REVIEW_MANAGER.paths["MAIN_REFERENCES"]).st_uid
    gid = os.stat(REVIEW_MANAGER.paths["MAIN_REFERENCES"]).st_gid

    CSL_FILE = REVIEW_MANAGER.config["CSL"]
    WORD_TEMPLATE_URL = Path(REVIEW_MANAGER.config["WORD_TEMPLATE_URL"])
    WORD_TEMPLATE_FILENAME = WORD_TEMPLATE_URL.name

    # TODO: maybe update?
    if not Path(WORD_TEMPLATE_FILENAME).is_file():

        url = WORD_TEMPLATE_URL
        r = requests.get(str(url))
        with open(WORD_TEMPLATE_FILENAME, "wb") as output:
            output.write(r.content)

    if "github.com" not in CSL_FILE and not os.path.exists(CSL_FILE):
        CSL_FILE = (
            "https://raw.githubusercontent.com/citation-style-"
            + "language/styles/6152ccea8b7d7a472910d36524d1bf3557"
            + "a83bfc/mis-quarterly.csl"
        )

    script = (
        "paper.md --citeproc --bibliography references.bib "
        + f"--csl {CSL_FILE} "
        + f"--reference-doc {WORD_TEMPLATE_FILENAME} "
        + "--output paper.docx"
    )

    client = docker.from_env()
    try:
        pandoc_u_latex_image = "pandoc/ubuntu-latex:2.14"
        msg = "Running docker container created from " f"image {pandoc_u_latex_image}"
        report_logger.info(msg)
        logger.info(msg)
        client.containers.run(
            image=pandoc_u_latex_image,
            command=script,
            user=f"{uid}:{gid}",
            volumes=[os.getcwd() + ":/data"],
        )
    except docker.errors.ImageNotFound:
        logger.error("Docker image not found")
        pass

    return
