#! /usr/bin/env python
"""Retrieving DOIs from a papers website/url as a prep operation"""
from __future__ import annotations

import collections
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import requests
import timeout_decorator
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class DOIFromURLsPrep(JsonSchemaMixin):
    """Prepares records by retrieving its DOI from the website (URL)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    # https://www.crossref.org/blog/dois-and-matching-regular-expressions/
    doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:

        same_record_type_required = (
            prep_operation.review_manager.settings.project.curated_masterdata
        )

        session = prep_operation.review_manager.get_cached_session()

        url = record.data.get("url", record.data.get("fulltext", "NA"))
        if "NA" != url:
            try:
                prep_operation.review_manager.logger.debug(
                    f"Retrieve doi-md from {url}"
                )
                headers = {
                    "user-agent": f"{__name__}  "
                    f"(mailto:{prep_operation.review_manager.email})"
                }
                ret = session.request(
                    "GET", url, headers=headers, timeout=prep_operation.timeout
                )
                ret.raise_for_status()
                res = re.findall(self.doi_regex, ret.text)
                if res:
                    if len(res) == 1:
                        ret_dois = [(res[0], 1)]
                    else:
                        counter = collections.Counter(res)
                        ret_dois = counter.most_common()

                    if not ret_dois:
                        return record
                    for doi, _ in ret_dois:
                        retrieved_record_dict = {
                            "doi": doi.upper(),
                            "ID": record.data["ID"],
                        }
                        retrieved_record = colrev.record.PrepRecord(
                            data=retrieved_record_dict
                        )
                        colrev.ops.built_in.database_connectors.DOIConnector.retrieve_doi_metadata(
                            review_manager=prep_operation.review_manager,
                            record=retrieved_record,
                            timeout=prep_operation.timeout,
                        )

                        similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                            record_original=record,
                            retrieved_record_original=retrieved_record,
                            same_record_type_required=same_record_type_required,
                        )
                        if similarity > prep_operation.retrieval_similarity:
                            record.merge(
                                merging_record=retrieved_record, default_source=url
                            )

                            prep_operation.review_manager.report_logger.debug(
                                "Retrieved metadata based on doi from"
                                f' website: {record.data["doi"]}'
                            )

            except requests.exceptions.RequestException:
                pass
        return record


if __name__ == "__main__":
    pass
