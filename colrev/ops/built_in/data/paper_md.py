#! /usr/bin/env python
"""Creation of a markdown paper as part of the data operations"""
from __future__ import annotations

import os
import re
import tempfile
import typing
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from threading import Timer

import docker
import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from docker.errors import DockerException

import colrev.env.package_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record
import colrev.ui_cli.cli_colors as colors


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class PaperMarkdown(JsonSchemaMixin):
    """Synthesize the literature in a markdown paper

    The paper (paper.md) is created automatically.
    Records are added for synthesis after the <!-- NEW_RECORD_SOURCE -->
    Once records are moved to other parts of the paper (cited or in comments)
    they are assumed to be synthesized in the paper.
    Once they are synthesized in all data endpoints,
    CoLRev sets their status to rev_synthesized.
    The data operation also builds the paper (using pandoc, csl and a template).
    """

    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"
    """Tag for appending new records in paper.md

    In the paper.md, the IDs of new records marked for synthesis
    will be appended after this tag.

    If IDs are moved to other parts of the paper,
    the corresponding record will be marked as rev_synthesized."""

    NON_SAMPLE_REFERENCES_RELATIVE = Path("non_sample_references.bib")

    ci_supported: bool = False

    @dataclass
    class PaperMarkdownSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Paper settings"""

        endpoint: str
        version: str
        word_template: Path
        paper_path: Path = Path("paper.md")
        paper_output: Path = Path("paper.docx")

        _details = {
            "word_template": {"tooltip": "Path to the word template (for Pandoc)"},
            "paper_path": {"tooltip": "Path for the paper (markdown source document)"},
            "paper_output": {
                "tooltip": "Path for the output (e.g., paper.docx/pdf/latex/html)"
            },
        }

    settings_class = PaperMarkdownSettings

    __temp_path = Path.home().joinpath("colrev") / Path(".colrev_temp")

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:
        self.data_operation = data_operation

        # Set default values (if necessary)
        if "version" not in settings:
            settings["version"] = "0.1"

        if "word_template" not in settings:
            settings["word_template"] = Path("data/APA-7.docx")

        if "paper_output" not in settings:
            settings["paper_output"] = Path("paper.docx")

        self.settings = self.settings_class.load_settings(data=settings)

        self.settings.paper_path = (
            data_operation.review_manager.data_dir / self.settings.paper_path
        )
        self.settings.word_template = (
            data_operation.review_manager.data_dir / self.settings.word_template
        )
        self.non_sample_references = (
            data_operation.review_manager.data_dir / self.NON_SAMPLE_REFERENCES_RELATIVE
        )
        self.data_operation = data_operation

        self.settings.paper_output = (
            data_operation.review_manager.output_dir / self.settings.paper_output
        )

        self.__create_non_sample_references_bib()

        if not data_operation.review_manager.in_ci_environment():
            self.pandoc_image = "pandoc/latex:2.19.2"
            data_operation.review_manager.environment_manager.build_docker_image(
                imagename=self.pandoc_image
            )

        self.paper_relative_path = self.settings.paper_path.relative_to(
            data_operation.review_manager.path
        )
        self.__temp_path.mkdir(exist_ok=True, parents=True)

    def get_default_setup(self) -> dict:
        """Get the default setup"""

        paper_md_endpoint_details = {
            "endpoint": "colrev.paper_md",
            "version": "0.1",
            "word_template": Path("data/APA-7.docx"),
        }

        return paper_md_endpoint_details

    def __retrieve_default_word_template(self) -> Path:
        template_name = self.data_operation.review_manager.data_dir / Path("APA-7.docx")

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/paper_md/APA-7.docx")
        )

        if filedata:
            with open(template_name, "wb") as file:
                file.write(filedata)
        self.data_operation.review_manager.dataset.add_changes(path=template_name)
        return template_name

    def __retrieve_default_csl(self) -> None:
        csl_link = ""
        with open(self.settings.paper_path, encoding="utf-8") as file:
            for line in file:
                csl_match = re.match(r"csl: ?\"([^\"\n]*)\"\n", line)
                if csl_match:
                    csl_link = csl_match.group(1)

        if "http" in csl_link:
            ret = requests.get(csl_link, allow_redirects=True, timeout=30)
            csl_filename = (
                self.data_operation.review_manager.DATA_DIR_RELATIVE
                / Path(csl_link).name
            )
            with open(csl_filename, "wb") as file:
                file.write(ret.content)
            colrev.env.utils.inplace_change(
                filename=self.settings.paper_path,
                old_string=f'csl: "{csl_link}"',
                new_string=f'csl: "{csl_filename}"',
            )
            self.data_operation.review_manager.dataset.add_changes(
                path=self.settings.paper_path
            )
            self.data_operation.review_manager.dataset.add_changes(
                path=Path(csl_filename)
            )
            self.data_operation.review_manager.logger.debug(
                "Downloaded csl file for offline use"
            )

    def __check_new_record_source_tag(
        self,
    ) -> None:
        with open(self.settings.paper_path, encoding="utf-8") as file:
            for line in file:
                if self.NEW_RECORD_SOURCE_TAG in line:
                    return
        raise PaperMarkdownRecordSourceTagError(
            f"Did not find {self.NEW_RECORD_SOURCE_TAG} tag in {self.settings.paper_path}"
        )

    def __authorship_heuristic(self) -> str:
        git_repo = self.data_operation.review_manager.dataset.get_repo()
        try:
            commits_list = list(git_repo.iter_commits())
            commits_authors = []

            for commit in commits_list:
                committer = git_repo.git.show("-s", "--format=%cn", commit.hexsha)
                if committer == "GitHub":
                    continue
                commits_authors.append(committer)
                # author = git_repo.git.show("-s", "--format=%an", commit.hexsha)
                # mail = git_repo.git.show("-s", "--format=%ae", commit.hexsha)
            author = ", ".join(dict(Counter(commits_authors)))
        except ValueError:
            author, _ = self.data_operation.review_manager.get_committer()
        return author

    def __get_data_page_missing(self, *, paper: Path, record_id_list: list) -> list:
        available = []
        with open(paper, encoding="utf-8") as file:
            line = file.read()
            for record in record_id_list:
                if record in line:
                    available.append(record)

        return list(set(record_id_list) - set(available))

    def __add_missing_records_to_paper(
        self,
        *,
        missing_records: list,
        silent_mode: bool,
    ) -> None:
        # pylint: disable=consider-using-with
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        # pylint: disable=too-many-locals

        temp = tempfile.NamedTemporaryFile(dir=self.__temp_path)
        paper_path = self.settings.paper_path
        Path(temp.name).unlink(missing_ok=True)
        paper_path.rename(temp.name)
        with open(temp.name, encoding="utf-8") as reader, open(
            paper_path, "w", encoding="utf-8"
        ) as writer:
            appended, completed = False, False
            line = reader.readline()
            while line:
                if self.NEW_RECORD_SOURCE_TAG in line:
                    if "_Records to synthesize" not in line:
                        line = "_Records to synthesize_:" + line + "\n"
                        writer.write(line)
                    else:
                        writer.write(line)
                        writer.write("\n")

                    paper_ids_added = []
                    for missing_record in missing_records:
                        writer.write("\n- @" + missing_record + "\n")
                        paper_ids_added.append(missing_record)

                    for paper_id in paper_ids_added:
                        self.data_operation.review_manager.report_logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ")
                            f" {paper_id}"
                            + f" added to {paper_path.name}"
                        )
                    nr_records_added = len(missing_records)
                    self.data_operation.review_manager.report_logger.info(
                        f"{nr_records_added} records added to {self.settings.paper_path.name}"
                    )

                    for paper_id_added in paper_ids_added:
                        if not silent_mode:
                            self.data_operation.review_manager.logger.info(
                                f" {colors.GREEN}{paper_id_added}".ljust(45)
                                + f"add to paper{colors.END}"
                            )

                    if not silent_mode:
                        self.data_operation.review_manager.logger.info(
                            f"Added to {paper_path.name}".ljust(24)
                            + f"{nr_records_added}".rjust(15, " ")
                            + " records"
                        )

                    # skip empty lines between to connect lists
                    line = reader.readline()
                    if line != "\n":
                        writer.write(line)

                    appended = True

                elif appended and not completed:
                    if line[:3] == "- @":
                        writer.write(line)
                    else:
                        if line != "\n":
                            writer.write("\n")
                        writer.write(line)
                        completed = True
                else:
                    writer.write(line)
                line = reader.readline()

            if not appended:
                msg = (
                    f"Marker {self.NEW_RECORD_SOURCE_TAG} not found in "
                    + f"{paper_path.name}. Add records at the end of "
                    + "the document."
                )
                self.data_operation.review_manager.report_logger.warning(msg)
                self.data_operation.review_manager.logger.warning(msg)
                if line != "\n":
                    writer.write("\n")
                marker = f"{self.NEW_RECORD_SOURCE_TAG}_Records to synthesize_:\n\n"
                writer.write(marker)
                for missing_record in missing_records:
                    writer.write(missing_record)
                    self.data_operation.review_manager.report_logger.info(
                        # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                        f" {missing_record} added"
                    )
                    if not silent_mode:
                        self.data_operation.review_manager.logger.info(
                            # f" {missing_record}".ljust(self.__PAD, " ") + " added"
                            f" {missing_record} added"
                        )

    def __create_paper(self, silent_mode: bool) -> None:
        if not silent_mode:
            self.data_operation.review_manager.report_logger.info("Create paper")
            self.data_operation.review_manager.logger.info("Create paper")

        title = "Paper template"
        readme_file = self.data_operation.review_manager.readme
        if readme_file.is_file():
            with open(readme_file, encoding="utf-8") as file:
                title = file.readline()
                title = title.replace("# ", "").replace("\n", "")

        author = self.__authorship_heuristic()

        review_type = self.data_operation.review_manager.settings.project.review_type

        package_manager = self.data_operation.review_manager.get_package_manager()
        check_operation = colrev.operation.CheckOperation(
            review_manager=self.data_operation.review_manager
        )

        review_type_endpoint = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.review_type,
            selected_packages=[{"endpoint": review_type}],
            operation=check_operation,
            ignore_not_available=False,
        )
        r_type_suffix = str(review_type_endpoint[review_type])
        paper_resource_path = Path(f"template/review_type/{r_type_suffix}/") / Path(
            "paper.md"
        )
        try:
            colrev.env.utils.retrieve_package_file(
                template_file=paper_resource_path, target=self.settings.paper_path
            )
        except FileNotFoundError:
            paper_resource_path = Path("template/paper_md") / Path("paper.md")
            colrev.env.utils.retrieve_package_file(
                template_file=paper_resource_path, target=self.settings.paper_path
            )

        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{review_type}}",
            new_string=r_type_suffix,
        )
        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{project_title}}",
            new_string=title,
        )
        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{colrev_version}}",
            new_string=str(self.data_operation.review_manager.get_colrev_versions()[1]),
        )
        colrev.env.utils.inplace_change(
            filename=self.settings.paper_path,
            old_string="{{author}}",
            new_string=author,
        )

    def __exclude_marked_records(
        self,
        *,
        synthesized_record_status_matrix: dict,
        records: typing.Dict,
    ) -> None:
        # pylint: disable=consider-using-with

        temp = tempfile.NamedTemporaryFile(dir=self.__temp_path)
        paper_path = self.settings.paper_path
        Path(temp.name).unlink(missing_ok=True)
        paper_path.rename(temp.name)

        screen_operation = self.data_operation.review_manager.get_screen_operation(
            notify_state_transition_operation=False
        )

        with open(temp.name, encoding="utf-8") as reader, open(
            paper_path, "w", encoding="utf-8"
        ) as writer:
            line = reader.readline()
            while line:
                if not line.startswith("EXCLUDE "):
                    writer.write(line)
                    line = reader.readline()
                    continue
                # TBD: how to cover reasons? (add a screening_criteria string in the first round?)
                # EXCLUDE Wagner2022
                # replaced by
                # EXCLUDE Wagner2022 because () digital () knowledge_work () contract
                # users: mark / add criteria

                record_id = (
                    line.replace("EXCLUDE ", "").replace("@", "").rstrip().lstrip()
                )
                if (
                    record_id in synthesized_record_status_matrix
                    and record_id in records
                ):
                    del synthesized_record_status_matrix[record_id]
                    screen_operation.screen(
                        record=colrev.record.Record(data=records[record_id]),
                        screen_inclusion=False,
                        screening_criteria="NA",
                    )

                    self.data_operation.review_manager.logger.info(
                        f"Excluded {record_id}"
                    )
                    self.data_operation.review_manager.report_logger.info(
                        f"Excluded {record_id}"
                    )
                else:
                    self.data_operation.review_manager.logger.error(
                        f"Did not find ID {record_id}"
                    )
                    writer.write(line)
                    line = reader.readline()
                    continue
                line = reader.readline()

    def __add_missing_records(
        self,
        *,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> None:
        missing_records = self.__get_data_page_missing(
            paper=self.settings.paper_path,
            record_id_list=list(synthesized_record_status_matrix.keys()),
        )
        missing_records = sorted(missing_records)
        # review_manager.logger.debug(f"missing_records: {missing_records}")

        self.__check_new_record_source_tag()

        if 0 == len(missing_records):
            if not silent_mode:
                self.data_operation.review_manager.report_logger.info(
                    f"All records included in {self.settings.paper_path.name}"
                )
            # review_manager.logger.debug(
            #     f"All records included in {self.settings.paper_path.name}"
            # )
        else:
            if not silent_mode:
                self.data_operation.review_manager.report_logger.info("Update paper")
                self.data_operation.review_manager.logger.info(
                    f"Update paper ({self.settings.paper_path.name})"
                )
            self.__add_missing_records_to_paper(
                missing_records=missing_records,
                silent_mode=silent_mode,
            )

    def __append_to_non_sample_references(self, *, filepath: Path) -> None:
        filedata = colrev.env.utils.get_package_file_content(file_path=filepath)

        if filedata:
            non_sample_records = {}
            with open(self.non_sample_references, encoding="utf8") as file:
                non_sample_records = (
                    self.data_operation.review_manager.dataset.load_records_dict(
                        load_str=file.read()
                    )
                )

            records_to_add = (
                self.data_operation.review_manager.dataset.load_records_dict(
                    load_str=filedata.decode("utf-8")
                )
            )

            # maybe prefix "non_sample_NameYear"? (also avoid conflicts with records.bib)
            duplicated_keys = [
                k for k in records_to_add.keys() if k in non_sample_records.keys()
            ]
            duplicated_records = [
                item
                for item in records_to_add.values()
                if item["ID"] in non_sample_records.keys()
            ]
            records_to_add = {
                k: v for k, v in records_to_add.items() if k not in non_sample_records
            }
            if duplicated_keys:
                self.data_operation.review_manager.logger.error(
                    f"{colors.RED}Cannot add {duplicated_keys} to "
                    f"{self.NON_SAMPLE_REFERENCES_RELATIVE}, "
                    f"please change ID and add manually:{colors.END}"
                )
                for duplicated_record in duplicated_records:
                    print(colrev.record.Record(data=duplicated_record))

            non_sample_records = {**non_sample_records, **records_to_add}
            self.data_operation.review_manager.dataset.save_records_dict_to_file(
                records=non_sample_records,
                save_path=self.non_sample_references,
            )
            self.data_operation.review_manager.dataset.add_changes(
                path=self.NON_SAMPLE_REFERENCES_RELATIVE
            )

    def __add_prisma_if_available(self, *, silent_mode: bool) -> None:
        prisma_endpoint_l = [
            d
            for d in self.data_operation.review_manager.settings.data.data_package_endpoints
            if d["endpoint"] == "colrev.prisma"
        ]
        if prisma_endpoint_l:
            if "PRISMA.png" not in self.settings.paper_path.read_text(encoding="UTF-8"):
                if not silent_mode:
                    self.data_operation.review_manager.logger.info(
                        "Add PRISMA diagram to paper"
                    )
                self.__append_to_non_sample_references(
                    filepath=Path("template/prisma/prisma-refs.bib"),
                )

                # pylint: disable=consider-using-with
                temp = tempfile.NamedTemporaryFile(dir=self.__temp_path)
                paper_path = self.settings.paper_path
                Path(temp.name).unlink(missing_ok=True)
                paper_path.rename(temp.name)
                with open(temp.name, encoding="utf-8") as reader, open(
                    paper_path, "w", encoding="utf-8"
                ) as writer:
                    line = reader.readline()
                    while line:
                        if "# Method" not in line:
                            writer.write(line)
                            line = reader.readline()
                            continue

                        writer.write(line)

                        filedata = colrev.env.utils.get_package_file_content(
                            file_path=Path("template/prisma/prisma_text.md")
                        )
                        if filedata:
                            writer.write(filedata.decode("utf-8"))

                        line = reader.readline()
                if not silent_mode:
                    print()

    def update_paper(
        self,
        *,
        records: typing.Dict,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> typing.Dict:
        """Update the paper (add new records after the NEW_RECORD_SOURCE_TAG)"""
        review_manager = self.data_operation.review_manager

        if not self.settings.paper_path.is_file():
            self.__create_paper(silent_mode=silent_mode)

        self.__add_missing_records(
            synthesized_record_status_matrix=synthesized_record_status_matrix,
            silent_mode=silent_mode,
        )

        self.__exclude_marked_records(
            synthesized_record_status_matrix=synthesized_record_status_matrix,
            records=records,
        )

        self.__add_prisma_if_available(silent_mode=silent_mode)

        review_manager.dataset.add_changes(path=self.settings.paper_path)

        return records

    def __create_non_sample_references_bib(self) -> None:
        if not self.NON_SAMPLE_REFERENCES_RELATIVE.is_file():
            try:
                retrieval_path = Path("template/paper_md/non_sample_references.bib")
                colrev.env.utils.retrieve_package_file(
                    template_file=retrieval_path,
                    target=self.non_sample_references,
                )
                self.data_operation.review_manager.dataset.add_changes(
                    path=self.non_sample_references
                )
            except AttributeError:
                pass

    def __call_docker_build_process(
        self, *, data_operation: colrev.ops.data.Data, script: str
    ) -> None:
        try:
            uid = os.stat(data_operation.review_manager.dataset.records_file).st_uid
            gid = os.stat(data_operation.review_manager.dataset.records_file).st_gid
            user = f"{uid}:{gid}"

            client = docker.from_env()
            msg = f"Running docker container created from image {self.pandoc_image}"
            data_operation.review_manager.report_logger.info(msg)

            client.containers.run(
                image=self.pandoc_image,
                command=script,
                user=user,
                volumes=[str(data_operation.review_manager.path) + ":/data"],
            )

        except docker.errors.ImageNotFound:
            data_operation.review_manager.logger.error("Docker image not found")
        except docker.errors.ContainerError as exc:
            if "Temporary failure in name resolution" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "pandoc service failed (tried to fetch csl without Internet connection)"
                ) from exc
            raise exc
        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Docker service not available ({exc}). Please install/start Docker."
            ) from exc

    def build_paper(self, *, data_operation: colrev.ops.data.Data) -> None:
        """Build the paper (based on pandoc)"""

        if not data_operation.review_manager.dataset.records_file.is_file():
            data_operation.review_manager.dataset.records_file.touch()

        if not self.settings.paper_path.is_file():
            data_operation.review_manager.logger.error(
                "File %s does not exist.", self.settings.paper_path
            )
            data_operation.review_manager.logger.info(
                "Complete processing and use colrev data"
            )
            return

        self.__retrieve_default_csl()
        self.__create_non_sample_references_bib()

        word_template = self.settings.word_template

        if not word_template.is_file():
            self.__retrieve_default_word_template()
        assert word_template.is_file()

        output_relative_path = self.settings.paper_output.relative_to(
            data_operation.review_manager.path
        )

        if (
            not data_operation.review_manager.dataset.has_changes(
                relative_path=self.paper_relative_path
            )
            and self.settings.paper_output.is_file()
        ):
            data_operation.review_manager.logger.debug(
                "Skipping paper build (no changes)"
            )
            return

        if data_operation.review_manager.verbose_mode:
            data_operation.review_manager.logger.info("Build paper")

        script = (
            f"{self.paper_relative_path} --filter pandoc-crossref --citeproc "
            + f"--reference-doc {word_template.relative_to(data_operation.review_manager.path)} "
            + f"--output {output_relative_path}"
        )

        Timer(
            1,
            lambda: self.__call_docker_build_process(
                data_operation=data_operation, script=script
            ),
        ).start()

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> None:
        """Update the data/paper"""

        if not data_operation.review_manager.dataset.has_changes(
            relative_path=self.paper_relative_path, change_type="unstaged"
        ):
            records = self.update_paper(
                records=records,
                synthesized_record_status_matrix=synthesized_record_status_matrix,
                silent_mode=silent_mode,
            )
        else:
            if not silent_mode:
                data_operation.review_manager.logger.warning(
                    f"{colors.RED}Skipping updates of "
                    f"{self.paper_relative_path} due to unstaged changes{colors.END}"
                )

        if not data_operation.review_manager.in_ci_environment():
            self.build_paper(data_operation=data_operation)

    def __get_to_synthesize_in_paper(
        self, *, paper: Path, records_for_synthesis: list
    ) -> list:
        in_paper_to_synthesize = []
        if paper.is_file():
            with open(paper, encoding="utf-8") as file:
                for line in file:
                    if self.NEW_RECORD_SOURCE_TAG in line:
                        while line:
                            line = file.readline()
                            if re.search(r"- @.*", line):
                                record_id = re.findall(r"- @(.*)$", line)
                                in_paper_to_synthesize.append(record_id[0])
                                if line == "\n":
                                    break

            in_paper_to_synthesize = [
                x for x in in_paper_to_synthesize if x in records_for_synthesis
            ]
        else:
            in_paper_to_synthesize = records_for_synthesis
        return in_paper_to_synthesize

    def __get_synthesized_ids_paper(
        self, *, paper: Path, synthesized_record_status_matrix: dict
    ) -> list:
        in_paper_to_synthesize = self.__get_to_synthesize_in_paper(
            paper=paper,
            records_for_synthesis=list(synthesized_record_status_matrix.keys()),
        )
        # Assuming that all records have been added to the paper before
        synthesized_ids = [
            x
            for x in list(synthesized_record_status_matrix.keys())
            if x not in in_paper_to_synthesize
        ]

        return synthesized_ids

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""
        # Update status / synthesized_record_status_matrix
        synthesized_in_paper = self.__get_synthesized_ids_paper(
            paper=self.settings.paper_path,
            synthesized_record_status_matrix=synthesized_record_status_matrix,
        )
        for syn_id in synthesized_in_paper:
            if syn_id in synthesized_record_status_matrix:
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = True
            else:
                print(f"Error: {syn_id} not int {synthesized_in_paper}")

    def get_advice(
        self,
        review_manager: colrev.review_manager.ReviewManager,  # pylint: disable=unused-argument
    ) -> dict:
        """Get advice on the next steps (for display in the colrev status)"""

        data_endpoint = "Data operation [paper_md endpoint]: "

        advice = {
            "msg": f"{data_endpoint}"
            + "\n    1. Edit the paper (data/data/paper.md)"
            + "\n    2. To build the paper (output/paper.docx), run: colrev data"
            + "\n    3. To create a version, run: git add data/data/paper.md && "
            + "git commit -m 'update paper'",
            "detailed_msg": "... with a link to the docs etc.",
        }
        return advice


class PaperMarkdownRecordSourceTagError(Exception):
    """NEW_RECORD_SOURCE_TAG not found in paper.md"""

    def __init__(self, msg: str) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


if __name__ == "__main__":
    pass
