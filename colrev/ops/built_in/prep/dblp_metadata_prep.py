#! /usr/bin/env python
"""Consolidation of metadata based on DBLP API as a prep operation"""
from __future__ import annotations

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
class DBLPMetadataPrep(JsonSchemaMixin):
    """Prepares records based on dblp.org metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = (
        "send and email to dblp@dagstuhl.de"
        + " (see https://dblp.org/faq/How+can+I+correct+errors+in+dblp.html)"
    )
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
        if "dblp_key" in record.data:
            return record

        same_record_type_required = (
            prep_operation.review_manager.settings.project.curated_masterdata
        )

        try:
            query = "" + record.data.get("title", "").replace("-", "_")
            # Note: queries combining title+author/journal do not seem to work any more
            # if "author" in record:
            #     query = query + "_" + record["author"].split(",")[0]
            # if "booktitle" in record:
            #     query = query + "_" + record["booktitle"]
            # if "journal" in record:
            #     query = query + "_" + record["journal"]
            # if "year" in record:
            #     query = query + "_" + record["year"]

            for (
                retrieved_record
            ) in colrev.ops.built_in.database_connectors.DBLPConnector.retrieve_dblp_records(
                review_manager=prep_operation.review_manager,
                query=query,
            ):
                similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                    record_original=record,
                    retrieved_record_original=retrieved_record,
                    same_record_type_required=same_record_type_required,
                )
                if similarity > prep_operation.retrieval_similarity:
                    prep_operation.review_manager.logger.debug("Found matching record")
                    prep_operation.review_manager.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(>{prep_operation.retrieval_similarity})"
                    )
                    source = retrieved_record.data["dblp_key"]
                    record.merge(
                        merging_record=retrieved_record,
                        default_source=source,
                    )
                    record.set_masterdata_complete(source_identifier=source)
                    record.set_status(
                        target_state=colrev.record.RecordState.md_prepared
                    )
                    if "Withdrawn (according to DBLP)" in record.data.get(
                        "warning", ""
                    ):
                        record.prescreen_exclude(reason="retracted")
                        record.remove_field(key="warning")

                else:
                    prep_operation.review_manager.logger.debug(
                        f"dblp similarity: {similarity} "
                        f"(<{prep_operation.retrieval_similarity})"
                    )
        except (requests.exceptions.RequestException, UnicodeEncodeError):
            pass
        return record


if __name__ == "__main__":
    pass
