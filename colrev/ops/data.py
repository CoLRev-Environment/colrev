#! /usr/bin/env python
"""CoLRev data operation: extract data, analyze, and synthesize."""
from __future__ import annotations

import typing
from pathlib import Path

import colrev.env.tei_parser
import colrev.packages.grobid_tei.src.grobid_tei
import colrev.process.operation
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState


class Data(colrev.process.operation.Operation):
    """Class supporting structured and unstructured
    data extraction, analysis and synthesis"""

    _pad = 0
    type = OperationsType.data

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.package_manager = self.review_manager.get_package_manager()

    def get_record_ids_for_synthesis(self, records: dict) -> list:
        """Get the IDs of records for the synthesis"""
        return [
            ID
            for ID, record in records.items()
            if record[Fields.STATUS]
            in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]
        ]

    def reading_heuristics(self) -> list:
        """Determine heuristics for the reading process"""

        enlit_list = []
        records = self.review_manager.dataset.load_records_dict()
        for relevant_record_id in self.get_record_ids_for_synthesis(records):
            enlit_status = str(records[relevant_record_id][Fields.STATUS])
            enlit_status = enlit_status.replace("rev_included", "").replace(
                "rev_synthesized", "synthesized"
            )
            enlit_list.append(
                {
                    Fields.ID: relevant_record_id,
                    "score": 0,
                    "score_intensity": 0,
                    Fields.STATUS: enlit_status,
                }
            )

        tei_path = colrev.packages.grobid_tei.src.grobid_tei.GROBIDTEI.TEI_PATH_RELATIVE
        required_records_ids = self.get_record_ids_for_synthesis(records)

        missing = []
        for required_records_id in required_records_ids:
            tei_file = tei_path / Path(f"{required_records_id}.tei.xml")
            if not tei_file.is_file():
                missing.append(required_records_id)

            tei_doc = colrev.env.tei_parser.TEIParser(
                tei_path=tei_file,
            )
            tei_doc.mark_references(records=records)
            data = tei_doc.get_tei_str()
            for enlit_item in enlit_list:
                id_string = f'ID="{enlit_item[Fields.ID]}"'
                if id_string in data:
                    enlit_item["score"] += 1
                enlit_item["score_intensity"] += data.count(id_string)

        if len(missing) > 0:
            print(f"Records with missing tei file: {missing}")

        enlit_list = sorted(enlit_list, key=lambda d: d["score"], reverse=True)

        return enlit_list

    def setup_custom_script(self) -> None:
        """Setup a custom data script"""

        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.ops", filename=Path("custom_scripts/custom_data_script.py")
        )
        if filedata:
            with open("custom_data_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(Path("custom_data_script.py"))

        new_data_endpoint = {"endpoint": "custom_data_script"}

        self.review_manager.settings.data.data_package_endpoints.append(
            new_data_endpoint
        )
        self.review_manager.save_settings()

    def _pre_data(self, *, records: dict, silent_mode: bool) -> None:
        if not silent_mode:
            self.review_manager.logger.info("Data")
            self.review_manager.logger.info(
                "The data operation covers different forms of data extraction, "
                "analysis, and synthesis."
            )
            self.review_manager.logger.info(
                "See https://colrev-environment.github.io/colrev/manual/data/data.html"
            )
        self._pad = min((max(len(ID) for ID in list(records.keys()) + [""]) + 2), 35)

    def _get_synthesized_record_status_matrix(self, records: dict) -> dict:
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
        return synthesized_record_status_matrix

    def _update_record_status_matrix(
        self, *, records: dict, synthesized_record_status_matrix: dict
    ) -> bool:
        records_changed = False
        for (
            record_id,
            individual_status_dict,
        ) in synthesized_record_status_matrix.items():
            if all(x for x in individual_status_dict.values()):
                if records[record_id][Fields.STATUS] != RecordState.rev_synthesized:
                    if self.review_manager.verbose_mode:
                        self.review_manager.report_logger.info(
                            f" {record_id}".ljust(self._pad, " ")
                            + "set colrev_status to synthesized"
                        )
                        self.review_manager.logger.info(
                            f" {record_id}".ljust(self._pad, " ")
                            + "set colrev_status to synthesized"
                        )

                if RecordState.rev_synthesized != records[record_id][Fields.STATUS]:
                    # pylint: disable=colrev-direct-status-assign
                    records[record_id].update(colrev_status=RecordState.rev_synthesized)
                    records_changed = True
            else:
                if RecordState.rev_included != records[record_id][Fields.STATUS]:
                    # pylint: disable=colrev-direct-status-assign
                    records[record_id].update(colrev_status=RecordState.rev_included)
                    records_changed = True
        return records_changed

    def _post_data(self, *, silent_mode: bool) -> None:
        # if self.review_manager.verbose_mode:
        #     self.review_manager.p_printer.pprint(synthesized_record_status_matrix)

        if self.review_manager.verbose_mode and not silent_mode:
            print()

        if not silent_mode:
            self.review_manager.logger.info(
                f"{Colors.GREEN}Completed data operation{Colors.END}"
            )
        if self.review_manager.in_ci_environment():
            print("\n\n")

    @colrev.process.operation.Operation.decorate()
    def main(
        self,
        *,
        selection_list: typing.Optional[list] = None,
        records: typing.Optional[dict] = None,
        silent_mode: bool = False,
    ) -> dict:
        """Data operation (main entrypoint)

        silent_mode: for review_manager checks
        """

        if not records:
            records = self.review_manager.dataset.load_records_dict()

        self._pre_data(records=records, silent_mode=silent_mode)

        synthesized_record_status_matrix = self._get_synthesized_record_status_matrix(
            records
        )

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
                    f"Data: {data_package_endpoint['endpoint'].replace('colrev.', '')}"
                )

            data_class = self.package_manager.get_package_endpoint_class(
                package_type=EndpointType.data,
                package_identifier=data_package_endpoint["endpoint"],
            )

            endpoint = data_class(data_operation=self, settings=data_package_endpoint)

            endpoint.update_data(  # type: ignore
                records, synthesized_record_status_matrix, silent_mode=silent_mode
            )

            endpoint.update_record_status_matrix(  # type: ignore
                synthesized_record_status_matrix,
                data_package_endpoint["endpoint"],
            )

            if self.review_manager.verbose_mode and not silent_mode:
                msg = f"Updated {endpoint.settings.endpoint}"  # type: ignore
                self.review_manager.logger.info(msg)

        records_status_changed = self._update_record_status_matrix(
            records=records,
            synthesized_record_status_matrix=synthesized_record_status_matrix,
        )
        if records_status_changed:
            self.review_manager.dataset.save_records_dict(records)

        self._post_data(silent_mode=silent_mode)

        no_endpoints_registered = 0 == len(
            self.review_manager.settings.data.data_package_endpoints
        )

        return {
            "ask_to_commit": self.review_manager.dataset.has_record_changes(),
            "no_endpoints_registered": no_endpoints_registered,
        }
