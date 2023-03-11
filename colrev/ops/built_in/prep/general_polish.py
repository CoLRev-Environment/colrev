#! /usr/bin/env python
"""Genral polishing rules"""
from __future__ import annotations

import re
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep
        import colrev.env.local_index

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class GeneralPolishPrep(JsonSchemaMixin):
    """Prepares records by applying polishing rules"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = False

    frequent_acronyms = [
        "MIS",
        "GSS",
        "DSS",
        "ICIS",
        "ECIS",
        "AMCIS",
        "PACIS",
        "BI",
        "CRM",
        "CIO",
        "CEO",
        "ERP",
        "ICT",
        "Twitter",
        "Facebook",
        "Wikipedia",
        "B2B",
        "C2C",
    ]

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the record by applying polishing rules"""

        if "title" in record.data:
            acronyms = [
                x
                for x in self.frequent_acronyms
                if x.lower() in record.data["title"].lower().split()
            ]
            for acronym in acronyms:
                record.data["title"] = re.sub(
                    acronym, acronym, record.data["title"], flags=re.I
                )

        return record


if __name__ == "__main__":
    pass
