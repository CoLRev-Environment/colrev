#! /usr/bin/env python
"""Consolidation of metadata based on CiteAs API as a prep operation"""
from __future__ import annotations

import json
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


@zope.interface.implementer(colrev.env.package_manager.PrepPackageInterface)
@dataclass
class CiteAsPrep(JsonSchemaMixin):
    """Prepares records based on citeas.org metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "Search on https://citeas.org/ and click 'modify'"
    always_apply_changes = False

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
        def cite_as_json_to_record(*, data: dict, url=str) -> colrev.record.PrepRecord:
            retrieved_record: dict = {}

            if "author" in data["metadata"]:
                authors = data["metadata"]["author"]
                authors_string = ""
                for author in authors:
                    authors_string += author.get("family", "") + ", "
                    authors_string += author.get("given", "") + " "
                authors_string = authors_string.lstrip().rstrip().replace("  ", " ")
                retrieved_record.update(author=authors_string)
            if "container-title" in data["metadata"]:
                retrieved_record.update(title=data["metadata"]["container-title"])
            if "URL" in data["metadata"]:
                retrieved_record.update(url=data["metadata"]["URL"])
            if "note" in data["metadata"]:
                retrieved_record.update(note=data["metadata"]["note"])
            if "type" in data["metadata"]:
                retrieved_record.update(ENTRYTYPE=data["metadata"]["type"])
            if "year" in data["metadata"]:
                retrieved_record.update(year=data["metadata"]["year"])
            if "DOI" in data["metadata"]:
                retrieved_record.update(doi=data["metadata"]["DOI"])

            record = colrev.record.PrepRecord(data=retrieved_record)
            record.add_provenance_all(source=url)
            return record

        if record.data.get("ENTRYTYPE", "NA") not in ["misc", "software"]:
            return record
        if "title" not in record.data:
            return record

        try:

            same_record_type_required = (
                prep_operation.review_manager.settings.project.curated_masterdata
            )

            session = prep_operation.review_manager.get_cached_session()
            url = (
                f"https://api.citeas.org/product/{record.data['title']}?"
                + f"email={prep_operation.review_manager.email}"
            )
            ret = session.request(
                "GET",
                url,
                headers=prep_operation.requests_headers,
                timeout=prep_operation.timeout,
            )
            ret.raise_for_status()
            prep_operation.review_manager.logger.debug(url)

            data = json.loads(ret.text)

            retrieved_record = cite_as_json_to_record(data=data, url=url)

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=retrieved_record,
                retrieved_record_original=retrieved_record,
                same_record_type_required=same_record_type_required,
            )
            if similarity > prep_operation.retrieval_similarity:
                record.merge(merging_record=retrieved_record, default_source=url)

        except requests.exceptions.RequestException:
            pass
        except UnicodeEncodeError:
            prep_operation.review_manager.logger.error(
                "UnicodeEncodeError - this needs to be fixed at some time"
            )

        return record


if __name__ == "__main__":
    pass
