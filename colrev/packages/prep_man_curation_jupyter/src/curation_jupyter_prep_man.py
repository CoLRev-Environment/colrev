#! /usr/bin/env python
"""Jupyter notebook for prep-man operation"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

from pydantic import Field

import colrev.env.utils
import colrev.package_manager.package_base_classes as base_classes
import colrev.package_manager.package_settings
import colrev.record.record

# pylint: disable=too-few-public-methods


class CurationJupyterNotebookManPrep(base_classes.PrepManPackageBaseClass):
    """Manual preparation based on a Jupyter Notebook"""

    settings_class = colrev.package_manager.package_settings.DefaultSettings
    ci_supported: bool = Field(default=False)

    def __init__(
        self,
        *,
        prep_man_operation: colrev.ops.prep_man.PrepMan,
        settings: dict,
        logger: typing.Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.settings = self.settings_class(**settings)

        Path("prep_man").mkdir(exist_ok=True)
        if not Path("prep_man/prep_man_curation.ipynb").is_file():
            self.logger.info(
                f"Activated jupyter notebook to"
                f"{Path('prep_man/prep_man_curation.ipynb')}"
            )
            colrev.env.utils.retrieve_package_file(
                template_file=Path("packages/prep_man/curation_jupyter_prep_man.ipynb"),
                target=Path("prep_man/prep_man_curation.ipynb"),
            )

    def prepare_manual(self, records: dict) -> dict:
        """Prepare records manually based on  a Jupyter notebeook"""

        input(
            "Navigate to the jupyter notebook available at\n"
            "prep_man/prep_man_curation.ipynb\n"
            "Press Enter to continue."
        )
        return records
