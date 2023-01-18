#! /usr/bin/env python
"""CoLRev data operation: extract data, analyze, and synthesize."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import colrev.operation
import colrev.record
import colrev.ui_cli.cli_colors as colors


class Data(colrev.operation.Operation):
    """Class supporting structured and unstructured
    data extraction, analysis and synthesis"""

    __pad = 0

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.data,
            notify_state_transition_operation=notify_state_transition_operation,
        )

    def get_record_ids_for_synthesis(self, records: dict) -> list:
        """Get the IDs of records for the synthesis"""
        return [
            ID
            for ID, record in records.items()
            if record["colrev_status"]
            in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]
        ]

    def reading_heuristics(self) -> list:
        """Determine heuristics for the reading process"""

        enlit_list = []
        records = self.review_manager.dataset.load_records_dict()
        for relevant_record_id in self.get_record_ids_for_synthesis(records):
            enlit_status = str(records[relevant_record_id]["colrev_status"])
            enlit_status = enlit_status.replace("rev_included", "").replace(
                "rev_synthesized", "synthesized"
            )
            enlit_list.append(
                {
                    "ID": relevant_record_id,
                    "score": 0,
                    "score_intensity": 0,
                    "colrev_status": enlit_status,
                }
            )

        tei_path = self.review_manager.path / Path("tei")
        required_records_ids = self.get_record_ids_for_synthesis(records)
        missing = [
            x
            for x in list(tei_path.glob("*.tei.xml"))
            if not any(i in str(x) for i in required_records_ids)
        ]
        if len(missing) > 0:
            print(f"Records with missing tei file: {missing}")

        for tei_file in tei_path.glob("*.tei.xml"):
            data = tei_file.read_text()
            for enlit_item in enlit_list:
                id_string = f'ID="{enlit_item["ID"]}"'
                if id_string in data:
                    enlit_item["score"] += 1
                enlit_item["score_intensity"] += data.count(id_string)

        enlit_list = sorted(enlit_list, key=lambda d: d["score"], reverse=True)

        return enlit_list

    def profile(self) -> None:
        """Create a profile of the sample"""

        self.review_manager.logger.info("Create sample profile")

        def prep_records(*, records: dict) -> pd.DataFrame:
            for record in records:
                record["outlet"] = record.get("journal", record.get("booktitle", "NA"))

            records_df = pd.DataFrame.from_records(list(records.values()))

            required_cols = [
                "ID",
                "ENTRYTYPE",
                "author",
                "title",
                "journal",
                "booktitle",
                "outlet",
                "year",
                "volume",
                "number",
                "pages",
                "doi",
            ]
            available_cols = records_df.columns.intersection(list(set(required_cols)))
            cols = [x for x in required_cols if x in available_cols]
            records_df = records_df[cols]
            return records_df

        def prep_observations(
            *, prepared_records_df: pd.DataFrame, records: dict
        ) -> pd.DataFrame:

            included_papers = [
                ID
                for ID, record in records.items()
                if record["colrev_status"]
                in [
                    colrev.record.RecordState.rev_synthesized,
                    colrev.record.RecordState.rev_included,
                ]
            ]
            observations = prepared_records_df[
                prepared_records_df["ID"].isin(included_papers)
            ].copy()
            observations.loc[:, "year"] = observations.loc[:, "year"].astype(int)
            missing_outlet = observations[observations["outlet"].isnull()][
                "ID"
            ].tolist()
            if len(missing_outlet) > 0:
                self.review_manager.logger.info(f"No outlet: {missing_outlet}")
            return observations

        # if not status.get_completeness_condition():
        #     self.review_manager.logger.warning(
        #  f"{colors.RED}Sample not completely processed!{colors.END}")

        records = self.review_manager.dataset.load_records_dict()

        output_dir = self.review_manager.path / Path("output")
        output_dir.mkdir(exist_ok=True)

        prepared_records_df = prep_records(records=records)  # .values()
        observations = prep_observations(
            prepared_records_df=prepared_records_df, records=records
        )

        if observations.empty:
            self.review_manager.logger.info("No sample/observations available")
            return

        self.review_manager.logger.info("Generate output/sample.csv")
        observations.to_csv(output_dir / Path("sample.csv"), index=False)

        tabulated = pd.pivot_table(
            observations[["outlet", "year"]],
            index=["outlet"],
            columns=["year"],
            aggfunc=len,
            fill_value=0,
            margins=True,
        )
        # Fill missing years with 0 columns
        years = range(
            min(e for e in tabulated.columns if isinstance(e, int)),
            max(e for e in tabulated.columns if isinstance(e, int)) + 1,
        )
        for year in years:
            if year not in tabulated.columns:
                tabulated[year] = 0
        year_list = list(years)
        year_list.extend(["All"])  # type: ignore
        tabulated = tabulated[year_list]

        self.review_manager.logger.info("Generate profile output/journals_years.csv")
        tabulated.to_csv(output_dir / Path("journals_years.csv"))

        tabulated = pd.pivot_table(
            observations[["ENTRYTYPE", "year"]],
            index=["ENTRYTYPE"],
            columns=["year"],
            aggfunc=len,
            fill_value=0,
            margins=True,
        )
        self.review_manager.logger.info("Generate output/ENTRYTYPES.csv")
        tabulated.to_csv(output_dir / Path("ENTRYTYPES.csv"))

        self.review_manager.logger.info(f"Files are available in {output_dir.name}")

    def add_data_endpoint(self, *, data_endpoint: dict) -> None:
        """Add a data endpoint"""

        self.review_manager.settings.data.data_package_endpoints.append(data_endpoint)
        self.review_manager.save_settings()

    def setup_custom_script(self) -> None:
        """Setup a custom data script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_scripts/custom_data_script.py")
        )
        if filedata:
            with open("custom_data_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_data_script.py"))

        new_data_endpoint = {"endpoint": "custom_data_script"}

        self.review_manager.settings.data.data_package_endpoints.append(
            new_data_endpoint
        )
        self.review_manager.save_settings()

    def main(
        self,
        *,
        selection_list: list = None,
        records: dict = None,
        silent_mode: bool = False,
    ) -> dict:
        """Data operation (main entrypoint)

        silent_mode: for review_manager checks
        """

        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals

        if not silent_mode:
            self.review_manager.logger.info("Data")
            self.review_manager.logger.info(
                "The data operation covers different forms of data extraction, "
                "analysis, and synthesis."
            )

        no_endpoints_registered = 0 == len(
            self.review_manager.settings.data.data_package_endpoints
        )

        if not records:
            records = self.review_manager.dataset.load_records_dict()

        self.__pad = min((max(len(ID) for ID in list(records.keys()) + [""]) + 2), 35)

        included = self.get_record_ids_for_synthesis(records)

        # TBD: do we assume that records are not changed by the processes?
        # records = self.review_manager.dataset.load_records_dict()

        # synthesized_record_status_matrix (paper IDs x endpoint):
        # each endpoint sets synthesized = True/False
        # and if a paper has synthesized=True in all fields,
        # its overall status is set to synthesized
        # Some endpoints may always set synthesized
        default_row = {
            df["endpoint"]: False
            for df in self.review_manager.settings.data.data_package_endpoints
        }
        synthesized_record_status_matrix = {ID: default_row.copy() for ID in included}

        # if self.review_manager.verbose_mode:
        #     self.review_manager.p_printer.pprint(synthesized_record_status_matrix)

        package_manager = self.review_manager.get_package_manager()

        for (
            data_package_endpoint
        ) in self.review_manager.settings.data.data_package_endpoints:
            if selection_list:
                if not any(
                    x in data_package_endpoint["endpoint"] for x in selection_list
                ):
                    continue

            if not silent_mode:
                print()
                self.review_manager.logger.info(
                    f"Data: {data_package_endpoint['endpoint'].replace('colrev_built_in.', '')}"
                )

            endpoint_dict = package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.data,
                selected_packages=[data_package_endpoint],
                operation=self,
            )
            endpoint = endpoint_dict[data_package_endpoint["endpoint"]]

            endpoint.update_data(  # type: ignore
                self, records, synthesized_record_status_matrix, silent_mode=silent_mode
            )

            endpoint.update_record_status_matrix(  # type: ignore
                self,
                synthesized_record_status_matrix,
                data_package_endpoint["endpoint"],
            )

            if self.review_manager.verbose_mode and not silent_mode:
                msg = f"Updated {endpoint.settings.endpoint}"  # type: ignore
                self.review_manager.logger.info(msg)

        records_changed = False
        for (
            record_id,
            individual_status_dict,
        ) in synthesized_record_status_matrix.items():
            if all(x for x in individual_status_dict.values()):
                if (
                    records[record_id]["colrev_status"]
                    != colrev.record.RecordState.rev_synthesized
                ):
                    if self.review_manager.verbose_mode:
                        self.review_manager.report_logger.info(
                            f" {record_id}".ljust(self.__pad, " ")
                            + "set colrev_status to synthesized"
                        )
                        self.review_manager.logger.info(
                            f" {record_id}".ljust(self.__pad, " ")
                            + "set colrev_status to synthesized"
                        )

                if (
                    colrev.record.RecordState.rev_synthesized
                    != records[record_id]["colrev_status"]
                ):
                    records[record_id].update(
                        colrev_status=colrev.record.RecordState.rev_synthesized
                    )
                    records_changed = True
            else:
                if (
                    colrev.record.RecordState.rev_included
                    != records[record_id]["colrev_status"]
                ):
                    records[record_id].update(
                        colrev_status=colrev.record.RecordState.rev_included
                    )
                    records_changed = True

        # if self.review_manager.verbose_mode:
        #     self.review_manager.p_printer.pprint(synthesized_record_status_matrix)

        if self.review_manager.verbose_mode and not silent_mode:
            print()

        if records_changed:
            self.review_manager.dataset.save_records_dict(records=records)
            self.review_manager.dataset.add_record_changes()

        if not silent_mode:
            self.review_manager.logger.info(
                f"{colors.GREEN}Completed data operation{colors.END}"
            )

        return {
            "ask_to_commit": True,
            "no_endpoints_registered": no_endpoints_registered,
        }


if __name__ == "__main__":
    pass
