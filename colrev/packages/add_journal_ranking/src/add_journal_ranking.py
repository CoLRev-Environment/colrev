#! /usr/bin/env python
"""Adding of journal rankings to metadata"""
from __future__ import annotations

import logging
import typing

from pydantic import Field

import colrev.env.local_index
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record
from colrev.constants import Fields

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument


class AddJournalRanking(base_classes.PrepPackageBaseClass):
    """Prepares records based on journal rankings"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    source_correction_hint = "check with the developer"
    always_apply_changes = False
    ci_supported: bool = Field(default=False)

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
        self.local_index = colrev.env.local_index.LocalIndex()

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        quality_model: typing.Optional[
            colrev.record.qm.quality_model.QualityModel
        ] = None,
    ) -> colrev.record.record.Record:
        """Add Journalranking to Metadata"""

        if record.data.get(Fields.JOURNAL, "") == "":
            return record

        rankings = self.local_index.get_journal_rankings(record.data[Fields.JOURNAL])
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
