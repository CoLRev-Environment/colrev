#! /usr/bin/env python
"""Default deduplication module for CoLRev"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from bib_dedupe.bib_dedupe import BibDeduper
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.dedupe.utils
import colrev.record

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
        self.bib_deduper = BibDeduper()

    def run_dedupe(self) -> None:
        """Run default dedupe"""

        records = self.review_manager.dataset.load_records_dict()
        records_df = pd.DataFrame.from_dict(records, orient="index")

        records_df = self.dedupe_operation.get_records_for_dedupe(records_df=records_df)

        if 0 == records_df.shape[0]:
            return

        deduplication_pairs = self.bib_deduper.block_pairs_for_deduplication(records_df)
        result = self.bib_deduper.identify_true_matches(deduplication_pairs)

        if self.dedupe_operation.debug:
            return

        self.dedupe_operation.apply_merges(
            origin_sets=result["duplicate_origin_sets"], complete_dedupe=True
        )

        self.review_manager.create_commit(
            msg="Merge duplicate records",
        )

        # TODO : maybes
