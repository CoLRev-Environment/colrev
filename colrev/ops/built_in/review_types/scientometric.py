#! /usr/bin/env python
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.ReviewTypePackageInterface)
class ScientometricReview:

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(self, *, operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def initialize(
        self, settings: colrev.settings.Configuration
    ) -> colrev.settings.Configuration:

        settings.data.scripts = [
            {
                "endpoint": "manuscript",
                "version": "1.0",
                "word_template": "APA-7.docx",
                "csl_style": "apa.csl",
            }
        ]
        settings.pdf_get.pdf_required_for_screen_and_synthesis = False
        return settings


if __name__ == "__main__":
    pass
