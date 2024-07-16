#! /usr/bin/env python
"""CoLRev pdf_prep operation: Prepare PDF documents."""
from __future__ import annotations

import multiprocessing as mp
import os
import shutil
from multiprocessing.pool import ThreadPool as Pool
from pathlib import Path

import requests

import colrev.exceptions as colrev_exceptions
import colrev.packages.grobid_tei.src.grobid_tei
import colrev.process.operation
import colrev.record.record_pdf
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState


class PDFPrep(colrev.process.operation.Operation):
    """Prepare PDFs"""

    to_prepare: int
    pdf_prepared: int
    not_prepared: int

    pdf_prep_package_endpoints: dict

    type = OperationsType.pdf_prep

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        reprocess: bool = False,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=self.type,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.reprocess = reprocess

        self.cpus = 4

        self.pdf_qm = self.review_manager.get_pdf_qm()

    def _complete_successful_pdf_prep(
        self, *, record: colrev.record.record.Record, original_filename: str
    ) -> None:
        # pylint: disable=colrev-direct-status-assign
        record.data.update(colrev_status=RecordState.pdf_prepared)
        pdf_path = self.review_manager.path / Path(record.data[Fields.FILE])
        if pdf_path.suffix == ".pdf":
            try:
                record.data.update(colrev_pdf_id=record.get_colrev_pdf_id(pdf_path))
            except colrev_exceptions.ServiceNotAvailableException:
                self.review_manager.logger.error(
                    "Cannot create pdf-hash (Docker service not available)"
                )

        # colrev_status == pdf_imported : means successful
        # create *_backup.pdf if record[Fields.FILE] was changed
        if original_filename != record.data[Fields.FILE]:
            current_file = self.review_manager.path / Path(record.data[Fields.FILE])
            original_file = self.review_manager.path / Path(original_filename)
            if current_file.is_file() and original_file.is_file():
                backup_filename = self.review_manager.path / Path(
                    original_filename.replace(".pdf", "_backup.pdf")
                )
                shutil.move(str(original_file), str(backup_filename))
                shutil.move(str(current_file), str(original_filename))
                record.data[Fields.FILE] = str(
                    original_file.relative_to(self.review_manager.path)
                )

        # Backup:
        # Create a copy of the original PDF if users cannot
        # restore it from git
        # linked_file.rename(str(linked_file).replace(".pdf", "_backup.pdf"))

        if not self.review_manager.settings.pdf_prep.keep_backup_of_pdfs:
            # Remove temporary PDFs when processing has succeeded
            target_fname = self.review_manager.path / Path(
                f"{record.data[Fields.ID]}.pdf"
            )
            linked_file = self.review_manager.path / Path(record.data[Fields.FILE])

            if target_fname.name != linked_file.name:
                if target_fname.is_file():
                    os.remove(target_fname)
                shutil.move(str(linked_file), str(target_fname))
                record.data[Fields.FILE] = str(
                    target_fname.relative_to(self.review_manager.path)
                )

            if not self.review_manager.verbose_mode:
                # Delete temporary PDFs for which processing has failed:
                if target_fname.is_file():
                    pdf_dir = self.review_manager.paths.pdf
                    for fpath in pdf_dir.glob("*.pdf"):
                        if (
                            record.data[Fields.ID] in str(fpath)
                            and fpath != target_fname
                        ):
                            os.remove(fpath)

    # Note : no named arguments (multiprocessing)
    def prepare_pdf(self, item: dict) -> dict:
        """Prepare a PDF (based on package_endpoints in the settings)"""

        record_dict = item["record"]

        if (
            RecordState.pdf_imported != record_dict[Fields.STATUS]
            or Fields.FILE not in record_dict
        ):
            return record_dict

        pad = 50

        pdf_path = self.review_manager.path / Path(record_dict[Fields.FILE])
        if not Path(pdf_path).is_file():
            self.review_manager.logger.error(
                f"{record_dict[Fields.ID]}".ljust(46, " ")
                + "Linked file/pdf does not exist"
            )
            return record_dict

        record = colrev.record.record_pdf.PDFRecord(record_dict)
        if record_dict[Fields.FILE].endswith(".pdf"):
            record.set_text_from_pdf()
        original_filename = record_dict[Fields.FILE]

        self.review_manager.logger.debug(f"Start PDF prep of {record_dict[Fields.ID]}")
        # Note: if there are problems
        # colrev_status is set to pdf_needs_manual_preparation
        # if it remains 'imported', all preparation checks have passed
        detailed_msgs = []
        for (
            pdf_prep_package_endpoint
        ) in self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints:
            try:
                if (
                    pdf_prep_package_endpoint["endpoint"]
                    not in self.pdf_prep_package_endpoints
                ):
                    self.review_manager.logger.error(
                        f'Skip {pdf_prep_package_endpoint["endpoint"]} (not available)'
                    )
                    continue
                endpoint = self.pdf_prep_package_endpoints[
                    pdf_prep_package_endpoint["endpoint"]  # type: ignore
                ]

                msg = f"{endpoint.settings.endpoint}({record.data[Fields.ID]}):"
                self.review_manager.logger.debug(
                    msg.ljust(50, " ") + "called"  # type: ignore
                )

                record.data = endpoint.prep_pdf(record, pad)  # type: ignore
            except colrev_exceptions.PDFHashError:
                record.add_field_provenance_note(key=Fields.FILE, note="pdf-hash-error")

            except (
                colrev_exceptions.InvalidPDFException,
                colrev_exceptions.TEIException,
                requests.exceptions.ReadTimeout,
            ) as err:
                self.review_manager.logger.error(
                    f"Error for {record.data[Fields.ID]} "  # type: ignore
                    f"(in {endpoint.settings.endpoint} : {err})"  # type: ignore
                )
                record.set_status(RecordState.pdf_needs_manual_preparation)

            failed = (
                RecordState.pdf_needs_manual_preparation == record.data[Fields.STATUS]
            )

            if failed:
                msg_str = f"{endpoint.settings.endpoint}"  # type: ignore
                msg_str = msg_str.replace("colrev.", "")
                detailed_msgs.append(f"{Colors.ORANGE}{msg_str}{Colors.END}")

            # Note: if we break, the teis will not be generated.
            # if failed:
            #     break

        record.run_pdf_quality_model(self.pdf_qm, set_prepared=True)

        # Each pdf_prep_package_endpoint can create a new file
        # previous/temporary pdfs are deleted when the process is successful
        # The original PDF is never deleted automatically.
        # If successful, it is renamed to *_backup.pdf

        self.review_manager.logger.debug(
            f"Completed PDF prep of {record_dict[Fields.ID]}"
        )

        successfully_prepared = RecordState.pdf_prepared == record.data[Fields.STATUS]

        if successfully_prepared:
            self.review_manager.logger.info(
                f" {Colors.GREEN}{record_dict['ID']}".ljust(46)
                + f"pdf_imported → pdf_prepared{Colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f" {Colors.ORANGE}{record_dict['ID']} ".ljust(46)
                + f"pdf_imported → pdf_needs_manual_preparation {Colors.END}"
                f"({', '.join(detailed_msgs)})"
            )

        if successfully_prepared:
            self._complete_successful_pdf_prep(
                record=record, original_filename=original_filename
            )

        record.data.pop(Fields.TEXT_FROM_PDF, None)
        record.data.pop(Fields.NR_PAGES_IN_FILE, None)

        return record.get_data()

    def _get_data(self, *, batch_size: int) -> dict:
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if RecordState.pdf_imported == x[Fields.STATUS]
            ]
        )

        items = self.review_manager.dataset.read_next_record(
            conditions=[{Fields.STATUS: RecordState.pdf_imported}],
        )
        self.to_prepare = nr_tasks

        prep_data = {
            "nr_tasks": nr_tasks,
            "items": [],
        }

        if batch_size == 0:
            batch_size = nr_tasks
        for ind, item in enumerate(items):
            if ind > batch_size:
                break
            prep_data["items"].append({"record": item})  # type: ignore

        return prep_data

    def _set_to_reprocess(self) -> None:
        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if RecordState.pdf_needs_manual_preparation != record_dict["colrev_stauts"]:
                continue

            record = colrev.record.record_pdf.PDFRecord(record_dict)
            # pylint: disable=colrev-direct-status-assign
            record.data.update(colrev_status=RecordState.pdf_imported)
            record.reset_pdf_provenance_notes()

        self.review_manager.dataset.save_records_dict(records)

    # Note : no named arguments (multiprocessing)
    def _update_colrev_pdf_ids(self, record_dict: dict) -> dict:
        if Fields.FILE in record_dict:
            pdf_path = self.review_manager.path / Path(record_dict[Fields.FILE])
            record_dict.update(
                colrev_pdf_id=colrev.record.record_pdf.PDFRecord.get_colrev_pdf_id(
                    pdf_path
                )
            )
        return record_dict

    def update_colrev_pdf_ids(self) -> None:
        """Update the colrev-pdf-ids"""
        self.review_manager.logger.info("Update colrev_pdf_ids")
        records = self.review_manager.dataset.load_records_dict()
        pool = Pool(self.cpus)
        records_list = pool.map(self._update_colrev_pdf_ids, records.values())
        pool.close()
        pool.join()
        records = {r[Fields.ID]: r for r in records_list}
        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(msg="Update colrev_pdf_ids")

    def _print_stats(self, *, pdf_prep_record_list: list) -> None:
        self.pdf_prepared = len(
            [
                r
                for r in pdf_prep_record_list
                if RecordState.pdf_prepared == r[Fields.STATUS]
            ]
        )

        self.not_prepared = self.to_prepare - self.pdf_prepared

        if not self.review_manager.high_level_operation:
            print()
        prepared_string = "Overall pdf_prepared".ljust(37)
        if self.pdf_prepared == 0:
            prepared_string += f"{self.pdf_prepared}".rjust(3, " ")
            prepared_string += " PDFs"
        elif self.pdf_prepared == 1:
            prepared_string += f"{Colors.GREEN}"
            prepared_string += f"{self.pdf_prepared}".rjust(3, " ")
            prepared_string += f"{Colors.END} PDF"
        else:
            prepared_string += f"{Colors.GREEN}"
            prepared_string += f"{self.pdf_prepared}".rjust(3, " ")
            prepared_string += f"{Colors.END} PDFs"

        not_prepared_string = "Overall pdf_needs_manual_preparation".ljust(37)
        if self.not_prepared == 0:
            not_prepared_string += f"{self.not_prepared}".rjust(3, " ")
            not_prepared_string += " PDFs"
        elif self.not_prepared == 1:
            not_prepared_string += f"{Colors.ORANGE}"
            not_prepared_string += f"{self.not_prepared}".rjust(3, " ")
            not_prepared_string += f"{Colors.END} PDF"
        else:
            not_prepared_string += f"{Colors.ORANGE}"
            not_prepared_string += f"{self.not_prepared}".rjust(3, " ")
            not_prepared_string += f"{Colors.END} PDFs"

        self.review_manager.logger.info(prepared_string)
        self.review_manager.logger.info(not_prepared_string)

    def setup_custom_script(self) -> None:
        """Setup a custom pdf-prep script"""

        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.ops",
            filename=Path("custom_scripts/custom_pdf_prep_script.py"),
        )

        if filedata:
            with open("custom_pdf_prep_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(Path("custom_pdf_prep_script.py"))

        self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints.append(
            {"endpoint": "custom_pdf_prep_script"}
        )

        self.review_manager.save_settings()

    def generate_tei(self) -> None:
        """Generate TEI documents for included records"""

        self.review_manager.logger.info("Generate TEI documents")
        endpoint = colrev.packages.grobid_tei.src.grobid_tei.GROBIDTEI(
            pdf_prep_operation=self, settings={"endpoint": "colrev.grobid_tei"}
        )
        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if record_dict[Fields.STATUS] not in [
                RecordState.rev_included,
                RecordState.rev_synthesized,
            ]:
                continue
            self.review_manager.logger.info(record_dict[Fields.ID])
            try:
                endpoint.prep_pdf(
                    record=colrev.record.record_pdf.PDFRecord(record_dict),
                    pad=0,
                )
            except colrev_exceptions.TEIException:
                self.review_manager.logger.error("Error generating TEI")

    @colrev.process.operation.Operation.decorate()
    def main(
        self,
        *,
        reprocess: bool = False,
        batch_size: int = 0,
    ) -> None:
        """Prepare PDFs (main entrypoint)"""

        if (
            self.review_manager.in_ci_environment()
            and not self.review_manager.in_test_environment()
        ):
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev pdf-prep",
                detailed_trace="pdf-prep not available in ci environment",
            )

        self.review_manager.logger.info("Prep PDFs")
        self.review_manager.logger.info(
            "Prepare PDFs, validating them against their metadata, "
            "removing additional pages, ensuring machine readability."
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_prep.html"
        )

        self.review_manager.logger.info(
            "INFO: This operation is computationally intensive and may take longer."
        )
        if not self.review_manager.high_level_operation:
            print()

        if reprocess:
            self._set_to_reprocess()

        pdf_prep_data = self._get_data(batch_size=batch_size)

        package_manager = self.review_manager.get_package_manager()
        self.pdf_prep_package_endpoints = {}
        for (
            pdf_prep_package_endpoint
        ) in self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints:

            pdf_prep_class = package_manager.get_package_endpoint_class(
                package_type=EndpointType.pdf_prep,
                package_identifier=pdf_prep_package_endpoint["endpoint"],
            )
            self.pdf_prep_package_endpoints[pdf_prep_package_endpoint["endpoint"]] = (
                pdf_prep_class(
                    pdf_prep_operation=self, settings=pdf_prep_package_endpoint
                )
            )

        self.review_manager.logger.info(
            "PDFs to prep".ljust(38) + f'{pdf_prep_data["nr_tasks"]} PDFs'
        )

        if self.review_manager.verbose_mode:
            for item in pdf_prep_data["items"]:
                record = item["record"]
                record = self.prepare_pdf(item)
                self.review_manager.dataset.save_records_dict(
                    {record[Fields.ID]: record}, partial=True
                )

        else:
            endpoint_names = [
                s["endpoint"]
                for s in self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints
            ]
            if "colrev.grobid_tei" in endpoint_names:  # type: ignore
                pool = Pool(mp.cpu_count() // 2)
            else:
                pool = Pool(self.cpus)
            pdf_prep_record_list = pool.map(self.prepare_pdf, pdf_prep_data["items"])
            pool.close()
            pool.join()

            self.review_manager.dataset.save_records_dict(
                {r[Fields.ID]: r for r in pdf_prep_record_list}, partial=True
            )

            self._print_stats(pdf_prep_record_list=pdf_prep_record_list)

        # Note: for formatting...
        records = self.review_manager.dataset.load_records_dict()
        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(msg="Prepare PDFs")
        self.review_manager.logger.info(
            f"{Colors.GREEN}Completed pdf-prep operation{Colors.END}"
        )
