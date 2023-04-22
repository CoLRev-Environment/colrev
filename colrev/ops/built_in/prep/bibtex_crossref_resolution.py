#! /usr/bin/env python
"""Resolution of BibTeX crossref fields as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep
        import colrev.env.local_index


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class BibTexCrossrefResolutionPrep(JsonSchemaMixin):
    """Prepares records by resolving BibTex crossref links (e.g., to proceedings)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    ci_supported: bool = True

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def __get_crossref_record(
        self, *, prep_operation: colrev.ops.prep.Prep, record_dict: dict
    ) -> dict:
        """Get the record linked through the BiBTex crossref field"""

        # Note : the ID of the crossrefed record_dict may have changed.
        # we need to trace based on the colrev_origin
        crossref_origin = record_dict["colrev_origin"]
        crossref_origin = crossref_origin[: crossref_origin.rfind("/")]
        crossref_origin = crossref_origin + "/" + record_dict["crossref"]
        for (
            candidate_record_dict
        ) in prep_operation.review_manager.dataset.read_next_record():
            if crossref_origin in candidate_record_dict["colrev_origin"]:
                return candidate_record_dict
        return {}

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by resolving BiBTex crossref links (proceedings)"""

        if "crossref" not in record.data:
            return record

        crossref_record = self.__get_crossref_record(
            prep_operation=prep_operation, record_dict=record.data
        )
        if not crossref_record:
            return record

        for key, value in crossref_record.items():
            if key not in record.data:
                record.update_field(
                    key=key,
                    value=value,
                    source="crossref_resolution",
                    append_edit=False,
                )

        return record


if __name__ == "__main__":
    pass
