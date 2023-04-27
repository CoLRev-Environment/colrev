#! /usr/bin/env python
"""Conslidation of metadata based on LocalIndex as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.search_sources.local_index as local_index_connector
import colrev.ops.search_sources
import colrev.record


# pylint: disable=duplicate-code

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class LocalIndexPrep(JsonSchemaMixin):
    """Prepares records based on LocalIndex metadata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = (
        "correct the metadata in the source "
        + "repository (as linked in the provenance field)"
    )
    always_apply_changes = True

    def __init__(self, *, prep_operation: colrev.ops.prep.Prep, settings: dict) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.local_index_source = local_index_connector.LocalIndexSearchSource(
            source_operation=prep_operation
        )

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record metadata based on local-index"""

        # don't move to  jour_iss_number_year prep
        # because toc-retrieval relies on adequate toc items!
        if "volume" in record.data and "number" in record.data:
            # Note : cannot use local_index as an attribute of PrepProcess
            # because it creates problems with multiprocessing
            fields_to_remove = self.local_index_source.local_index.get_fields_to_remove(
                record_dict=record.get_data()
            )
            for field_to_remove in fields_to_remove:
                if field_to_remove in record.data:
                    record.remove_field(
                        key=field_to_remove,
                        not_missing_note=True,
                        source="local_index",
                    )

        self.local_index_source.get_masterdata(
            prep_operation=prep_operation, record=record
        )

        return record


if __name__ == "__main__":
    pass
