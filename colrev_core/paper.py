#! /usr/bin/env python
from pathlib import Path

from colrev_core.process import Process
from colrev_core.process import ProcessType


class Paper(Process):
    def __init__(self, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER, ProcessType.explore)

    def check_precondition(self) -> None:
        return

    def main(self) -> None:
        import os
        import requests
        import docker

        if not self.REVIEW_MANAGER.paths["PAPER"].is_file():
            self.logger.error("File paper.md does not exist.")
            self.logger.info("Complete processing and use colrev_core data")
            return

        self.REVIEW_MANAGER.build_docker_images()

        uid = os.stat(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"]).st_uid
        gid = os.stat(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"]).st_gid

        CSL_FILE = Path(self.REVIEW_MANAGER.config["CSL"])
        WORD_TEMPLATE_URL = Path(self.REVIEW_MANAGER.config["WORD_TEMPLATE_URL"])
        WORD_TEMPLATE_FILENAME = WORD_TEMPLATE_URL.name

        # TODO: maybe update?
        if not Path(WORD_TEMPLATE_FILENAME).is_file():

            url = WORD_TEMPLATE_URL
            r = requests.get(str(url))
            with open(WORD_TEMPLATE_FILENAME, "wb") as output:
                output.write(r.content)

        if "github.com" not in str(CSL_FILE) and not CSL_FILE.is_file():
            CSL_FILE = Path(
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
            msg = (
                "Running docker container created from " f"image {pandoc_u_latex_image}"
            )
            self.report_logger.info(msg)
            self.logger.info(msg)
            client.containers.run(
                image=pandoc_u_latex_image,
                command=script,
                user=f"{uid}:{gid}",
                volumes=[os.getcwd() + ":/data"],
            )
        except docker.errors.ImageNotFound:
            self.logger.error("Docker image not found")
            pass

        return


if __name__ == "__main__":
    pass
