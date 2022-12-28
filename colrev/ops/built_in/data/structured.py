#! /usr/bin/env python
"""Structured data extraction as part of the data operations"""
from __future__ import annotations

import csv
import itertools
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class StructuredData(JsonSchemaMixin):
    """Summarize the literature in a structured data extraction (a table)"""

    @dataclass
    class StructuredDataSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for StructuredData"""

        endpoint: str
        version: str
        # gh_issue https://github.com/geritwagner/colrev/issues/79
        # Field dataclass (name, explanation, data_type)
        fields: dict
        data_path_relative: Path = Path("data/data.csv")

        _details = {
            "fields": {"tooltip": "Fields for the structured data extraction"},
        }

    settings_class = StructuredDataSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,
        settings: dict,
    ) -> None:

        self.settings = self.settings_class.load_settings(data=settings)
        self.data_path = (
            data_operation.review_manager.path / self.settings.data_path_relative
        )

    def get_default_setup(self) -> dict:
        """Get the default setup"""
        structured_endpoint_details = {
            "endpoint": "colrev_built_in.structured",
            "version": "0.1",
            "fields": [
                {
                    "name": "field name",
                    "explanation": "explanation",
                    "data_type": "data type",
                }
            ],
        }
        return structured_endpoint_details

    def validate_structured_data(self) -> None:
        """Validate the extracted data"""

        # gh_issue https://github.com/geritwagner/colrev/issues/79
        # implement the following:
        # # Check whether there are duplicate IDs in data.csv
        # if not data['ID'].is_unique:
        #     raise some error (data[data.duplicated(['ID'])].ID.tolist())

        # # Check consistency: all IDs in data.csv in data/records.bib
        # missing_IDs = [ID for
        #                 ID in data['ID'].tolist()
        #                 if ID not in IDs]
        # if not len(missing_IDs) == 0:
        #     raise some error ('IDs in data.csv not in RECORDS_FILE: ' +
        #             str(set(missing_IDs)))

        # # Check consistency: data -> inclusion_2
        # data_IDs = data['ID'].tolist()
        # screen_IDs = \
        #     screen['ID'][screen['inclusion_2'] == 'yes'].tolist()
        # violations = [ID for ID in set(
        #     data_IDs) if ID not in set(screen_IDs)]
        # if len(violations) != 0:
        #     raise some error ('IDs in DATA not coded as inclusion_2=yes: ' +
        #           f'{violations}')

        return

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,
        synthesized_record_status_matrix: dict,
    ) -> None:
        """Update the data/structured data extraction"""

        def update_structured_data(
            *,
            review_manager: colrev.review_manager.ReviewManager,
            synthesized_record_status_matrix: dict,
        ) -> typing.Dict:

            if not self.data_path.is_file():

                coding_dimensions_str = input(
                    "\n\nEnter columns for data extraction (comma-separted)"
                )
                coding_dimensions = coding_dimensions_str.replace(" ", "_").split(",")

                data_list = []
                for included_id in list(synthesized_record_status_matrix.keys()):
                    item = [[included_id], ["TODO"] * len(coding_dimensions)]
                    data_list.append(list(itertools.chain(*item)))

                data_df = pd.DataFrame(data_list, columns=["ID"] + coding_dimensions)
                data_df.sort_values(by=["ID"], inplace=True)

                data_df.to_csv(self.data_path, index=False, quoting=csv.QUOTE_ALL)

            else:

                nr_records_added = 0

                data_df = pd.read_csv(self.data_path, dtype=str)

                for record_id in list(synthesized_record_status_matrix.keys()):
                    # skip when already available
                    if 0 < len(data_df[data_df["ID"].str.startswith(record_id)]):
                        continue

                    add_record = pd.DataFrame({"ID": [record_id]})
                    add_record = add_record.reindex(
                        columns=data_df.columns, fill_value="TODO"
                    )
                    data_df = pd.concat(
                        [data_df, add_record], axis=0, ignore_index=True
                    )
                    nr_records_added = nr_records_added + 1

                data_df.sort_values(by=["ID"], inplace=True)

                data_df.to_csv(self.data_path, index=False, quoting=csv.QUOTE_ALL)

                review_manager.report_logger.info(
                    f"{nr_records_added} records added ({self.settings.data_path_relative})"
                )
                review_manager.logger.info(
                    f"{nr_records_added} records added ({self.settings.data_path_relative})"
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

        advice = {
            "msg": f"The data extraction sheed is at {self.settings.data_path_relative}",
            "detailed_msg": "TODO",
        }
        return advice


if __name__ == "__main__":
    pass
