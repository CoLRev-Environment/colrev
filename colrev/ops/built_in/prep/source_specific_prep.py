#! /usr/bin/env python
"""Source-specific preparation as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

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


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class SourceSpecificPrep(JsonSchemaMixin):
    """Prepares records based on the prepare scripts specified by the SearchSource"""

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

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:
        # TODO : may need to rerun import_provenance

        search_sources = colrev.ops.search_sources.SearchSources(
            review_manager=prep_operation.review_manager
        )

        origin_source = record.data["colrev_origin"][0].split("/")[0]

        sources = [
            s.endpoint
            for s in prep_operation.review_manager.settings.sources
            if s.filename.with_suffix(".bib") == Path("search") / Path(origin_source)
        ]

        for source in sources:
            if source not in search_sources.packages:
                continue
            endpoint = search_sources.packages[source]

            if callable(endpoint.prepare):
                record = endpoint.prepare(record)
            else:
                print(f"error: {source}")

        if "howpublished" in record.data and "url" not in record.data:
            if "url" in record.data["howpublished"]:
                record.rename_field(key="howpublished", new_key="url")
                record.data["url"] = (
                    record.data["url"].replace("\\url{", "").rstrip("}")
                )

        if "webpage" == record.data["ENTRYTYPE"].lower() or (
            "misc" == record.data["ENTRYTYPE"].lower() and "url" in record.data
        ):
            record.data["ENTRYTYPE"] = "online"

        return record


if __name__ == "__main__":
    pass
