#! /usr/bin/env python
"""Curated metadata project"""
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.ops.search
import colrev.record

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.ReviewTypePackageEndpointInterface
)
@dataclass
class CuratedMasterdata(JsonSchemaMixin):
    """Curated masterdata"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    def __init__(
        self, *, operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)
        self.review_manager = operation.review_manager

    def __str__(self) -> str:
        return "curated masterdata repository"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a curated masterdata repository"""

        # replace readme
        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/review_type/curated_masterdata/readme.md"),
            target=Path("readme.md"),
        )
        colrev.env.utils.retrieve_package_file(
            template_file=Path(
                "template/review_type/curated_masterdata/curations_github_colrev_update.yml"
            ),
            target=Path(".github/workflows/colrev_update.yml"),
        )

        if hasattr(self.review_manager.settings.project, "curation_url"):
            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{url}}",
                new_string=self.review_manager.settings.project.curation_url,
            )

        settings.search.retrieve_forthcoming = False

        settings.prep.prep_rounds[0].prep_package_endpoints = [
            {"endpoint": "colrev_built_in.resolve_crossrefs"},
            {"endpoint": "colrev_built_in.source_specific_prep"},
            {"endpoint": "colrev_built_in.exclude_non_latin_alphabets"},
            {"endpoint": "colrev_built_in.exclude_collections"},
            {"endpoint": "colrev_built_in.exclude_complementary_materials"},
            {"endpoint": "colrev_built_in.exclude_languages"},
            {"endpoint": "colrev_built_in.remove_urls_with_500_errors"},
            {"endpoint": "colrev_built_in.remove_broken_ids"},
            {"endpoint": "colrev_built_in.global_ids_consistency_check"},
            {"endpoint": "colrev_built_in.get_doi_from_urls"},
            {"endpoint": "colrev_built_in.get_year_from_vol_iss_jour"},
        ]

        settings.prep.prep_man_package_endpoints = [
            {"endpoint": "colrev_built_in.prep_man_curation_jupyter"},
            {"endpoint": "colrev_built_in.export_man_prep"},
        ]
        settings.prescreen.explanation = (
            "All records are automatically prescreen included."
        )

        settings.screen.explanation = (
            "All records are automatically included in the screen."
        )

        settings.prescreen.prescreen_package_endpoints = [
            {
                "endpoint": "colrev_built_in.scope_prescreen",
                "ExcludeComplementaryMaterials": True,
            },
            {"endpoint": "colrev_built_in.conditional_prescreen"},
        ]
        settings.screen.screen_package_endpoints = []
        settings.pdf_get.pdf_get_package_endpoints = []

        settings.dedupe.dedupe_package_endpoints = [
            {
                "endpoint": "colrev_built_in.curation_full_outlet_dedupe",
                "selected_source": "data/search/CROSSREF.bib",
            },
            {
                "endpoint": "colrev_built_in.curation_full_outlet_dedupe",
                "selected_source": "data/search/pdfs.bib",
            },
            {"endpoint": "colrev_built_in.curation_missing_dedupe"},
        ]

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev_built_in.colrev_curation",
                "version": "0.1",
                "curation_url": "TODO",
                "curated_masterdata": True,
                "masterdata_restrictions": {
                    # "1900": {
                    #     "ENTRYTYPE": "article",
                    #     "volume": True,
                    #     "number": True,
                    #     "journal": "Journal Name",
                    # }
                },
                "curated_fields": ["doi", "url"],
            }
        ]

        # curated repo: automatically prescreen/screen-include papers
        # (no data endpoint -> automatically rev_synthesized)

        return settings


if __name__ == "__main__":
    pass
