#! /usr/bin/env python
"""Consolidation of metadata based on SemanticScholar API as a prep operation"""
from __future__ import annotations

import json
from dataclasses import dataclass

import requests
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
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
class SemanticScholarPrep(JsonSchemaMixin):
    """Prepares records based on SemanticScholar metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = (
        "fill out the online form: "
        + "https://www.semanticscholar.org/faq#correct-error"
    )
    always_apply_changes = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        _, email = prep_operation.review_manager.get_committer()
        self.headers = {"user-agent": f"{__name__} (mailto:{email})"}
        self.session = prep_operation.review_manager.get_cached_session()

    def __get_record_from_item(
        self, *, item: dict, record_in: colrev.record.PrepRecord
    ) -> colrev.record.PrepRecord:
        # pylint: disable=too-many-branches
        retrieved_record: dict = {}
        if "authors" in item:
            authors_string = " and ".join(
                [author["name"] for author in item["authors"] if "name" in author]
            )
            authors_string = colrev.record.PrepRecord.format_author_field(
                input_string=authors_string
            )
            retrieved_record.update(author=authors_string)
        if "abstract" in item:
            retrieved_record.update(abstract=item["abstract"])
        if "doi" in item:
            if str(item["doi"]).lower() != "none":
                retrieved_record.update(doi=str(item["doi"]).upper())
        if "title" in item:
            retrieved_record.update(title=item["title"])
        if "year" in item:
            retrieved_record.update(year=item["year"])
        # Note: semantic scholar does not provide data on the type of venue.
        # we therefore use the original ENTRYTYPE
        if "venue" in item:
            if "journal" in record_in.data:
                retrieved_record.update(journal=item["venue"])
            if "booktitle" in record_in.data:
                retrieved_record.update(booktitle=item["venue"])
        if "url" in item:
            retrieved_record.update(sem_scholar_id=item["url"])

        keys_to_drop = []
        for key, value in retrieved_record.items():
            retrieved_record[key] = str(value).replace("\n", " ").lstrip().rstrip()
            if value in ["", "None"] or value is None:
                keys_to_drop.append(key)
        for key in keys_to_drop:
            record_in.remove_field(key=key)

        record = colrev.record.PrepRecord(data=retrieved_record)
        return record

    def retrieve_record_from_semantic_scholar(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        url: str,
        record_in: colrev.record.PrepRecord,
    ) -> colrev.record.PrepRecord:
        """Prepare the record metadata based on SemanticScholar"""

        # prep_operation.review_manager.logger.debug(url)
        ret = self.session.request(
            "GET", url, headers=self.headers, timeout=prep_operation.timeout
        )
        ret.raise_for_status()

        data = json.loads(ret.text)
        items = data["data"]
        if len(items) == 0:
            return record_in
        if "paperId" not in items[0]:
            return record_in

        paper_id = items[0]["paperId"]
        record_retrieval_url = "https://api.semanticscholar.org/v1/paper/" + paper_id
        # prep_operation.review_manager.logger.debug(record_retrieval_url)
        ret_ent = self.session.request(
            "GET",
            record_retrieval_url,
            headers=self.headers,
            timeout=prep_operation.timeout,
        )
        ret_ent.raise_for_status()
        item = json.loads(ret_ent.text)

        record = self.__get_record_from_item(item=item, record_in=record_in)
        record.add_provenance_all(source=record_retrieval_url)

        return record

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare a record based on metadata from SemanticScholar"""

        same_record_type_required = (
            prep_operation.review_manager.settings.is_curated_masterdata_repo()
        )
        try:
            search_api_url = (
                "https://api.semanticscholar.org/graph/v1/paper/search?query="
            )
            url = search_api_url + record.data.get("title", "").replace(" ", "+")

            retrieved_record = self.retrieve_record_from_semantic_scholar(
                prep_operation=prep_operation, url=url, record_in=record
            )
            if "sem_scholar_id" not in retrieved_record.data:
                return record

            # Remove fields that are not/rarely available before
            # calculating similarity metrics
            orig_record = record.copy_prep_rec()
            for key in ["volume", "number", "number", "pages"]:
                if key in orig_record.data:
                    record.remove_field(key=key)

            similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                record_original=orig_record,
                retrieved_record_original=retrieved_record,
                same_record_type_required=same_record_type_required,
            )
            if similarity > prep_operation.retrieval_similarity:
                # prep_operation.review_manager.logger.debug("Found matching record")
                # prep_operation.review_manager.logger.debug(
                #     f"scholar similarity: {similarity} "
                #     f"(>{prep_operation.retrieval_similarity})"
                # )

                record.merge(
                    merging_record=retrieved_record,
                    default_source=retrieved_record.data["sem_scholar_id"],
                )

            else:
                # prep_operation.review_manager.logger.debug(
                #     f"scholar similarity: {similarity} "
                #     f"(<{prep_operation.retrieval_similarity})"
                # )
                pass

        except (
            requests.exceptions.RequestException,
            colrev_exceptions.InvalidMerge,
        ):
            pass
        return record


if __name__ == "__main__":
    pass
