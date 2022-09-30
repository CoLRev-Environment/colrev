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


@zope.interface.implementer(
    colrev.env.package_manager.ReviewTypePackageEndpointInterface
)
@dataclass
class RealTimeReview(JsonSchemaMixin):
    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self, *, operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __str__(self) -> str:
        return "realtime review"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev_built_in.manuscript",
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
                prep_package_endpoints=[
                    {"endpoint": "colrev_built_in.load_fixes"},
                    {"endpoint": "colrev_built_in.remove_urls_with_500_errors"},
                    {"endpoint": "colrev_built_in.remove_broken_IDs"},
                    {"endpoint": "colrev_built_in.global_ids_consistency_check"},
                    {"endpoint": "colrev_built_in.prep_curated"},
                    {"endpoint": "colrev_built_in.format"},
                    {"endpoint": "colrev_built_in.resolve_crossrefs"},
                    {"endpoint": "colrev_built_in.get_doi_from_urls"},
                    {"endpoint": "colrev_built_in.get_masterdata_from_doi"},
                    {"endpoint": "colrev_built_in.get_masterdata_from_crossref"},
                    {"endpoint": "colrev_built_in.get_masterdata_from_dblp"},
                    {"endpoint": "colrev_built_in.get_masterdata_from_open_library"},
                    {"endpoint": "colrev_built_in.get_year_from_vol_iss_jour_crossref"},
                    {"endpoint": "colrev_built_in.get_record_from_local_index"},
                    {"endpoint": "colrev_built_in.remove_nicknames"},
                    {"endpoint": "colrev_built_in.format_minor"},
                    {"endpoint": "colrev_built_in.drop_fields"},
                ],
            )
        ]

        return settings


if __name__ == "__main__":
    pass
