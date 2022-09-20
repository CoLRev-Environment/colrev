#! /usr/bin/env python
"""Resolution of BibTeX crossref fields as a prep operation"""
from __future__ import annotations

from typing import TYPE_CHECKING

import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep
    import colrev.env.local_index

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageInterface)
class BibTexCrossrefResolutionPrep:
    """Prepares records by resolving BibTex crossref links (e.g., to proceedings)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False

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
        if "crossref" in record.data:
            crossref_record = prep_operation.review_manager.dataset.get_crossref_record(
                record_dict=record.data
            )
            if 0 != len(crossref_record):
                for key, value in crossref_record.items():
                    if key not in record.data:
                        record.data[key] = value

        return record


if __name__ == "__main__":
    pass
