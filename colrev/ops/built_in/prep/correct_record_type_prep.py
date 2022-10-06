#! /usr/bin/env python
"""Correction of record ENTRYTYPE as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep
    import colrev.env.local_index

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class CorrectRecordTypePrep(JsonSchemaMixin):
    """Prepares records by correcting the record type (ENTRYTYPE)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by heuristically correcting erroneous ENTRYTYPEs"""

        if (
            not record.has_inconsistent_fields()
            or record.masterdata_is_curated()
            or prep_operation.retrieval_similarity > 0.9
        ):
            return record

        if (
            "dissertation" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.data.update(ENTRYTYPE="phdthesis")
            prep_operation.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(prep_operation.pad, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("dissertation" in fulltext link)'
            )

        if (
            "thesis" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.data.update(ENTRYTYPE="phdthesis")
            prep_operation.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(prep_operation.pad, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "This thesis" in record.data.get("abstract", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.data.update(ENTRYTYPE="phdthesis")
            prep_operation.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(prep_operation.pad, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

        # Journal articles should not have booktitles/series set.
        if "article" == record.data["ENTRYTYPE"]:
            if "booktitle" in record.data:
                if "journal" not in record.data:
                    record.data.update(journal=record.data["booktitle"])
                    record.remove_field(key="booktitle")
            if "series" in record.data:
                if "journal" not in record.data:
                    record.data.update(journal=record.data["series"])
                    record.remove_field(key="series")

        if "article" == record.data["ENTRYTYPE"]:
            if "journal" not in record.data:
                if "series" in record.data:
                    journal_string = record.data["series"]
                    record.data.update(journal=journal_string)
                    record.remove_field(key="series")
        return record


if __name__ == "__main__":
    pass
