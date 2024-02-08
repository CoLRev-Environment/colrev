#! /usr/bin/env python
"""Default deduplication module for CoLRev"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import bib_dedupe.cluster
import pandas as pd
import zope.interface
from bib_dedupe.bib_dedupe import block
from bib_dedupe.bib_dedupe import export_maybe
from bib_dedupe.bib_dedupe import import_maybe
from bib_dedupe.bib_dedupe import match
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.dedupe

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.DedupePackageEndpointInterface)
@dataclass
class Dedupe(JsonSchemaMixin):
    """Default deduplication"""

    ci_supported: bool = True

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        dedupe_operation: colrev.ops.dedupe.Dedupe,
        settings: dict,
    ):
        self.settings = self.settings_class.load_settings(data=settings)
        self.dedupe_operation = dedupe_operation
        self.review_manager = dedupe_operation.review_manager

    def run_dedupe(self) -> None:
        """Run default dedupe"""

        records = self.review_manager.dataset.load_records_dict()

        records_df = pd.DataFrame.from_dict(records, orient="index")

        records_df = records_df[
            ~(
                records_df[Fields.STATUS].isin(
                    [
                        "md_imported",
                        "md_needs_manual_preparation",
                    ]
                )
            )
        ]

        records_df.loc[
            records_df[Fields.STATUS].isin(
                colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.md_processed
                )
            ),
            "search_set",
        ] = "old_search"

        records_df = self.dedupe_operation.get_records_for_dedupe(records_df=records_df)

        if 0 == records_df.shape[0]:
            return

        deduplication_pairs = block(records_df)
        matched_df = match(deduplication_pairs)
        matched_df = import_maybe(matched_df)

        if self.dedupe_operation.debug:
            return

        duplicate_id_sets = bib_dedupe.cluster.get_connected_components(matched_df)

        self.dedupe_operation.apply_merges(
            id_sets=duplicate_id_sets, complete_dedupe=True
        )

        self.review_manager.create_commit(
            msg="Merge duplicate records",
        )
        # TODO : export to custom path
        export_maybe(matched_df, records_df)
