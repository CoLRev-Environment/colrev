#! /usr/bin/env python
"""CoLRev prescreen operation: Prescreen records (metadata)."""
from __future__ import annotations

import math
from pathlib import Path

import colrev.operation
import colrev.ops.built_in.prescreen.conditional_prescreen
import colrev.ops.built_in.prescreen.prescreen_table
import colrev.record


class Prescreen(colrev.operation.Operation):
    """Prescreen records (based on metadata)"""

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.prescreen,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.verbose = True

    def export_table(self, *, export_table_format: str = "csv") -> None:
        """Export a table with records to prescreen"""

        endpoint = colrev.ops.built_in.prescreen.prescreen_table.TablePrescreen(
            prescreen_operation=self, settings={"endpoint": "export_table"}
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.export_table(
            prescreen_operation=self,
            records=records,
            split=[],
            export_table_format=export_table_format,
        )

    def import_table(self, *, import_table_path: str) -> None:
        """Import a table with prescreened records"""

        endpoint = colrev.ops.built_in.prescreen.prescreen_table.TablePrescreen(
            prescreen_operation=self, settings={"endpoint": "import_table"}
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.import_table(
            prescreen_operation=self,
            records=records,
            import_table_path=import_table_path,
        )

    def include_all_in_prescreen(self) -> None:
        """Include all records in the prescreen"""

        endpoint = (
            colrev.ops.built_in.prescreen.conditional_prescreen.ConditionalPrescreen(
                prescreen_operation=self, settings={"endpoint": "include_all"}
            )
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.run_prescreen(self, records, [])

    def get_data(self) -> dict:
        """Get the data for prescreen"""

        # pylint: disable=duplicate-code

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if colrev.record.RecordState.md_processed == x["colrev_status"]
            ]
        )
        pad = min((max(len(x["ID"]) for x in record_header_list) + 2), 40)
        items = self.review_manager.dataset.read_next_record(
            conditions=[{"colrev_status": colrev.record.RecordState.md_processed}]
        )
        prescreen_data = {"nr_tasks": nr_tasks, "PAD": pad, "items": items}

        return prescreen_data

    def create_prescreen_split(self, *, create_split: int) -> list:
        """Split the prescreen between researchers"""

        prescreen_splits = []

        data = self.get_data()
        nrecs = math.floor(data["nr_tasks"] / create_split)

        self.review_manager.report_logger.info(
            f"Creating prescreen splits for {create_split} researchers "
            f"({nrecs} each)"
        )

        added: list[str] = []
        while len(added) < nrecs:
            added.append(next(data["items"])["ID"])
        prescreen_splits.append("colrev prescreen --split " + ",".join(added))

        return prescreen_splits

    def setup_custom_script(self) -> None:
        """Setup a custom prescreen script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom/custom_prescreen_script.py")
        )

        if filedata:
            with open("custom_prescreen_script.py", "w", encoding="utf8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_prescreen_script.py"))

        self.review_manager.settings.prescreen.prescreen_package_endpoints.append(
            {"endpoint": "custom_prescreen_script"}
        )
        self.review_manager.save_settings()

    def main(self, *, split_str: str) -> None:
        """Prescreen records (main entrypoint)"""

        # pylint: disable=duplicate-code
        split = []
        if split_str != "NA":
            split = split_str.split(",")
            split.remove("")

        records = self.review_manager.dataset.load_records_dict()

        package_manager = self.review_manager.get_package_manager()

        prescreen_package_endpoints = (
            self.review_manager.settings.prescreen.prescreen_package_endpoints
        )
        for prescreen_package_endpoint in prescreen_package_endpoints:

            self.review_manager.logger.info(
                f"Run {prescreen_package_endpoint['endpoint']}"
            )
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.prescreen,
                selected_packages=prescreen_package_endpoints,
                operation=self,
            )
            endpoint = endpoint_dict[prescreen_package_endpoint["endpoint"]]
            records = endpoint.run_prescreen(self, records, split)  # type: ignore


if __name__ == "__main__":
    pass
