#! /usr/bin/env python
"""Jupyter notebook for prep-man operation"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep_man

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepManPackageEndpointInterface)
@dataclass
class CurationJupyterNotebookManPrep(JsonSchemaMixin):
    """Manual preparation based on a Jupyter Notebook"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    def __init__(
        self, *, prep_man_operation: colrev.ops.prep_man.PrepMan, settings: dict
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        Path("prep_man").mkdir(exist_ok=True)
        if not Path("prep_man/prep_man_curation.ipynb").is_file():
            prep_man_operation.review_manager.logger.info(
                f"Activated jupyter notebook to"
                f"{Path('prep_man/prep_man_curation.ipynb')}"
            )
            colrev.env.utils.retrieve_package_file(
                template_file=Path("template/ops/prep_man_curation.ipynb"),
                target=Path("prep_man/prep_man_curation.ipynb"),
            )

    def prepare_manual(
        self,
        prep_man_operation: colrev.ops.prep_man.PrepMan,  # pylint: disable=unused-argument
        records: dict,
    ) -> dict:
        """Prepare records manually based on  a Jupyter notebeook"""

        input(
            "Navigate to the jupyter notebook available at\n"
            "prep_man/prep_man_curation.ipynb\n"
            "Press Enter to continue."
        )
        return records


if __name__ == "__main__":
    pass
