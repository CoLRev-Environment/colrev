#! /usr/bin/env python
import os
from pathlib import Path

import docker

import colrev_core.built_in.data as built_in_data
import colrev_core.environment
import colrev_core.exceptions as colrev_exceptions
import colrev_core.process


class Paper(colrev_core.process.Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.explore,
        )

    def main(self) -> None:

        paper_endpoint_settings_l = [
            s
            for s in self.REVIEW_MANAGER.settings.data.scripts
            if "MANUSCRIPT" == s["endpoint"]
        ]

        if len(paper_endpoint_settings_l) != 1:
            raise colrev_exceptions.NoPaperEndpointRegistered()

        paper_endpoint_settings = paper_endpoint_settings_l[0]

        if not self.REVIEW_MANAGER.paths["PAPER"].is_file():
            self.REVIEW_MANAGER.logger.error("File paper.md does not exist.")
            self.REVIEW_MANAGER.logger.info(
                "Complete processing and use colrev_core data"
            )
            return

        colrev_core.environment.EnvironmentManager.build_docker_images()

        CSL_FILE = paper_endpoint_settings["csl_style"]
        WORD_TEMPLATE = paper_endpoint_settings["word_template"]

        if not Path(WORD_TEMPLATE).is_file():
            built_in_data.ManuscriptEndpoint.retrieve_default_word_template()
        if not Path(CSL_FILE).is_file():
            built_in_data.ManuscriptEndpoint.retrieve_default_csl()
        assert Path(WORD_TEMPLATE).is_file()
        assert Path(CSL_FILE).is_file()

        uid = os.stat(self.REVIEW_MANAGER.paths["RECORDS_FILE"]).st_uid
        gid = os.stat(self.REVIEW_MANAGER.paths["RECORDS_FILE"]).st_gid

        script = (
            "paper.md --citeproc --bibliography records.bib "
            + f"--csl {CSL_FILE} "
            + f"--reference-doc {WORD_TEMPLATE} "
            + "--output paper.docx"
        )

        client = docker.from_env()
        try:
            pandoc_img = colrev_core.environment.EnvironmentManager.docker_images[
                "pandoc/ubuntu-latex"
            ]
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

        return


if __name__ == "__main__":
    pass
