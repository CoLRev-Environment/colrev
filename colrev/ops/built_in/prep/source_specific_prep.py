#! /usr/bin/env python
"""Source-specific preparation as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
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
class SourceSpecificPrep(JsonSchemaMixin):
    """Prepares records based on the prepare scripts specified by the SearchSource"""

    source_correction_hint = "check with the developer"
    ci_supported: bool = True

    always_apply_changes = True
    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        self.search_sources = colrev.ops.search_sources.SearchSources(
            review_manager=prep_operation.review_manager
        )

    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        """Prepare the record by applying source-specific fixes"""

        # Note : we take the first origin (ie., the source-specific prep should
        # be one of the first in the prep-list)
        origin_source = record.data["colrev_origin"][0].split("/")[0]

        sources = [
            s
            for s in prep_operation.review_manager.settings.sources
            if s.filename.with_suffix(".bib")
            == Path("data/search") / Path(origin_source)
        ]

        for source in sources:
            if source.endpoint not in self.search_sources.packages:
                continue
            endpoint = self.search_sources.packages[source.endpoint]

            if callable(endpoint.prepare):
                record = endpoint.prepare(record, source)
            else:
                print(f"error: {source.endpoint}")

        if "howpublished" in record.data and "url" not in record.data:
            if "url" in record.data["howpublished"]:
                record.rename_field(key="howpublished", new_key="url")
                record.update_field(
                    key="url",
                    value=record.data["url"].replace("\\url{", "").rstrip("}"),
                    source="source_specific_prep",
                )

        if "webpage" == record.data["ENTRYTYPE"].lower() or (
            "misc" == record.data["ENTRYTYPE"].lower() and "url" in record.data
        ):
            record.update_field(
                key="ENTRYTYPE", value="online", source="source_specific_prep"
            )

        return record


if __name__ == "__main__":
    pass
