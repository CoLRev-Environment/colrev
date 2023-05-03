#! /usr/bin/env python
"""Structured data extraction as part of the data operations"""
from __future__ import annotations

import csv
import typing
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from git.exc import GitCommandError

import colrev.env.package_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record
import colrev.ui_cli.cli_colors as colors

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.data


# an option: https://pypi.org/project/csv-schema/
@dataclass
class Field(JsonSchemaMixin):
    """Field definition"""

    name: str
    explanation: str
    data_type: str


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class StructuredData(JsonSchemaMixin):
    """Summarize the literature in a structured data extraction (a table)"""

    settings: StructuredDataSettings
    ci_supported: bool = False

    @dataclass
    class StructuredDataSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for StructuredData"""

        endpoint: str
        version: str
        fields: typing.List[Field]
        data_path_relative: Path = Path("data.csv")

        _details = {
            "fields": {"tooltip": "Fields for the structured data extraction"},
        }

    settings_class = StructuredDataSettings

    __FULL_DATA_FIELD_EXPLANATION = """Explanation: Data fields are used in the coding tables.
Example 1:
    - name           : summary
    - explanation    : Brief summary of the principal findings
    - data_type      : str

Example 2:
    - name           : sample_size
    - explanation    : Sample size of the study
    - data_type      : int
    """

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:
        if "version" not in settings:
            settings["version"] = "0.1"

        if "fields" not in settings:
            settings["fields"] = []
        if "data_path_relative" not in settings:
            settings["data_path_relative"] = Path("data.csv")

        self.settings = self.settings_class.load_settings(data=settings)
        self.data_path = (
            data_operation.review_manager.data_dir / self.settings.data_path_relative
        )
        self.review_manager = data_operation.review_manager

    def get_default_setup(self) -> dict:
        """Get the default setup"""

        # Note : add fields interactively upon update_data()

        structured_endpoint_details = {
            "endpoint": "colrev.structured",
            "version": "0.1",
            "fields": [],
            "data_path_relative": "data/data.csv",
        }
        return structured_endpoint_details

    def validate_structured_data(self) -> None:
        """Validate the extracted data"""

        if not self.data_path.is_file():
            return

        data_df = pd.read_csv(self.data_path, dtype=str)

        # Check for duplicate IDs
        if not data_df["ID"].is_unique:
            raise colrev_exceptions.DataException(
                msg=f"duplicates in {self.settings.data_path_relative}: "
                + ",".join(data_df[data_df.duplicated(["ID"])].ID.tolist())
            )

        # Check consistency: data -> inclusion_2
        data_ids = data_df["ID"].tolist()
        records = self.review_manager.dataset.load_records_dict()
        for data_id in data_ids:
            if data_id not in records:
                raise colrev_exceptions.DataException(
                    msg=f"{data_id} in {self.settings.data_path_relative} not in records"
                )
            if records[data_id]["colrev_status"] not in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                raise colrev_exceptions.DataException(
                    msg=f"{data_id} in {self.settings.data_path_relative} "
                    + "not in [rev_included, rev_synthesized]"
                )

        # Note : missing IDs are added through update_data

        return

    def __set_fields(self) -> None:
        self.review_manager.logger.info("Add fields for data extraction")
        try:
            _ = self.review_manager.dataset.get_repo()
        except GitCommandError:
            return

        print(self.__FULL_DATA_FIELD_EXPLANATION)
        while "y" == input("Add a data field [y,n]?"):
            short_name = input("Provide a short name: ")
            explanation = input("Provide a short explanation: ")
            data_type = input("Provide the data type (str, int, double):")

            self.settings.fields.append(
                Field(
                    **{
                        "name": short_name,
                        "explanation": explanation,
                        "data_type": data_type,
                    }
                )
            )

            print()

        # Note : the following should be easier...
        for i, candidate in enumerate(
            self.review_manager.settings.data.data_package_endpoints
        ):
            if candidate.get("data_path_relative", "NA") == str(
                self.settings.data_path_relative
            ):
                self.review_manager.settings.data.data_package_endpoints[i] = asdict(
                    self.settings, dict_factory=colrev.env.utils.custom_asdict_factory
                )
        self.review_manager.save_settings()

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,
        silent_mode: bool,
    ) -> None:
        """Update the data/structured data extraction"""

        def update_structured_data(
            *,
            review_manager: colrev.review_manager.ReviewManager,
            synthesized_record_status_matrix: dict,
        ) -> typing.Dict:
            if not self.data_path.is_file():
                self.__set_fields()

                field_names = [f["name"] for f in self.settings.fields]
                data_df = pd.DataFrame([], columns=["ID"] + field_names)
                data_df.sort_values(by=["ID"], inplace=True)

                data_df.to_csv(self.data_path, index=False, quoting=csv.QUOTE_ALL)

            nr_records_added = 0

            if not silent_mode:
                self.review_manager.report_logger.info("Update structured data")
                self.review_manager.logger.info(
                    f"Update structured data ({self.settings.data_path_relative})"
                )

            data_df = pd.read_csv(self.data_path, dtype=str)

            for record_id in list(synthesized_record_status_matrix.keys()):
                # skip when already available
                if 0 < len(data_df[data_df["ID"].str.startswith(record_id)]):
                    continue

                add_record = pd.DataFrame({"ID": [record_id]})
                add_record = add_record.reindex(
                    columns=data_df.columns, fill_value="TODO"
                )
                data_df = pd.concat([data_df, add_record], axis=0, ignore_index=True)
                review_manager.logger.info(
                    f" {colors.GREEN}{record_id}".ljust(45)
                    + f"add to structured_data{colors.END}"
                )
                nr_records_added = nr_records_added + 1

            data_df.sort_values(by=["ID"], inplace=True)

            data_df.to_csv(self.data_path, index=False, quoting=csv.QUOTE_ALL)

            if not (0 == nr_records_added and silent_mode):
                review_manager.logger.info(
                    f"Added to {self.settings.data_path_relative}".ljust(24)
                    + f"{nr_records_added}".rjust(15, " ")
                    + " records"
                )

                review_manager.logger.info(
                    f"Added to {self.settings.data_path_relative}".ljust(24)
                    + f"{nr_records_added}".rjust(15, " ")
                    + " records"
                )
            return records

        self.validate_structured_data()
        records = update_structured_data(
            review_manager=data_operation.review_manager,
            synthesized_record_status_matrix=synthesized_record_status_matrix,
        )

        data_operation.review_manager.dataset.add_changes(
            path=self.settings.data_path_relative
        )

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""

        def get_data_extracted(
            data_path: Path, records_for_data_extraction: list
        ) -> list:
            data_extracted = []
            data_df = pd.read_csv(data_path)

            for record in records_for_data_extraction:
                drec = data_df.loc[data_df["ID"] == record]
                if 1 == drec.shape[0]:
                    if "TODO" not in drec.iloc[0].tolist():
                        data_extracted.append(drec.loc[drec.index[0], "ID"])

            data_extracted = [
                x for x in data_extracted if x in records_for_data_extraction
            ]
            return data_extracted

        def get_structured_data_extracted(
            *, synthesized_record_status_matrix: typing.Dict, data_path: Path
        ) -> list:
            if not data_path.is_file():
                return []

            data_extracted = get_data_extracted(
                data_path, list(synthesized_record_status_matrix.keys())
            )
            data_extracted = [
                x
                for x in data_extracted
                if x in list(synthesized_record_status_matrix.keys())
            ]
            return data_extracted

        structured_data_extracted = get_structured_data_extracted(
            synthesized_record_status_matrix=synthesized_record_status_matrix,
            data_path=self.data_path,
        )

        for syn_id in structured_data_extracted:
            if syn_id in synthesized_record_status_matrix:
                synthesized_record_status_matrix[syn_id][endpoint_identifier] = True
            else:
                print(f"Error: {syn_id} not int " f"{synthesized_record_status_matrix}")

    def get_advice(
        self,
        review_manager: colrev.review_manager.ReviewManager,  # pylint: disable=unused-argument
    ) -> dict:
        """Get advice on the next steps (for display in the colrev status)"""

        data_endpoint = "Data operation [structured data endpoint]: "

        if self.settings.data_path_relative.is_file():
            advice = {
                "msg": f"{data_endpoint}"
                + f"\n    - Complete the data extraction ({self.settings.data_path_relative})",
                "detailed_msg": "TODO",
            }
        else:
            advice = {}
        return advice


if __name__ == "__main__":
    pass
