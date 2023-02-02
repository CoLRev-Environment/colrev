#! /usr/bin/env python
"""CLI interface for prep-man operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.prep_man

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepManPackageEndpointInterface)
@dataclass
class CoLRevCLIManPrep(JsonSchemaMixin):
    """Manual preparation using the CLI (Not yet implemented)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        prep_man_operation: colrev.ops.prep_man.PrepMan,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def prepare_manual(
        self, prep_man_operation: colrev.ops.prep_man.PrepMan, records: dict
    ) -> dict:
        """Prepare records manually based on cli"""

        md_prep_man_data = prep_man_operation.get_data()
        stat_len = md_prep_man_data["nr_tasks"]

        if 0 == stat_len:
            prep_man_operation.review_manager.logger.info(
                "No records to prepare manually"
            )

        print("Man-prep is not fully implemented (yet).\n")
        print(
            "Edit the data/records.bib directly, set the colrev_status to 'md_prepared' and "
            "create a commit.\n"  # call this script again to create a commit
        )

        # if prep_man_operation.review_manager.dataset.has_changes():
        #     if "y" == input("Create commit (y/n)?"):
        #         prep_man_operation.review_manager.create_commit(
        #            msg= "Manual preparation of records",
        #             manual_author=True,
        #         )
        #     else:
        #         input("Press Enter to exit.")
        # else:
        #     input("Press Enter to exit.")

        return records


if __name__ == "__main__":
    pass
