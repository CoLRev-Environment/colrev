#! /usr/bin/env python
"""Creation of a PRISMA chart as part of the data operations"""
from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import List

import docker
import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from docker.errors import DockerException

import colrev.env.package_manager
import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.data


@zope.interface.implementer(colrev.env.package_manager.DataPackageEndpointInterface)
@dataclass
class PRISMA(JsonSchemaMixin):
    """Create a PRISMA diagram"""

    ci_supported: bool = False

    @dataclass
    class PRISMASettings(colrev.env.package_manager.DefaultSettings, JsonSchemaMixin):
        """PRISMA settings"""

        endpoint: str
        version: str
        diagram_path: List[Path] = field(default_factory=lambda: [Path("PRISMA.png")])

    settings_class = PRISMASettings

    def __init__(
        self,
        *,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        # Set default values (if necessary)
        if "version" not in settings:
            settings["version"] = "0.1"

        if "diagram_path" in settings:
            settings["diagram_path"] = [Path(path) for path in settings["diagram_path"]]
        else:
            settings["diagram_path"] = [Path("PRISMA.png")]

        self.settings = self.settings_class.load_settings(data=settings)

        self.csv_path = data_operation.review_manager.output_dir / Path("PRISMA.csv")
        self.data_operation = data_operation

        self.settings.diagram_path = [
            data_operation.review_manager.output_dir / path
            for path in self.settings.diagram_path
        ]

        if not data_operation.review_manager.in_ci_environment():
            self.prisma_image = "colrev/prisma:latest"
            data_operation.review_manager.environment_manager.build_docker_image(
                imagename=self.prisma_image
            )

    def get_default_setup(self) -> dict:
        """Get the default setup"""

        prisma_endpoint_details = {
            "endpoint": "colrev.prisma",
            "version": "0.1",
            "diagram_path": ["PRISMA.png"],
        }
        return prisma_endpoint_details

    def __export_csv(
        self, data_operation: colrev.ops.data.Data, silent_mode: bool
    ) -> None:
        csv_resource_path = Path("template/") / Path("prisma/PRISMA.csv")
        self.csv_path.parent.mkdir(exist_ok=True, parents=True)

        if self.csv_path.is_file():
            os.remove(self.csv_path)
        colrev.env.utils.retrieve_package_file(
            template_file=csv_resource_path, target=self.csv_path
        )

        status_stats = data_operation.review_manager.get_status_stats()

        prisma_data = pd.read_csv(self.csv_path)
        prisma_data["ind"] = prisma_data["data"]
        prisma_data.set_index("ind", inplace=True)
        prisma_data.loc["database_results", "n"] = status_stats.overall.md_retrieved
        prisma_data.loc[
            "duplicates", "n"
        ] = status_stats.currently.md_duplicates_removed
        prisma_data.loc["records_screened", "n"] = status_stats.overall.rev_prescreen
        prisma_data.loc[
            "records_excluded", "n"
        ] = status_stats.overall.rev_prescreen_excluded
        if status_stats.currently.exclusion:
            prisma_data.loc["dbr_excluded", "n"] = ";".join(
                f"Reason {key}, {val}"
                for key, val in status_stats.currently.exclusion.items()
            )
        else:
            prisma_data.loc[
                "dbr_excluded", "n"
            ] = f"Overall, {status_stats.overall.rev_excluded}"

        prisma_data.loc["dbr_assessed", "n"] = status_stats.overall.rev_screen
        prisma_data.loc["new_studies", "n"] = status_stats.overall.rev_included
        prisma_data.loc[
            "dbr_notretrieved_reports", "n"
        ] = status_stats.overall.pdf_not_available
        prisma_data.loc[
            "dbr_sought_reports", "n"
        ] = status_stats.overall.rev_prescreen_included

        prisma_data.to_csv(self.csv_path, index=False)
        data_operation.review_manager.logger.debug(f"Exported {self.csv_path}")

        if not status_stats.completeness_condition and not silent_mode:
            data_operation.review_manager.logger.info("Review not (yet) complete")

    def __export_diagram(
        self, data_operation: colrev.ops.data.Data, silent_mode: bool
    ) -> None:
        if not self.csv_path.is_file():
            data_operation.review_manager.logger.error(
                "File %s does not exist.", self.csv_path
            )
            data_operation.review_manager.logger.info(
                "Complete processing and use colrev data"
            )
            return

        csv_relative_path = self.csv_path.relative_to(
            data_operation.review_manager.path
        )

        if not silent_mode:
            data_operation.review_manager.logger.info("Create PRISMA diagram")

        for diagram_path in self.settings.diagram_path:
            diagram_relative_path = diagram_path.relative_to(
                data_operation.review_manager.path
            )

            script = (
                "Rscript "
                + "/prisma.R "
                + f"/data/{csv_relative_path} "
                + f"/data/{diagram_relative_path}"
            )
            # Users can place a custom script in src/prisma.R
            if (data_operation.review_manager.path / Path("src/prisma.R")).is_file():
                script = (
                    "Rscript "
                    + "-e \"source('/data/src/prisma.R')\" "
                    + f"/data/{csv_relative_path} "
                    + f"/data/{diagram_relative_path}"
                )

            self.__call_docker_build_process(
                data_operation=data_operation, script=script
            )
            csv_relative_path.unlink()

    def __call_docker_build_process(
        self, *, data_operation: colrev.ops.data.Data, script: str
    ) -> None:
        try:
            uid = os.stat(data_operation.review_manager.settings_path).st_uid
            gid = os.stat(data_operation.review_manager.settings_path).st_gid
            user = f"{uid}:{gid}"

            client = docker.from_env()

            msg = f"Running docker container created from image {self.prisma_image}"
            data_operation.review_manager.report_logger.info(msg)

            client.containers.run(
                image=self.prisma_image,
                command=script,
                user=user,
                volumes=[os.getcwd() + ":/data"],
            )
        except docker.errors.ImageNotFound:
            data_operation.review_manager.logger.error("Docker image not found")
        except docker.errors.ContainerError as exc:
            if "Temporary failure in name resolution" in str(exc):
                raise colrev_exceptions.ServiceNotAvailableException(
                    "prisma service failed"
                ) from exc
            raise exc
        except DockerException as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                f"Docker service not available ({exc}). Please install/start Docker."
            ) from exc

    def update_data(
        self,
        data_operation: colrev.ops.data.Data,
        records: dict,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,  # pylint: disable=unused-argument
        silent_mode: bool,
    ) -> None:
        """Update the data/prisma diagram"""

        self.__export_csv(data_operation=data_operation, silent_mode=silent_mode)
        self.__export_diagram(data_operation=data_operation, silent_mode=silent_mode)

    def update_record_status_matrix(
        self,
        data_operation: colrev.ops.data.Data,  # pylint: disable=unused-argument
        synthesized_record_status_matrix: dict,
        endpoint_identifier: str,
    ) -> None:
        """Update the record_status_matrix"""

        # Note : automatically set all to True / synthesized
        for syn_id in list(synthesized_record_status_matrix.keys()):
            synthesized_record_status_matrix[syn_id][endpoint_identifier] = True

    def get_advice(
        self,
        review_manager: colrev.review_manager.ReviewManager,  # pylint: disable=unused-argument
    ) -> dict:
        """Get advice on the next steps (for display in the colrev status)"""

        data_endpoint = "Data operation [prisma data endpoint]: "

        path_str = ",".join(
            [
                str(x.relative_to(review_manager.path))
                for x in self.settings.diagram_path
            ]
        )
        advice = {
            "msg": f"{data_endpoint}"
            + "\n    - The PRISMA diagram is created automatically "
            + f"({path_str})",
            "detailed_msg": "TODO",
        }
        return advice


if __name__ == "__main__":
    pass
