#! /usr/bin/env python
"""CoLRev prescreen operation: Prescreen records (metadata)."""
from __future__ import annotations

import math
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ops.built_in.prescreen.conditional_prescreen
import colrev.ops.built_in.prescreen.prescreen_table
import colrev.record
import colrev.ui_cli.cli_colors as colors


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

    def include_all_in_prescreen(self, *, persist: bool) -> None:
        """Include all records in the prescreen"""

        if persist:
            self.review_manager.settings.prescreen.prescreen_package_endpoints = []
            self.review_manager.save_settings()

        endpoint = (
            colrev.ops.built_in.prescreen.conditional_prescreen.ConditionalPrescreen(
                prescreen_operation=self, settings={"endpoint": "include_all"}
            )
        )
        records = self.review_manager.dataset.load_records_dict()
        endpoint.run_prescreen(self, records, [])

    def include_records(self, *, ids: str) -> None:
        """Include records in the prescreen"""

        self.__prescreen_records(ids=ids, include=True)

    def exclude_records(self, *, ids: str) -> None:
        """Exclude records in the prescreen"""

        self.__prescreen_records(ids=ids, include=False)

    def __prescreen_records(self, *, ids: str, include: bool) -> None:
        records = self.review_manager.dataset.load_records_dict()
        for record_id in ids.split(","):
            if record_id not in records:
                self.review_manager.logger.info(f" not found: {record_id}")
                continue
            record = colrev.record.Record(data=records[record_id])
            if (
                record.data["colrev_status"] != colrev.record.RecordState.md_processed
                and not self.review_manager.force_mode
            ):
                self.review_manager.logger.info(
                    f" record not md_processed / cannot prescreen: {record_id}"
                )
                continue
            if include:
                record.set_status(
                    target_state=colrev.record.RecordState.rev_prescreen_included
                )
            else:
                record.set_status(
                    target_state=colrev.record.RecordState.rev_prescreen_excluded
                )

        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

        msg = f"Pre-screen (exclude {ids})"
        if include:
            msg = f"Pre-screen (include {ids})"

        self.review_manager.create_commit(
            msg=msg,
            manual_author=False,
        )

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
            file_path=Path("template/custom_scripts/custom_prescreen_script.py")
        )

        if filedata:
            with open("custom_prescreen_script.py", "w", encoding="utf8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_prescreen_script.py"))

        self.review_manager.settings.prescreen.prescreen_package_endpoints.append(
            {"endpoint": "custom_prescreen_script"}
        )
        self.review_manager.save_settings()

    def __prescreen_include_all(self, *, records: dict) -> None:
        # pylint: disable=duplicate-code
        self.review_manager.logger.info("Prescreen-including all records")
        for record_dict in records.values():
            if record_dict["colrev_status"] == colrev.record.RecordState.md_processed:
                record = colrev.record.Record(data=record_dict)
                record.set_status(
                    target_state=colrev.record.RecordState.rev_prescreen_included
                )
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Pre-screen (include_all)",
            manual_author=False,
        )

    def __print_stats(self, *, selected_record_ids: list) -> None:
        records = self.review_manager.dataset.load_records_dict(header_only=True)
        prescreen_excluded = [
            r["ID"]
            for r in records.values()
            if colrev.record.RecordState.rev_prescreen_excluded == r["colrev_status"]
            and r["ID"] in selected_record_ids
        ]
        prescreen_included = [
            r["ID"]
            for r in records.values()
            if colrev.record.RecordState.rev_prescreen_included == r["colrev_status"]
            and r["ID"] in selected_record_ids
        ]

        if not prescreen_excluded and not prescreen_included:
            return

        print()
        self.review_manager.logger.info("Statistics")
        for record_dict in records.values():
            if record_dict["ID"] in prescreen_excluded:
                self.review_manager.logger.info(
                    f" {record_dict['ID']}".ljust(41)
                    + "md_processed → rev_prescreen_excluded"
                )
            elif record_dict["ID"] in prescreen_included:
                self.review_manager.logger.info(
                    f"{colors.GREEN}"
                    + f" {record_dict['ID']}".ljust(41)
                    + f"md_processed → rev_prescreen_included{colors.END}"
                )

        nr_prescreen_excluded = len(prescreen_excluded)
        nr_prescreen_included = len(prescreen_included)

        self.review_manager.logger.info(
            "Prescreen excluded".ljust(30)
            + f"{nr_prescreen_excluded}".rjust(10, " ")
            + " records"
        )
        self.review_manager.logger.info(
            "Prescreen included".ljust(30)
            + f"{nr_prescreen_included}".rjust(10, " ")
            + " records"
        )

    def prescreen(
        self,
        *,
        record: colrev.record.Record,
        prescreen_inclusion: bool,
        PAD: int = 40,
    ) -> None:
        """Save the prescreen decision"""
        if prescreen_inclusion:
            self.review_manager.report_logger.info(
                f" {record.data['ID']}".ljust(PAD, " ") + "Included in prescreen"
            )
            record.set_status(
                target_state=colrev.record.RecordState.rev_prescreen_included
            )
            self.review_manager.dataset.save_records_dict(
                records={record.data["ID"]: record.get_data()}, partial=True
            )

        else:
            self.review_manager.report_logger.info(
                f" {record.data['ID']}".ljust(PAD, " ") + "Excluded in prescreen"
            )
            record.set_status(
                target_state=colrev.record.RecordState.rev_prescreen_excluded
            )
            self.review_manager.dataset.save_records_dict(
                records={record.data["ID"]: record.get_data()}, partial=True
            )

        self.review_manager.dataset.add_record_changes()

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

        if not prescreen_package_endpoints:
            self.__prescreen_include_all(records=records)
            return

        for prescreen_package_endpoint in prescreen_package_endpoints:
            self.review_manager.logger.debug(
                f"Run {prescreen_package_endpoint['endpoint']}"
            )
            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.prescreen,
                selected_packages=prescreen_package_endpoints,
                operation=self,
                only_ci_supported=self.review_manager.in_ci_environment(),
            )
            if prescreen_package_endpoint["endpoint"] not in endpoint_dict:
                self.review_manager.logger.info(
                    f'Skip {prescreen_package_endpoint["endpoint"]} (not available)'
                )
                if self.review_manager.in_ci_environment():
                    raise colrev_exceptions.ServiceNotAvailableException(
                        dep="colrev presceen",
                        detailed_trace="presceen not available in ci environment",
                    )
                raise colrev_exceptions.ServiceNotAvailableException(
                    dep="colrev presceen", detailed_trace="presceen not available"
                )

            endpoint = endpoint_dict[prescreen_package_endpoint["endpoint"]]

            selected_record_ids = [
                r["ID"]
                for r in records.values()
                if colrev.record.RecordState.md_processed == r["colrev_status"]
            ]
            endpoint.run_prescreen(self, records, split)  # type: ignore

            self.__print_stats(selected_record_ids=selected_record_ids)

        self.review_manager.logger.info(
            "%sCompleted prescreen operation%s", colors.GREEN, colors.END
        )
        if self.review_manager.in_ci_environment():
            print("\n\n")


if __name__ == "__main__":
    pass
