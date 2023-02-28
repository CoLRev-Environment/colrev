#! /usr/bin/env python
"""SearchSource: systematic-review-datasets"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path

import zope.interface
from crossref.restful import Etiquette
from crossref.restful import Works
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.utils as connector_utils
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class SystematicReviewDatasetsSearchSource(JsonSchemaMixin):
    """SearchSource for systematic-review-datasets

    https://github.com/asreview/systematic-review-datasets

    csv files available in the releases (output directories) are supported:
    https://github.com/asreview/systematic-review-datasets/tags

    csv files containing article IDs are supported by source-specific preparation.
    metadata is added based on dois and pubmedid (openalex is not yet supported)

    """

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{ID}}"
    search_type = colrev.settings.SearchType.DB
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "systematic-review-datasets"
    link = "https://about.proquest.com/en/products-services/abi_inform_complete/"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        _, email = source_operation.review_manager.get_committer()
        self.etiquette = Etiquette(
            "CoLRev",
            version("colrev"),
            "https://github.com/CoLRev-Ecosystem/colrev",
            email,
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for systematic-review-datasets"""

        result = {"confidence": 0.0}

        if "doi,pmid,openalex_id,label_included" in data:
            result["confidence"] = 1.0

        if '"doi","pmid","openalex_id","label_included"' in data:
            result["confidence"] = 1.0

        if (
            "record_id,pubmedID,title,authors,abstract,year,label_included,label_abstract_screening"
            in data
        ):
            result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for systematic-review-datasets"""

        for record in records.values():
            if "pmid" in record:
                record["pubmedid"] = record["pmid"].replace(
                    "https://pubmed.ncbi.nlm.nih.gov/", ""
                )
                del record["pmid"]

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for systematic-review-datasets"""

        if "doi" in record.data:
            works = Works(etiquette=self.etiquette)
            crossref_query_return = works.doi(record.data["doi"])
            if crossref_query_return:
                retrieved_record_dict = connector_utils.json_to_record(
                    item=crossref_query_return
                )
                record.change_entrytype(
                    new_entrytype=retrieved_record_dict["ENTRYTYPE"]
                )
                for key in [
                    "journal",
                    "booktitle",
                    "volume",
                    "number",
                    "year",
                    "pages",
                    "author",
                    "title",
                ]:
                    if key in retrieved_record_dict:
                        record.data[key] = retrieved_record_dict[key]

        return record


if __name__ == "__main__":
    pass
