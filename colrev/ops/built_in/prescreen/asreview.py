#! /usr/bin/env python
"""ASReview-based prescreen"""
from __future__ import annotations

import csv
import os
import typing
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.record

if False:  # pylint: disable=using-constant-test
    if typing.TYPE_CHECKING:
        import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class ASReviewPrescreen(JsonSchemaMixin):

    """ASReview-based prescreen"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = False

    endpoint_path = Path("prescreen/asreview")
    export_filepath = endpoint_path / Path("records_to_screen.csv")

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        if not prescreen_operation.review_manager.in_ci_environment():
            try:
                # pylint: disable=import-outside-toplevel

                import asreview  # noqa: F401

                _ = asreview
            except (ImportError, ModuleNotFoundError) as exc:
                raise colrev_exceptions.MissingDependencyError(
                    "Dependency asreview not found. "
                    "Please install it\n  pip install asreview"
                ) from exc

    def __export_for_asreview(
        self,
        prescreen: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> None:
        self.endpoint_path.mkdir(exist_ok=True, parents=True)

        prescreen.review_manager.logger.info("Export: asreview")

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/74
        # tbd. whether the selection is necessary
        records = {
            ID: r
            for ID, r in records.items()
            if r["colrev_status"] in [colrev.record.RecordState.md_processed]
        }
        # Casting to string (in particular the RecordState Enum)
        records = {
            ID: {
                k: str(v)
                for k, v in r.items()
                if k
                not in [
                    "colrev_origin",
                    "colrev_status",
                    "colrev_masterdata_provenance",
                    "colrev_id",
                    "colrev_data_provenance",
                ]
            }
            for ID, r in records.items()
        }

        to_screen_df = pd.DataFrame.from_dict(records)
        to_screen_df.to_csv(self.export_filepath, quoting=csv.QUOTE_NONNUMERIC)

    def __import_from_asreview(
        self, prescreen_operation: colrev.ops.prescreen.Prescreen, records: dict
    ) -> None:
        def get_last_modified(input_paths: list[str]) -> Path:
            latest_file = max(input_paths, key=os.path.getmtime)
            return Path(latest_file)

        available_files = [
            str(x)
            for x in self.endpoint_path.glob("**/*")
            if "records_to_screen" not in str(x) and x.suffix in [".csv"]
        ]
        if 0 == len(available_files):
            return

        asreview_project_file = get_last_modified(available_files)

        print(f"Loading prescreen results from {asreview_project_file}")

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/74
        # get asreview (python package) version / Docker asreview version
        # If both are available (and if they differ), the user will have to select
        # the one that was actually used

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/74
        # if the included column is not set, no decision has been recorded
        # The idea of asreview is that they could be set to "excluded" automatically
        # We would probably want to do that in a separate commit

        if asreview_project_file.suffix == ".asreview":  # "Export project" in asreview
            print(
                "the project export seems to have changed. we now need to parse"
                "the results.sql file..."
            )
            return
            # import zipfile
            # with zipfile.ZipFile(asreview_project_file, "r") as zip_ref:
            #     zip_ref.extractall(self.endpoint_path)
            # os.remove(asreview_project_file)

            # prescreen.review_manager.dataset.\
            # add_changes(path=str(self.endpoint_path))
            # csv_dir = self.endpoint_path / Path("data")
            # csv_path = next(csv_dir.glob("*.csv"))
            # to_import = pd.read_csv(csv_path)

            # labels_json_path = self.endpoint_path / Path("labeled.json")
            # with open(labels_json_path) as json_str:
            #     label_data = json.loads(json_str.read())
            # label_df = pd.DataFrame(label_data, columns=["row_num", "included"])
            # label_df.reset_index(drop=True)
            # label_df.set_index("row_num", inplace=True)

            # to_import = pd.merge(to_import, label_df,
            #  left_index=True, right_index=True)

            # for index, row in to_import.iterrows():
            #     prescreen_record = Record(data=records[row["ID"]])
            #     if 1 == row["included"]:
            #       prescreen_operation.prescreen(
            #          record=prescreen_record,
            #          prescreen_inclusion=True,
            #       )
            #     if 0 == row["included"]:
            #        prescreen_operation.prescreen(
            #            record=prescreen_record,
            #            prescreen_inclusion=False,
            #        )
            # result_json_path = self.endpoint_path / Path("result.json")
            # with open(result_json_path) as json_str:
            #     json_data = json.loads(json_str.read())

            # prescreen.review_manager.report_logger.info({
            #     "version": json_data["version"],
            #     "software_version": json_data["software_version"],
            # })
            # prescreen.review_manager.report_logger.info(
            #     "asreview settings: "
            # f"\n{prescreen.review_manager.p_printer.pformat(json_data['settings'])}"
            # )

        if asreview_project_file.suffix == ".csv":  # "Export results" in asreview
            to_import = pd.read_csv(asreview_project_file)
            for _, row in to_import.iterrows():
                prescreen_record = colrev.record.Record(data=records[row["ID"]])
                if str(row["included"]) == "1":
                    prescreen_operation.prescreen(
                        record=prescreen_record,
                        prescreen_inclusion=True,
                    )
                elif str(row["included"]) == "0":
                    prescreen_operation.prescreen(
                        record=prescreen_record,
                        prescreen_inclusion=False,
                    )
                else:
                    print(f'not prescreened: {row["ID"]}')

        # gh_issue https://github.com/CoLRev-Environment/colrev/issues/74
        # add version

        prescreen_operation.review_manager.create_commit(
            msg="Pre-screening (manual, with asreview)",
            manual_author=True,
        )

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,
    ) -> dict:
        """Prescreen records based on ASReview"""

        # there may be an optional setting to change the endpoint_path

        endpoint_path_empty = not any(Path(self.endpoint_path).iterdir())

        # Note : we always update/overwrite the to_screen csv
        self.__export_for_asreview(prescreen_operation, records, split)

        if endpoint_path_empty:
            start_screen_selected = True
        else:
            start_screen_selected = "y" == input("Start prescreen [y,n]?")

        if start_screen_selected:
            # Note : the Docker image throws errors for Linux machines
            # The pip package is recommended anyway.

            print(
                "\n  To start the prescreen, create a project and import"
                f" the following csv file: \n\n     {self.export_filepath}"
            )
            print(
                "\n\n  Once completed, export the results as a csv file and"
                f" save in {self.endpoint_path}"
            )
            input("\n  Press Enter to start and ctrl+c to stop ...")
            print("\n\n  ASReview will open shortly.")

            # gh_issue https://github.com/CoLRev-Environment/colrev/issues/74
            # if not available: ask to "pip install asreview"
            # pylint: disable=import-outside-toplevel
            from asreview.entry_points import LABEntryPoint

            try:
                asreview = LABEntryPoint()
                asreview.execute(argv={})
            except KeyboardInterrupt:
                print("\n\n\nCompleted prescreen. ")

        if input("Import prescreen from asreview [y,n]?") == "y":
            self.__import_from_asreview(prescreen_operation, records)

            if prescreen_operation.review_manager.dataset.has_changes():
                if input("create commit [y,n]?") == "y":
                    prescreen_operation.review_manager.create_commit(
                        msg="Pre-screen (asreview)",
                        manual_author=True,
                    )

        return records


if __name__ == "__main__":
    pass
