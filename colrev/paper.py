#! /usr/bin/env python
import os
from pathlib import Path

import docker

import colrev.built_in.data as built_in_data
import colrev.exceptions as colrev_exceptions
import colrev.process


class Paper(colrev.process.Process):
    def __init__(self, *, review_manager):
        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.explore,
        )

    def main(self) -> None:

        paper_endpoint_settings_l = [
            s
            for s in self.review_manager.settings.data.scripts
            if "MANUSCRIPT" == s["endpoint"]
        ]

        if len(paper_endpoint_settings_l) != 1:
            raise colrev_exceptions.NoPaperEndpointRegistered()

        paper_endpoint_settings = paper_endpoint_settings_l[0]

        if not self.review_manager.paths["PAPER"].is_file():
            self.review_manager.logger.error("File paper.md does not exist.")
            self.review_manager.logger.info("Complete processing and use colrev data")
            return

        environment_manager = self.review_manager.get_environment_manager()
        environment_manager.build_docker_images()

        csl_file = paper_endpoint_settings["csl_style"]
        word_template = paper_endpoint_settings["word_template"]

        if not Path(word_template).is_file():
            built_in_data.ManuscriptEndpoint.retrieve_default_word_template()
        if not Path(csl_file).is_file():
            built_in_data.ManuscriptEndpoint.retrieve_default_csl()
        assert Path(word_template).is_file()
        assert Path(csl_file).is_file()

        uid = os.stat(self.review_manager.paths["RECORDS_FILE"]).st_uid
        gid = os.stat(self.review_manager.paths["RECORDS_FILE"]).st_gid

        script = (
            "paper.md --citeproc --bibliography records.bib "
            + f"--csl {csl_file} "
            + f"--reference-doc {word_template} "
            + "--output paper.docx"
        )

        client = docker.from_env()
        try:
            environment_manager = self.review_manager.get_environment_manager()

            pandoc_img = environment_manager.docker_images["pandoc/ubuntu-latex"]
            msg = "Running docker container created from " f"image {pandoc_img}"
            self.review_manager.report_logger.info(msg)
            self.review_manager.logger.info(msg)
            client.containers.run(
                image=pandoc_img,
                command=script,
                user=f"{uid}:{gid}",
                volumes=[os.getcwd() + ":/data"],
            )
        except docker.errors.ImageNotFound:
            self.review_manager.logger.error("Docker image not found")

        return


if __name__ == "__main__":
    pass
