#! /usr/bin/env python
"""Creation of a Zettlr database as part of the data operations"""
from __future__ import annotations

import configparser
import datetime
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data

# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class Zettlr(JsonSchemaMixin):
    """Export the sample into a Zettlr database"""

    zettlr_bib_item_resource_path = Path("template/zettlr/") / Path(
        "zettlr_bib_item.md"
    )
    zettlr_resource_path = Path("template/zettlr/") / Path("zettlr.md")

    @dataclass
    class ZettlrSettings(colrev.env.package_manager.DefaultSettings, JsonSchemaMixin):
        """Settings for Zettlr"""

        endpoint: str
        version: str
        config: dict

        # _details = {
        #     "config": {
        #         "tooltip": "TODO"
        #     },
        # }

    settings_class = ZettlrSettings

    NEW_RECORD_SOURCE_TAG = "<!-- NEW_RECORD_SOURCE -->"
    ZETTLR_PATH_RELATIVE = Path("data/zettlr")
    ZETTLR_CONFIG_PATH_RELATIVE = Path(".zettlr_config.ini")

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:

        self.settings = self.settings_class.load_settings(data=settings)
        self.endpoint_path = (
            data_operation.review_manager.path / self.ZETTLR_PATH_RELATIVE
        )
        self.zettlr_config_path = (
            data_operation.review_manager.path / self.ZETTLR_CONFIG_PATH_RELATIVE
        )

    def get_default_setup(self) -> dict:
        """Get the default setup"""
        zettlr_endpoint_details = {
            "endpoint": "colrev_built_in.zettlr",
            "version": "0.1",
            "config": {},
        }
        return zettlr_endpoint_details

    def __get_zettlr_missing(self, *, endpoint_path: Path, included: list) -> list:
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

    def __add_missing_records_to_zettlr(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        paper_path: Path,
        missing_records: list,
    ) -> None:
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

    def __create_record_item_pages(
        self, *, data_operation: colrev.ops.data.Data, missing_record_fields: list
    ) -> None:
        for missing_record_field in missing_record_fields:
            paper_id, record_field = missing_record_field
            print(paper_id + record_field)
            zettlr_path = self.endpoint_path / Path(paper_id)

            colrev.env.utils.retrieve_package_file(
                template_file=self.zettlr_bib_item_resource_path, target=zettlr_path
            )
            colrev.env.utils.inplace_change(
                filename=zettlr_path,
                old_string="{{project_name}}",
                new_string=record_field,
            )
            with zettlr_path.open("a") as file:
                file.write(f"\n\n@{record_field}\n")

            data_operation.review_manager.dataset.add_changes(path=zettlr_path)

    def __append_missing_records(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        current_dt: datetime.datetime,
        zettlr_path: Path,
        silent_mode: bool,
    ) -> None:

        records_dict = data_operation.review_manager.dataset.load_records_dict()
        included = data_operation.get_record_ids_for_synthesis(records_dict)
        missing_records = self.__get_zettlr_missing(
            endpoint_path=self.endpoint_path, included=included
        )
        if len(missing_records) == 0:
            if not silent_mode:
                print("All records included. Nothing to export.")
            return

        print(missing_records)

        missing_records = sorted(missing_records)
        missing_record_fields = []
        for i, missing_record in enumerate(missing_records):
            unique_timestamp = current_dt - datetime.timedelta(seconds=i)
            missing_record_fields.append(
                [unique_timestamp.strftime("%Y%m%d%H%M%S") + ".md", missing_record]
            )

        self.__add_missing_records_to_zettlr(
            review_manager=data_operation.review_manager,
            paper_path=zettlr_path,
            missing_records=[
                "\n- [[" + i + "]] @" + r + "\n" for i, r in missing_record_fields
            ],
        )

        data_operation.review_manager.dataset.add_changes(path=zettlr_path)

        self.__create_record_item_pages(
            data_operation=data_operation, missing_record_fields=missing_record_fields
        )

        data_operation.review_manager.create_commit(
            msg="Setup zettlr", script_call="colrev data"
        )

        print("TODO: recommend zettlr/snippest, adding tags")

    def __retrieve_setup(
        self, *, data_operation: colrev.ops.data.Data, current_dt: datetime.datetime
    ) -> Path:
        if self.zettlr_config_path.is_file():
            zettlr_config = configparser.ConfigParser()
            zettlr_config.read(self.zettlr_config_path)
            zettlr_path = self.endpoint_path / Path(
                zettlr_config.get("general", "main")
            )

        else:
            unique_timestamp = current_dt + datetime.timedelta(seconds=3)
            fname = Path(unique_timestamp.strftime("%Y%m%d%H%M%S") + ".md")
            zettlr_path = self.endpoint_path / fname

            zettlr_config = configparser.ConfigParser()
            zettlr_config.add_section("general")
            zettlr_config["general"]["main"] = str(fname)
            with open(self.zettlr_config_path, "w", encoding="utf-8") as configfile:
                zettlr_config.write(configfile)
            data_operation.review_manager.dataset.add_changes(
                path=self.zettlr_config_path
            )

            colrev.env.utils.retrieve_package_file(
                template_file=self.zettlr_resource_path, target=zettlr_path
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
        return zettlr_path

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
        silent_mode: bool,  # pylint: disable=unused-argument
    ) -> None:
        """Update the data/zettlr notes"""

        if not silent_mode:
            data_operation.review_manager.logger.info("Export to zettlr endpoint")

        current_dt = datetime.datetime.now()
        zettlr_path = self.__retrieve_setup(
            data_operation=data_operation, current_dt=current_dt
        )

        self.__append_missing_records(
            data_operation=data_operation,
            current_dt=current_dt,
            zettlr_path=zettlr_path,
            silent_mode=silent_mode,
        )

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""

        print("not yet implemented")

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True

    def get_advice(
        self,
        review_manager: colrev.review_manager.ReviewManager,  # pylint: disable=unused-argument
    ) -> dict:
        """Get advice on the next steps (for display in the colrev status)"""

        data_endpoint = "Data operation [zettlr data endpoint]: "

        advice = {
            "msg": f"{data_endpoint}"
            + f"\n    - The zettlr project is updated automatically ({self.ZETTLR_PATH_RELATIVE})",
            "detailed_msg": "TODO",
        }
        return advice


if __name__ == "__main__":
    pass
