#! /usr/bin/env python
"""Realtime review"""
from dataclasses import dataclass

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.ReviewTypePackageInterface)
@dataclass
class RealTimeReview(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(self, *, operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:

        settings.data.scripts = [
            {
                "endpoint": "manuscript",
                "version": "1.0",
                "word_template": "APA-7.docx",
                "csl_style": "apa.csl",
            }
        ]
        settings.project.delay_automated_processing = False
        settings.prep.prep_rounds = [
            colrev.settings.PrepRound(
                name="quick_prep",
                similarity=0.95,
                scripts=[
                    "load_fixes",
                    "remove_urls_with_500_errors",
                    "remove_broken_IDs",
                    "global_ids_consistency_check",
                    "prep_curated",
                    "format",
                    "resolve_crossrefs",
                    "get_doi_from_urls",
                    "get_masterdata_from_doi",
                    "get_masterdata_from_crossref",
                    "get_masterdata_from_dblp",
                    "get_masterdata_from_open_library",
                    "get_year_from_vol_iss_jour_crossref",
                    "get_record_from_local_index",
                    "remove_nicknames",
                    "format_minor",
                    "drop_fields",
                ],
            )
        ]

        return settings


if __name__ == "__main__":
    pass
