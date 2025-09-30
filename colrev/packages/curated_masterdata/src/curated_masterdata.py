#! /usr/bin/env python
"""Curated metadata project"""
import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.env.utils
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
from colrev.constants import Fields
from colrev.constants import SearchType

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class CuratedMasterdata(base_classes.ReviewTypePackageBaseClass):
    """Curated masterdata"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=True)

    def __init__(
        self,
        *,
        operation: colrev.process.operation.Operation,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)
        self.review_manager = operation.review_manager

    def __str__(self) -> str:
        return "curated masterdata repository"

    def initialize(
        self, settings: colrev.settings.Settings
    ) -> colrev.settings.Settings:
        """Initialize a curated masterdata repository"""

        self.logger.info("Initializing curated masterdata repository")

        # replace readme
        colrev.env.utils.retrieve_package_file(
            template_file=Path(
                "packages/curated_masterdata/curated_masterdata/README.md"
            ),
            target=Path("readme.md"),
        )
        colrev.env.utils.retrieve_package_file(
            template_file=Path(
                "packages/curated_masterdata/curated_masterdata/curations_github_colrev_update.yml"
            ),
            target=Path(".github/workflows/colrev_update.yml"),
        )

        issn = input("Provide ISSN for crossref (or leave blank to skip:)")

        crossref_search_history = colrev.search_file.ExtendedSearchFile(
            platform="colrev.crossref",
            search_results_path=Path("data/search/CROSSREF.bib"),
            search_type=SearchType.TOC,
            search_string=f"https://api.crossref.org/journals/{issn}/works",
            comment="",
            version="0.1.0",
        )
        pdf_search_history = colrev.search_file.ExtendedSearchFile(
            platform="colrev.files_dir",
            search_results_path=Path("data/search/pdfs.bib"),
            search_string="",
            search_parameters={
                "scope": {
                    # "subdir_pattern": "volume_number|year",
                    "type": "TODO",
                    # "conference": "TODO",
                    # "journal": "TODO",
                    # "year": "TODO",
                    "path": "data/pdfs",
                }
            },
            search_type=SearchType.FILES,
            version="0.1.0",
        )

        settings.sources = [crossref_search_history, pdf_search_history]

        settings.search.retrieve_forthcoming = False

        settings.prep.prep_rounds[0].prep_package_endpoints = [
            {"endpoint": "colrev.source_specific_prep"},
            {"endpoint": "colrev.exclude_complementary_materials"},
            {"endpoint": "colrev.remove_urls_with_500_errors"},
            {"endpoint": "colrev.remove_broken_ids"},
            {"endpoint": "colrev.get_doi_from_urls"},
            {"endpoint": "colrev.get_year_from_vol_iss_jour"},
        ]

        settings.prep.prep_man_package_endpoints = [
            {"endpoint": "colrev.prep_man_curation_jupyter"},
            {"endpoint": "colrev.export_man_prep"},
        ]
        settings.prescreen.explanation = (
            "All records are automatically prescreen included."
        )

        settings.screen.explanation = (
            "All records are automatically included in the screen."
        )

        settings.prescreen.prescreen_package_endpoints = [
            {
                "endpoint": "colrev.scope_prescreen",
                "ExcludeComplementaryMaterials": True,
            },
            {"endpoint": "colrev.conditional_prescreen"},
        ]
        settings.screen.screen_package_endpoints = []
        settings.pdf_get.pdf_get_package_endpoints = []

        settings.dedupe.dedupe_package_endpoints = [
            {
                "endpoint": "colrev.curation_full_outlet_dedupe",
                "selected_source": "data/search/CROSSREF.bib",
            },
            {
                "endpoint": "colrev.curation_full_outlet_dedupe",
                "selected_source": "data/search/pdfs.bib",
            },
            {"endpoint": "colrev.curation_missing_dedupe"},
        ]

        curation_url = input(
            "Enter the curation URL (or <leave blank to skip>): "
        ).strip()

        settings.data.data_package_endpoints = [
            {
                "endpoint": "colrev.colrev_curation",
                "version": "0.1",
                "curation_url": curation_url,
                "curated_masterdata": True,
                "masterdata_restrictions": {
                    # "1900": {
                    #     Fields.ENTRYTYPE: "article",
                    #     Fields.VOLUME: True,
                    #     Fields.NUMBER: True,
                    #     Fields.JOURNAL: "Journal Name",
                    # }
                },
                "curated_fields": [Fields.DOI, Fields.URL],
            }
        ]

        if settings.data.data_package_endpoints[0].get("curation_url"):
            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{url}}",
                new_string=settings.data.data_package_endpoints[0].get("curation_url"),
            )

        # curated repo: automatically prescreen/screen-include papers
        # (no data endpoint -> automatically rev_synthesized)

        return settings
