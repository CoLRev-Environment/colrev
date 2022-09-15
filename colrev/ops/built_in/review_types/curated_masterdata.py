#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.env.utils
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.ReviewTypePackageInterface)
class CuratedMasterdata:

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(self, *, operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)
        self.review_manager = operation.review_manager

    def initialize(
        self, settings: colrev.settings.Configuration
    ) -> colrev.settings.Configuration:

        # replace readme
        colrev.env.utils.retrieve_package_file(
            template_file=Path("template/review_type/curated_masterdata/readme.md"),
            target=Path("readme.md"),
        )
        if self.review_manager.settings.project.curation_url:
            colrev.env.utils.inplace_change(
                filename=Path("readme.md"),
                old_string="{{url}}",
                new_string=self.review_manager.settings.project.curation_url,
            )
        crossref_source = colrev.settings.SearchSource(
            filename=Path("search/CROSSREF.bib"),
            search_type=colrev.settings.SearchType["DB"],
            source_name="crossref",
            source_identifier="https://api.crossref.org/works/{{doi}}",
            search_parameters={},
            load_conversion_script={"endpoint": "bibtex"},
            comment="",
        )
        settings.sources.insert(0, crossref_source)
        settings.search.retrieve_forthcoming = False

        # TODO : exclude complementary materials in prep scripts
        # TODO : exclude get_masterdata_from_citeas etc. from prep
        settings.prep.man_prep_scripts = [
            {"endpoint": "prep_man_curation_jupyter"},
            {"endpoint": "export_man_prep"},
        ]
        settings.prescreen.explanation = (
            "All records are automatically prescreen included."
        )

        settings.screen.explanation = (
            "All records are automatically included in the screen."
        )

        settings.project.curated_masterdata = True
        settings.prescreen.scripts = [
            {"endpoint": "scope_prescreen", "ExcludeComplementaryMaterials": True},
            {"endpoint": "conditional_prescreen"},
        ]
        settings.screen.scripts = [{"endpoint": "conditional_screen"}]
        settings.pdf_get.scripts = []
        # TODO : Deactivate languages, ...
        #  exclusion and add a complementary exclusion built-in script

        settings.dedupe.scripts = [
            {
                "endpoint": "curation_full_outlet_dedupe",
                "selected_source": "search/CROSSREF.bib",
            },
            {
                "endpoint": "curation_full_outlet_dedupe",
                "selected_source": "search/pdfs.bib",
            },
            {"endpoint": "curation_missing_dedupe"},
        ]

        # curated repo: automatically prescreen/screen-include papers
        # (no data endpoint -> automatically rev_synthesized)

        return settings


if __name__ == "__main__":
    pass
