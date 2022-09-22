#! /usr/bin/env python
"""Creation of a markdown manuscript as part of the data operations"""
from __future__ import annotations

import os
import re
import tempfile
import typing
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import docker
import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageInterface)
@dataclass
class Manuscript(JsonSchemaMixin):
    """Synthesize the literature in a manuscript

    The manuscript (paper.md) is created automatically.
    Records are added for synthesis after the <!-- NEW_RECORD_SOURCE -->
    Once records are moved to other parts of the manuscript (cited or in comments)
    they are assumed to be synthesized in the manuscript.
    Once they are synthesized in all data endpoints,
    CoLRev sets their status to rev_synthesized.
    The data operation also builds the manuscript (using pandoc, csl and a template).
    """

    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"
    """Tag for appending new records in paper.md

    In the paper.md, the IDs of new records marked for synthesis
    will be appended after this tag.

    If IDs are moved to other parts of the manuscript,
    the corresponding record will be marked as rev_synthesized."""

    @dataclass
    class ManuscriptSettings(JsonSchemaMixin):
        name: str
        version: str
        word_template: str
        csl_style: str
        paper_path: Path = Path("paper.md")
        paper_output: Path = Path("paper.docx")
        # TODO : output path

        _details = {
            "word_template": {"tooltip": "Path to the word template (for Pandoc)"},
            "csl_style": {"tooltip": "Path to the csl file (for Pandoc)"},
            "paper_path": {"tooltip": "Path for the paper (markdown source document)"},
        }

    settings_class = ManuscriptSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:

        # Set default values (if necessary)
        if "version" not in settings:
            settings["version"] = "0.1"

        if "word_template" not in settings:
            settings["word_template"] = self.retrieve_default_word_template()
        if "csl_style" not in settings:
            settings["csl_style"] = (self.retrieve_default_csl(),)

        if "paper_output" not in settings:
            settings["paper_output"] = Path("paper.docx")

        self.settings = from_dict(data_class=self.settings_class, data=settings)

        self.settings.paper_path = (
            data_operation.review_manager.data_dir / self.settings.paper_path
        )
        self.settings.word_template = (
            data_operation.review_manager.data_dir / self.settings.word_template
        )
        self.settings.csl_style = (
            data_operation.review_manager.data_dir / self.settings.csl_style
        )

        self.data_operation = data_operation

        self.settings.paper_output = (
            data_operation.review_manager.output_dir / self.settings.paper_output
        )

    def get_default_setup(self) -> dict:

        manuscript_endpoint_details = {
            "endpoint": "MANUSCRIPT",
            "version": "0.1",
            "word_template": self.retrieve_default_word_template(),
            "csl_style": self.retrieve_default_csl(),
        }

        return manuscript_endpoint_details

    def retrieve_default_word_template(self) -> Path:
        template_name = self.data_operation.review_manager.data_dir / Path("APA-7.docx")

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/APA-7.docx")
        )

        if filedata:
            with open(template_name, "wb") as file:
                file.write(filedata)
        self.data_operation.review_manager.dataset.add_changes(
            path=template_name.relative_to(self.data_operation.review_manager.path)
        )
        return template_name

    def retrieve_default_csl(self) -> str:
        csl_link = (
            "https://raw.githubusercontent.com/"
            + "citation-style-language/styles/master/apa.csl"
        )
        csl_path = self.data_operation.review_manager.data_dir / Path(csl_link).name
        ret = requests.get(csl_link, allow_redirects=True)
        with open(csl_path, "wb") as file:
            file.write(ret.content)
        csl = Path(csl_link).name

        self.data_operation.review_manager.dataset.add_changes(
            path=csl_path.relative_to(self.data_operation.review_manager.path)
        )
        return csl

    def check_new_record_source_tag(
        self,
    ) -> None:

        with open(self.settings.paper_path, encoding="utf-8") as file:
            for line in file:
                if self.NEW_RECORD_SOURCE_TAG in line:
                    return
        raise ManuscriptRecordSourceTagError(
            f"Did not find {self.NEW_RECORD_SOURCE_TAG} tag in {self.settings.paper_path}"
        )

    def __authorship_heuristic(
        self, *, review_manager: colrev.review_manager.ReviewManager
    ) -> str:
        git_repo = review_manager.dataset.get_repo()
        commits_list = list(git_repo.iter_commits())
        commits_authors = []
        for commit in commits_list:
            committer = git_repo.git.show("-s", "--format=%cn", commit.hexsha)
            if "GitHub" == committer:
                continue
            commits_authors.append(committer)
            # author = git_repo.git.show("-s", "--format=%an", commit.hexsha)
            # mail = git_repo.git.show("-s", "--format=%ae", commit.hexsha)
        author = ", ".join(dict(Counter(commits_authors)))
        return author

    def __get_data_page_missing(self, *, paper: Path, record_id_list: list) -> list:
        available = []
        with open(paper, encoding="utf-8") as file:
            line = file.read()
            for record in record_id_list:
                if record in line:
                    available.append(record)

        return list(set(record_id_list) - set(available))

    def __add_missing_records_to_manuscript(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        paper_path: Path,
        missing_records: list,
    ):
        # pylint: disable=consider-using-with
        # pylint: disable=too-many-branches

        temp = tempfile.NamedTemporaryFile()
        paper_path.rename(temp.name)
        with open(temp.name, encoding="utf-8") as reader, open(
            paper_path, "w", encoding="utf-8"
        ) as writer:
            appended, completed = False, False
            line = reader.readline()
            while line != "":
                if self.NEW_RECORD_SOURCE_TAG in line:
                    if "_Records to synthesize" not in line:
                        line = "_Records to synthesize_:" + line + "\n"
                        writer.write(line)
                    else:
                        writer.write(line)
                        writer.write("\n")

                    for missing_record in missing_records:
                        writer.write(missing_record)
                        review_manager.report_logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ")
                            f" {missing_record}"
                            + f" added to {paper_path.name}"
                        )

                        review_manager.logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ")
                            f" {missing_record}"
                            + f" added to {paper_path.name}"
                        )

                    # skip empty lines between to connect lists
                    line = reader.readline()
                    if "\n" != line:
                        writer.write(line)

                    appended = True

                elif appended and not completed:
                    if "- @" == line[:3]:
                        writer.write(line)
                    else:
                        if "\n" != line:
                            writer.write("\n")
                        writer.write(line)
                        completed = True
                else:
                    writer.write(line)
                line = reader.readline()

            if not appended:
                msg = (
                    f"Marker {self.NEW_RECORD_SOURCE_TAG} not found in "
                    + f"{paper_path.name}. Adding records at the end of "
                    + "the document."
                )
                review_manager.report_logger.warning(msg)
                review_manager.logger.warning(msg)
                if line != "\n":
                    writer.write("\n")
                marker = f"{self.NEW_RECORD_SOURCE_TAG}_Records to synthesize_:\n\n"
                writer.write(marker)
                for missing_record in missing_records:
                    writer.write(missing_record)
                    review_manager.report_logger.info(
                        # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                        f" {missing_record} added"
                    )
                    review_manager.logger.info(
                        # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                        f" {missing_record} added"
                    )

    def __create_paper(
        self, review_manager: colrev.review_manager.ReviewManager
    ) -> None:

        review_manager.report_logger.info("Creating manuscript")
        review_manager.logger.info("Creating manuscript")

        title = "Manuscript template"
        readme_file = review_manager.readme
        if readme_file.is_file():
            with open(readme_file, encoding="utf-8") as file:
                title = file.readline()
                title = title.replace("# ", "").replace("\n", "")

        author = self.__authorship_heuristic(review_manager=review_manager)

        review_type = review_manager.settings.project.review_type

        r_type_path = str(review_type).replace(" ", "_").replace("-", "_")
        paper_resource_path = Path(f"template/review_type/{r_type_path}/") / Path(
            "paper.md"
        )
        try:
            colrev.env.utils.retrieve_package_file(
                template_file=paper_resource_path, target=self.settings.paper_path
            )
        except FileNotFoundError:
            paper_resource_path = Path("template/") / Path("paper.md")
            colrev.env.utils.retrieve_package_file(
                template_file=paper_resource_path, target=self.settings.paper_path
            )

        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{review_type}}",
            new_string=str(review_type),
        )
        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{project_title}}",
            new_string=title,
        )
        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{author}}",
            new_string=author,
        )
        review_manager.logger.info(
            f"Please update title and authors in {self.settings.paper_path.name}"
        )

    def __add_missing_records(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        synthesized_record_status_matrix: dict,
    ) -> None:
        review_manager.report_logger.info("Updating manuscript")
        review_manager.logger.info("Updating manuscript")
        missing_records = self.__get_data_page_missing(
            paper=self.settings.paper_path,
            record_id_list=list(synthesized_record_status_matrix.keys()),
        )
        missing_records = sorted(missing_records)
        review_manager.logger.debug(f"missing_records: {missing_records}")

        self.check_new_record_source_tag()

        if 0 == len(missing_records):
            review_manager.report_logger.info(
                f"All records included in {self.settings.paper_path.name}"
            )
            review_manager.logger.info(
                f"All records included in {self.settings.paper_path.name}"
            )
        else:
            self.__add_missing_records_to_manuscript(
                review_manager=review_manager,
                paper_path=self.settings.paper_path,
                missing_records=[
                    "\n- @" + missing_record + "\n"
                    for missing_record in missing_records
                ],
            )
            nr_records_added = len(missing_records)
            review_manager.report_logger.info(
                f"{nr_records_added} records added to {self.settings.paper_path.name}"
            )
            review_manager.logger.info(
                f"{nr_records_added} records added to {self.settings.paper_path.name}"
            )

    def update_manuscript(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        records: typing.Dict,
        synthesized_record_status_matrix: dict,
    ) -> typing.Dict:

        if not self.settings.paper_path.is_file():
            self.__create_paper(review_manager=review_manager)

        self.__add_missing_records(
            review_manager=review_manager,
            synthesized_record_status_matrix=synthesized_record_status_matrix,
        )

        review_manager.dataset.add_changes(path=self.settings.paper_path)

        return records

    def build_manuscript(self, *, data_operation: colrev.ops.data.Data) -> None:

        data_operation.review_manager.logger.info("Build manuscript")

        if not self.settings.paper_path.is_file():
            data_operation.review_manager.logger.error(
                "File %s does not exist.", self.settings.paper_path
            )
            data_operation.review_manager.logger.info(
                "Complete processing and use colrev data"
            )
            return

        environment_manager = data_operation.review_manager.get_environment_manager()
        environment_manager.build_docker_images()

        csl_file = self.settings.csl_style
        word_template = self.settings.word_template

        if not Path(word_template).is_file():
            self.retrieve_default_word_template()
        if not Path(csl_file).is_file():
            self.retrieve_default_csl()
        assert Path(word_template).is_file()
        assert Path(csl_file).is_file()

        uid = os.stat(data_operation.review_manager.dataset.records_file).st_uid
        gid = os.stat(data_operation.review_manager.dataset.records_file).st_gid

        paper_relative_path = self.settings.paper_path.relative_to(
            data_operation.review_manager.path
        )
        output_relative_path = self.settings.paper_output.relative_to(
            data_operation.review_manager.path
        )
        script = (
            f"{paper_relative_path} --citeproc --bibliography records.bib "
            + f"--csl {csl_file.relative_to(data_operation.review_manager.path)} "
            + f"--reference-doc {word_template.relative_to(data_operation.review_manager.path)} "
            + f"--output {output_relative_path}"
        )

        client = docker.from_env()
        try:
            environment_manager = (
                data_operation.review_manager.get_environment_manager()
            )

            pandoc_img = environment_manager.docker_images["pandoc/ubuntu-latex"]
            msg = "Running docker container created from " f"image {pandoc_img}"
            data_operation.review_manager.report_logger.info(msg)
            data_operation.review_manager.logger.info(msg)
            client.containers.run(
                image=pandoc_img,
                command=script,
                user=f"{uid}:{gid}",
                volumes=[os.getcwd() + ":/data"],
            )
        except docker.errors.ImageNotFound:
            data_operation.review_manager.logger.error("Docker image not found")

        return

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,
    ):
        records = self.update_manuscript(
            review_manager=data_operation.review_manager,
            records=records,
            synthesized_record_status_matrix=synthesized_record_status_matrix,
        )
        self.build_manuscript(data_operation=data_operation)

    def __get_to_synthesize_in_manuscript(
        self, *, paper: Path, records_for_synthesis: list
    ) -> list:
        in_manuscript_to_synthesize = []
        if paper.is_file():
            with open(paper, encoding="utf-8") as file:
                for line in file:
                    if self.NEW_RECORD_SOURCE_TAG in line:
                        while line != "":
                            line = file.readline()
                            if re.search(r"- @.*", line):
                                record_id = re.findall(r"- @(.*)$", line)
                                in_manuscript_to_synthesize.append(record_id[0])
                                if line == "\n":
                                    break

            in_manuscript_to_synthesize = [
                x for x in in_manuscript_to_synthesize if x in records_for_synthesis
            ]
        else:
            in_manuscript_to_synthesize = records_for_synthesis
        return in_manuscript_to_synthesize

    def __get_synthesized_ids_paper(
        self, *, paper: Path, synthesized_record_status_matrix: dict
    ) -> list:

        in_manuscript_to_synthesize = self.__get_to_synthesize_in_manuscript(
            paper=paper,
            records_for_synthesis=list(synthesized_record_status_matrix.keys()),
        )
        # Assuming that all records have been added to the paper before
        synthesized_ids = [
            x
            for x in list(synthesized_record_status_matrix.keys())
            if x not in in_manuscript_to_synthesize
        ]

        return synthesized_ids

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ):
        # Update status / synthesized_record_status_matrix
        synthesized_in_manuscript = self.__get_synthesized_ids_paper(
            paper=self.settings.paper_path,
            synthesized_record_status_matrix=synthesized_record_status_matrix,
        )
        for syn_id in synthesized_in_manuscript:
            if syn_id in synthesized_record_status_matrix:
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = True
            else:
                print(f"Error: {syn_id} not int {synthesized_in_manuscript}")


class ManuscriptRecordSourceTagError(Exception):
    """NEW_RECORD_SOURCE_TAG not found in paper.md"""

    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


if __name__ == "__main__":
    pass
