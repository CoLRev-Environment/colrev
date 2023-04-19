#! /usr/bin/env python
"""Retrieving DOIs from a papers website/url as a prep operation"""
from __future__ import annotations

import collections
import re
from dataclasses import dataclass
from sqlite3 import OperationalError

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.doi_org as doi_connector
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class DOIFromURLsPrep(JsonSchemaMixin):
    """Prepares records by retrieving its DOI from the website (URL)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

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
        self.settings = self.settings_class.load_settings(data=settings)
        self.same_record_type_required = (
            prep_operation.review_manager.settings.is_curated_masterdata_repo()
        )
        try:
            self.session = prep_operation.review_manager.get_cached_session()
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="sqlite-requests-cache"
            ) from exc
        _, self.email = prep_operation.review_manager.get_committer()

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by retrieving its DOI from the website (url) if available"""

        if ("url" not in record.data and "fulltext" not in record.data) or (
            "doi" in record.data
        ):
            return record

        try:
            url = record.data.get("url", record.data.get("fulltext", "NA"))
            headers = {"user-agent": f"{__name__}  " f"(mailto:{self.email})"}
            ret = self.session.request(
                "GET", url, headers=headers, timeout=prep_operation.timeout
            )
            ret.raise_for_status()
            res = re.findall(self.doi_regex, ret.text)
            if not res:
                return record

            if len(res) == 1:
                ret_dois = [(res[0], 1)]
            else:
                counter = collections.Counter(res)
                ret_dois = counter.most_common()

            if not ret_dois:
                return record

            doi, _ = ret_dois[0]

            retrieved_record_dict = {
                "doi": doi.upper(),
                "ID": record.data["ID"],
            }
            retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)
            doi_connector.DOIConnector.retrieve_doi_metadata(
                review_manager=prep_operation.review_manager,
                record=retrieved_record,
                timeout=prep_operation.timeout,
            )

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=record,
                retrieved_record_original=retrieved_record,
                same_record_type_required=self.same_record_type_required,
            )
            if similarity < prep_operation.retrieval_similarity:
                return record

            record.merge(merging_record=retrieved_record, default_source=url)

        except (requests.exceptions.RequestException, colrev_exceptions.InvalidMerge):
            pass
        return record


if __name__ == "__main__":
    pass
