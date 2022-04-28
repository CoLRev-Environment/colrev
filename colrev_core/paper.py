#! /usr/bin/env python
from pathlib import Path

from colrev_core.process import Process
from colrev_core.process import ProcessType


class Paper(Process):
    def __init__(self, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER, ProcessType.explore)

    def main(self) -> None:
        import os
        import requests
        import docker

        from colrev_core.environment import EnvironmentManager

        if not self.REVIEW_MANAGER.paths["PAPER"].is_file():
            self.REVIEW_MANAGER.logger.error("File paper.md does not exist.")
            self.REVIEW_MANAGER.logger.info(
                "Complete processing and use colrev_core data"
            )
            return

        EnvironmentManager.build_docker_images()

        uid = os.stat(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"]).st_uid
        gid = os.stat(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"]).st_gid

        CSL_FILE = self.REVIEW_MANAGER.config["CSL"]
        WORD_TEMPLATE_URL = self.REVIEW_MANAGER.config["WORD_TEMPLATE_URL"]
        WORD_TEMPLATE_FILENAME = Path(WORD_TEMPLATE_URL).name

        if not Path(WORD_TEMPLATE_FILENAME).is_file():

            url = WORD_TEMPLATE_URL
            r = requests.get(str(url))
            with open(WORD_TEMPLATE_FILENAME, "wb", encoding="utf8") as output:
                output.write(r.content)
        else:
            WORD_TEMPLATE_URL = Path(self.REVIEW_MANAGER.config["WORD_TEMPLATE_URL"])

        script = (
            "paper.md --citeproc --bibliography references.bib "
            + f"--csl {CSL_FILE} "
            + f"--reference-doc {WORD_TEMPLATE_FILENAME} "
            + "--output paper.docx"
        )

        client = docker.from_env()
        try:
            pandoc_img = EnvironmentManager.docker_images["pandoc/ubuntu-latex"]
            msg = "Running docker container created from " f"image {pandoc_img}"
            self.REVIEW_MANAGER.report_logger.info(msg)
            self.REVIEW_MANAGER.logger.info(msg)
            client.containers.run(
                image=pandoc_img,
                command=script,
                user=f"{uid}:{gid}",
                volumes=[os.getcwd() + ":/data"],
            )
        except docker.errors.ImageNotFound:
            self.REVIEW_MANAGER.logger.error("Docker image not found")
            pass

        return


if __name__ == "__main__":
    pass
