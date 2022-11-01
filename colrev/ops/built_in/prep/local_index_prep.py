#! /usr/bin/env python
"""Conslidation of metadata based on LocalIndex as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from opensearchpy import NotFoundError
from opensearchpy.exceptions import TransportError

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class LocalIndexPrep(JsonSchemaMixin):
    """Prepares records based on LocalIndex metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = (
        "correct the metadata in the source "
        + "repository (as linked in the provenance field)"
    )
    always_apply_changes = True

    def __init__(self, *, prep_operation: colrev.ops.prep.Prep, settings: dict) -> None:

        self.local_index = prep_operation.review_manager.get_local_index()

        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record metadtaa based on local-index"""

        # TBD: maybe extract the following three lines as a separate script...
        if not record.masterdata_is_curated():
            try:
                year = self.local_index.get_year_from_toc(record_dict=record.get_data())
                record.update_field(
                    key="year",
                    value=year,
                    source="LocalIndexPrep",
                    keep_source_if_equal=True,
                )
            except colrev_exceptions.TOCNotAvailableException:
                pass

        # Note : cannot use local_index as an attribute of PrepProcess
        # because it creates problems with multiprocessing
        retrieved = False
        try:
            retrieved_record_dict = self.local_index.retrieve(
                record_dict=record.get_data(), include_file=False
            )
            retrieved = True
        except (colrev_exceptions.RecordNotInIndexException, NotFoundError):
            try:
                # Note: Records can be CURATED without being indexed
                if not record.masterdata_is_curated():
                    retrieved_record_dict = self.local_index.retrieve_from_toc(
                        record_dict=record.data,
                        similarity_threshold=prep_operation.retrieval_similarity,
                        include_file=False,
                    )
                    retrieved = True
            except (
                colrev_exceptions.RecordNotInIndexException,
                colrev_exceptions.NotTOCIdentifiableException,
                NotFoundError,
                TransportError,
            ):
                pass

        if retrieved:
            retrieved_record = colrev.record.PrepRecord(data=retrieved_record_dict)

            default_source = "LOCAL_INDEX"
            if "colrev_masterdata_provenance" in retrieved_record.data:
                if "CURATED" in retrieved_record.data["colrev_masterdata_provenance"]:
                    default_source = retrieved_record.data[
                        "colrev_masterdata_provenance"
                    ]["CURATED"]["source"]
            record.merge(
                merging_record=retrieved_record,
                default_source=default_source,
            )

            git_repo = prep_operation.review_manager.dataset.get_repo()
            cur_project_source_paths = [str(prep_operation.review_manager.path)]
            for remote in git_repo.remotes:
                if remote.url:
                    shared_url = remote.url
                    shared_url = shared_url.rstrip(".git")
                    cur_project_source_paths.append(shared_url)
                    break

            # extend fields_to_keep (to retrieve all fields from the index)
            for key in retrieved_record.data.keys():
                if key not in prep_operation.fields_to_keep:
                    prep_operation.fields_to_keep.append(key)

        return record


if __name__ == "__main__":
    pass
