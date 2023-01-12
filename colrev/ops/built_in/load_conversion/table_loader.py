#! /usr/bin/env python
"""Load conversion of tables (xlsx, csv)"""
from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class TableLoadUtility:
    """Utility for tables loading"""

    @classmethod
    def preprocess_records(cls, *, records: list) -> dict:
        """Preprocess records imported from a table"""

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements

        next_id = 1
        for record_dict in records:

            if "ENTRYTYPE" not in record_dict:
                if "" != record_dict.get("journal", ""):
                    record_dict["ENTRYTYPE"] = "article"
                if "" != record_dict.get("booktitle", ""):
                    record_dict["ENTRYTYPE"] = "inproceedings"
                else:
                    record_dict["ENTRYTYPE"] = "misc"

            if "ID" not in record_dict:
                if "citation_key" in record_dict:
                    record_dict["ID"] = record_dict["citation_key"]
                else:
                    record_dict["ID"] = next_id
                    next_id += 1

            for key, value in record_dict.items():
                record_dict[key] = str(value)

            if "authors" in record_dict and "author" not in record_dict:
                record_dict["author"] = record_dict["authors"]
                del record_dict["authors"]
            if "publication_year" in record_dict and "year" not in record_dict:
                record_dict["year"] = record_dict["publication_year"]
                del record_dict["publication_year"]
            # Note: this is a simple heuristic:
            if (
                "journal/book" in record_dict
                and "journal" not in record_dict
                and "doi" in record_dict
            ):
                record_dict["journal"] = record_dict["journal/book"]
                del record_dict["journal/book"]

        if all("ID" in r for r in records):
            records_dict = {r["ID"]: r for r in records}
        else:
            records_dict = {}
            for i, record in enumerate(records):
                records_dict[str(i)] = record

        for r_dict in records_dict.values():
            if "no year" == r_dict.get("year", "NA"):
                del r_dict["year"]
            if "no journal" == r_dict.get("journal", "NA"):
                del r_dict["journal"]
            if "no volume" == r_dict.get("volume", "NA"):
                del r_dict["volume"]
            if "no pages" == r_dict.get("pages", "NA"):
                del r_dict["pages"]
            if "no issue" == r_dict.get("issue", "NA"):
                del r_dict["issue"]
            if "no number" == r_dict.get("number", "NA"):
                del r_dict["number"]
            if "no doi" == r_dict.get("doi", "NA"):
                del r_dict["doi"]
            if "no type" == r_dict.get("type", "NA"):
                del r_dict["type"]
            if "author_count" in r_dict:
                del r_dict["author_count"]
            if "no Number-of-Cited-References" == r_dict.get(
                "number_of_cited_references", "NA"
            ):
                del r_dict["number_of_cited_references"]
            if "no file" in r_dict.get("file_name", "NA"):
                del r_dict["file_name"]
            if "times_cited" == r_dict.get("times_cited", "NA"):
                del r_dict["times_cited"]

        return records_dict


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
@dataclass
class CSVLoader(JsonSchemaMixin):

    """Loads csv files (based on pandas)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["csv"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        try:
            data = pd.read_csv(source.filename)
        except pd.errors.ParserError as exc:
            raise colrev_exceptions.ImportException(
                f"Error: Not a csv file? {source.filename.name}"
            ) from exc

        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data.columns = data.columns.str.lower()
        records_value_list = data.to_dict("records")

        records_dict = TableLoadUtility.preprocess_records(records=records_value_list)

        if not all("ID" in r for r in records_dict.values()):
            for i, record in enumerate(records_dict.values()):
                record["ID"] = str(i).rjust(6, "0")

        records = {r["ID"]: r for r in records_dict.values()}

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[asdict(source)],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )

        return records


@zope.interface.implementer(
    colrev.env.package_manager.LoadConversionPackageEndpointInterface
)
class ExcelLoader:
    """Loads Excel (xls, xlsx) files (based on pandas)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    supported_extensions = ["xls", "xlsx"]

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)

    def load(
        self, load_operation: colrev.ops.load.Load, source: colrev.settings.SearchSource
    ) -> dict:
        """Load records from the source"""

        try:
            data = pd.read_excel(
                source.filename, dtype=str
            )  # dtype=str to avoid type casting
        except pd.errors.ParserError:
            load_operation.review_manager.logger.error(
                f"Error: Not an xlsx file: {source.filename.name}"
            )
            return {}

        data.columns = data.columns.str.replace(" ", "_")
        data.columns = data.columns.str.replace("-", "_")
        data.columns = data.columns.str.lower()
        record_value_list = data.to_dict("records")
        records_dicts = TableLoadUtility.preprocess_records(records=record_value_list)
        records = {r["ID"]: r for r in records_dicts}

        endpoint_dict = load_operation.package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.search_source,
            selected_packages=[asdict(source)],
            operation=load_operation,
            ignore_not_available=False,
        )
        endpoint = endpoint_dict[source.endpoint]

        records = endpoint.load_fixes(  # type: ignore
            load_operation, source=source, records=records
        )
        return records


if __name__ == "__main__":
    pass
