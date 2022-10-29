#! /usr/bin/env python
"""SearchSource: Europe PMC"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class EuropePMCSearchSource(JsonSchemaMixin):
    """SearchSource for Europe PMC"""

    # settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = (
        "https://www.ebi.ac.uk/europepmc/webservices/rest/article/{{europe_pmc_id}}"
    )

    @dataclass
    class EuropePMCSearchSourceSettings(JsonSchemaMixin):
        """Settings for EuropePMCSearchSource"""

        # pylint: disable=duplicate-code
        # pylint: disable=too-many-instance-attributes
        endpoint: str
        filename: Path
        search_type: colrev.settings.SearchType
        source_identifier: str
        search_parameters: dict
        load_conversion_package_endpoint: dict
        comment: typing.Optional[str]

        _details = {
            "search_parameters": {
                "tooltip": "Currently supports a scope item "
                "with venue_key and journal_abbreviated fields."
            },
        }

    settings_class = EuropePMCSearchSourceSettings

    def __init__(
        self,
        *,
        source_operation: colrev.operation.CheckOperation,
        settings: dict,
    ) -> None:

        if "query" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "query required in search_parameters"
            )

        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __retrieve_and_append(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        records_dict: typing.Dict[str, typing.Dict],
    ) -> typing.Dict[str, typing.Dict]:

        search_operation.review_manager.logger.info(
            f"Retrieving from Europe PMC: {self.settings.search_parameters['query']}"
        )

        available_ids = [
            x["europe_pmc_id"] for x in records_dict.values() if "europe_pmc_id" in x
        ]
        max_id = (
            max(
                [int(x["ID"]) for x in records_dict.values() if x["ID"].isdigit()] + [1]
            )
            + 1
        )

        europe_pmc_connector = (
            colrev.ops.built_in.database_connectors.EuropePMCConnector
        )
        record_input = colrev.record.Record(
            data={"title": self.settings.search_parameters["query"]}
        )

        for retrieved_record in europe_pmc_connector.europe_pcmc_query(
            review_manager=search_operation.review_manager,
            record_input=record_input,
            most_similar_only=False,
        ):

            if "colrev_data_provenance" in retrieved_record.data:
                del retrieved_record.data["colrev_data_provenance"]
            if "colrev_masterdata_provenance" in retrieved_record.data:
                del retrieved_record.data["colrev_masterdata_provenance"]

            if retrieved_record.data["europe_pmc_id"] not in available_ids:
                retrieved_record.data["ID"] = str(max_id).rjust(6, "0")
                available_ids.append(retrieved_record.data["europe_pmc_id"])

                records_dict[retrieved_record.data["ID"]] = retrieved_record.data
                max_id += 1

        return records_dict

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of Europe PMC"""

        # https://europepmc.org/RestfulWebService

        search_operation.review_manager.logger.info(
            f"Retrieve Europe PMC: {self.settings.search_parameters}"
        )

        records: list = []
        if self.settings.filename.is_file():
            with open(self.settings.filename, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())

        try:

            records_dict = {r["ID"]: r for r in records}
            records_dict = self.__retrieve_and_append(
                search_operation=search_operation,
                records_dict=records_dict,
            )

            search_operation.save_feed_file(
                records=records_dict, feed_file=self.settings.filename
            )

        except UnicodeEncodeError:
            print("UnicodeEncodeError - this needs to be fixed at some time")
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError,
        ):
            pass

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for Europe PMC"""

        result = {"confidence": 0.0}
        if "europe_pmc_id" in data:
            result["confidence"] = 1.0

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for Europe PMC"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for Europe PMC"""
        record.data["author"].rstrip(".")
        record.data["title"].rstrip(".")
        return record


if __name__ == "__main__":
    pass
