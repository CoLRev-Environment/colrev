#! /usr/bin/env python
"""Adding of journal rankings to metadata"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.local_index
import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class AddJournalRanking(JsonSchemaMixin):
    """Class for add _journal_ranking"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = False
    ci_supported: bool = False

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.local_index = colrev.env.local_index.LocalIndex()

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Add Journalranking to Metadata"""

        if record.data.get("journal", "") == "":
            return record

        rankings = self.local_index.search_in_database(record.data["journal"])
        # extend: include journal-impact factor or ranking category
        if rankings:
            rankings_str = ",".join(r["ranking"] for r in rankings)
        else:
            rankings_str = "not included in a ranking"

        record.update_field(
            key="journal_ranking",
            value=rankings_str,
            source="add_journal_ranking",
            note="",
        )

        return record


if __name__ == "__main__":
    pass
