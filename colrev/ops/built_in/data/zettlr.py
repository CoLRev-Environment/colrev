#! /usr/bin/env python
from __future__ import annotations

import configparser
import datetime
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.env.utils
import colrev.process
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data

# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.process.DataEndpoint)
class ZettlrEndpoint:
    """Export the sample into a Zettlr database"""

    @dataclass
    class ZettlrSettings:
        name: str
        version: str
        config: dict

        # _details = {
        #     "config": {
        #         "tooltip": "TODO"
        #     },
        # }

    settings_class = ZettlrSettings

    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def get_default_setup(self) -> dict:
        zettlr_endpoint_details = {
            "endpoint": "ZETTLR",
            "version": "0.1",
            "config": {},
        }
        return zettlr_endpoint_details

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:

        data_operation.review_manager.logger.info("Export to zettlr endpoint")
        endpoint_path = data_operation.review_manager.path / Path("data/zettlr")

        # TODO : check if a main-zettlr file exists.

        def get_zettlr_missing(*, endpoint_path, included) -> list:
            in_zettelkasten = []

            for md_file in endpoint_path.glob("*.md"):
                with open(md_file, encoding="utf-8") as file:
                    line = file.readline()
                    while line:
                        if "title:" in line:
                            paper_id = line[line.find('"') + 1 : line.rfind('"')]
                            in_zettelkasten.append(paper_id)
                        line = file.readline()

            return [x for x in included if x not in in_zettelkasten]

        def add_missing_records_to_manuscript(
            *,
            review_manager: colrev.review_manager.ReviewManager,
            paper_path: Path,
            missing_records: list,
        ) -> None:
            # pylint: disable=consider-using-with
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

        zettlr_config_path = endpoint_path / Path(".zettlr_config.ini")
        current_dt = datetime.datetime.now()
        if zettlr_config_path.is_file():
            zettlr_config = configparser.ConfigParser()
            zettlr_config.read(zettlr_config_path)
            zettlr_path = endpoint_path / Path(zettlr_config.get("general", "main"))

        else:
            unique_timestamp = current_dt + datetime.timedelta(seconds=3)
            zettlr_resource_path = Path("template/zettlr/") / Path("zettlr.md")
            fname = Path(unique_timestamp.strftime("%Y%m%d%H%M%S") + ".md")
            zettlr_path = endpoint_path / fname

            zettlr_config = configparser.ConfigParser()
            zettlr_config.add_section("general")
            zettlr_config["general"]["main"] = str(fname)
            with open(zettlr_config_path, "w", encoding="utf-8") as configfile:
                zettlr_config.write(configfile)
            data_operation.review_manager.dataset.add_changes(path=zettlr_config_path)

            colrev.env.utils.retrieve_package_file(
                template_file=zettlr_resource_path, target=zettlr_path
            )
            title = "PROJECT_NAME"
            if data_operation.review_manager.readme.is_file():
                with open(
                    data_operation.review_manager.readme, encoding="utf-8"
                ) as file:
                    title = file.readline()
                    title = title.replace("# ", "").replace("\n", "")

            colrev.env.utils.inplace_change(
                filename=zettlr_path, old_string="{{project_title}}", new_string=title
            )
            # author = authorship_heuristic(review_manager)
            data_operation.review_manager.create_commit(
                msg="Add zettlr endpoint", script_call="colrev data"
            )

        records_dict = data_operation.review_manager.dataset.load_records_dict()
        included = data_operation.get_record_ids_for_synthesis(records_dict)
        missing_records = get_zettlr_missing(
            endpoint_path=endpoint_path, included=included
        )

        if len(missing_records) == 0:
            print("All records included. Nothing to export.")
        else:
            print(missing_records)

            missing_records = sorted(missing_records)
            missing_record_fields = []
            for i, missing_record in enumerate(missing_records):
                unique_timestamp = current_dt - datetime.timedelta(seconds=i)
                missing_record_fields.append(
                    [unique_timestamp.strftime("%Y%m%d%H%M%S") + ".md", missing_record]
                )

            add_missing_records_to_manuscript(
                review_manager=data_operation.review_manager,
                paper_path=zettlr_path,
                missing_records=[
                    "\n- [[" + i + "]] @" + r + "\n" for i, r in missing_record_fields
                ],
            )

            data_operation.review_manager.dataset.add_changes(path=zettlr_path)

            zettlr_resource_path = Path("template/zettlr/") / Path("zettlr_bib_item.md")
            for missing_record_field in missing_record_fields:
                paper_id, record_field = missing_record_field
                print(paper_id + record_field)
                zettlr_path = endpoint_path / Path(paper_id)

                colrev.env.utils.retrieve_package_file(
                    template_file=zettlr_resource_path, target=zettlr_path
                )
                colrev.env.utils.inplace_change(
                    filename=zettlr_path,
                    old_string="{{project_name}}",
                    new_string=record_field,
                )
                with zettlr_path.open("a") as file:
                    file.write(f"\n\n@{record_field}\n")

                data_operation.review_manager.dataset.add_changes(path=zettlr_path)

            data_operation.review_manager.create_commit(
                msg="Setup zettlr", script_call="colrev data"
            )

            print("TODO: recommend zettlr/snippest, adding tags")

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        # TODO : not yet implemented!
        # TODO : records mentioned after the NEW_RECORD_SOURCE tag are not synthesized.

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True


if __name__ == "__main__":
    pass
