#! /usr/bin/env python
"""Creation of a PRISMA chart as part of the data operations"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import zope.interface
from dacite import from_dict

import colrev.env.package_manager
import colrev.env.utils
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageInterface)
class PRISMA:
    """Create a PRISMA diagram"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def get_default_setup(self) -> dict:
        prisma_endpoint_details = {
            "endpoint": "PRISMA",
            "prisma_data_endpoint_version": "0.1",
        }
        return prisma_endpoint_details

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
    ) -> None:

        prisma_resource_path = Path("template/") / Path("PRISMA.csv")
        prisma_path = Path("data/PRISMA.csv")
        prisma_path.parent.mkdir(exist_ok=True, parents=True)

        if prisma_path.is_file():
            os.remove(prisma_path)
        colrev.env.utils.retrieve_package_file(
            template_file=prisma_resource_path, target=prisma_path
        )

        status_stats = data_operation.review_manager.get_status_stats()

        prisma_data = pd.read_csv(prisma_path)
        prisma_data["ind"] = prisma_data["data"]
        prisma_data.set_index("ind", inplace=True)
        prisma_data.loc["database_results", "n"] = status_stats.overall.md_retrieved
        prisma_data.loc[
            "duplicates", "n"
        ] = status_stats.currently.md_duplicates_removed
        prisma_data.loc["records_screened", "n"] = status_stats.overall.rev_prescreen
        prisma_data.loc["records_excluded", "n"] = status_stats.overall.rev_excluded
        prisma_data.loc["dbr_assessed", "n"] = status_stats.overall.rev_screen
        prisma_data.loc["new_studies", "n"] = status_stats.overall.rev_included
        # TODO : TBD: if settings.pdf_get.pdf_required_for_screen_and_synthesis = False
        # should the following be included?
        prisma_data.loc[
            "dbr_notretrieved_reports", "n"
        ] = status_stats.overall.pdf_not_available
        prisma_data.loc[
            "dbr_sought_reports", "n"
        ] = status_stats.overall.rev_prescreen_included

        exclusion_stats = []
        for criterion, value in status_stats.currently.exclusion.items():
            exclusion_stats.append(f"Reason {criterion}, {value}")
        prisma_data.loc["dbr_excluded", "n"] = "; ".join(exclusion_stats)

        prisma_data.to_csv(prisma_path, index=False)
        print(f"Exported {prisma_path}")
        print(
            "Diagrams can be created online "
            "at https://estech.shinyapps.io/prisma_flowdiagram/"
        )

        if not status_stats.completeness_condition:
            print("Warning: review not (yet) complete")

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True


if __name__ == "__main__":
    pass
