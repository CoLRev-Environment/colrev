#! /usr/bin/env python
"""CoLRev pdf_prep operation: Prepare PDF documents."""
from __future__ import annotations

import logging
import multiprocessing as mp
import os
import subprocess
from multiprocessing.pool import ThreadPool as Pool
from pathlib import Path

import requests
import timeout_decorator

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.ops.built_in.pdf_prep.tei_prep
import colrev.record
import colrev.ui_cli.cli_colors as colors


class PDFPrep(colrev.operation.Operation):
    """Prepare PDFs"""

    to_prepare: int
    pdf_prepared: int
    not_prepared: int

    pdf_prep_package_endpoints: dict

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        reprocess: bool = False,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.pdf_prep,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        self.reprocess = reprocess

        self.cpus = 4

    def __complete_successful_pdf_prep(
        self, *, record: colrev.record.Record, original_filename: str
    ) -> None:
        record.data.update(colrev_status=colrev.record.RecordState.pdf_prepared)
        pdf_path = self.review_manager.path / Path(record.data["file"])
        if pdf_path.suffix == ".pdf":
            try:
                record.data.update(
                    colrev_pdf_id=record.get_colrev_pdf_id(pdf_path=pdf_path)
                )
            except colrev_exceptions.ServiceNotAvailableException:
                self.review_manager.logger.error(
                    "Cannot create pdf-hash (Docker service not available)"
                )

        # colrev_status == pdf_imported : means successful
        # create *_backup.pdf if record["file"] was changed
        if original_filename != record.data["file"]:
            current_file = self.review_manager.path / Path(record.data["file"])
            original_file = self.review_manager.path / Path(original_filename)
            if current_file.is_file() and original_file.is_file():
                backup_filename = self.review_manager.path / Path(
                    original_filename.replace(".pdf", "_backup.pdf")
                )
                original_file.rename(backup_filename)
                current_file.rename(original_filename)
                record.data["file"] = str(
                    original_file.relative_to(self.review_manager.path)
                )

        # Backup:
        # Create a copy of the original PDF if users cannot
        # restore it from git
        # linked_file.rename(str(linked_file).replace(".pdf", "_backup.pdf"))

        if not self.review_manager.settings.pdf_prep.keep_backup_of_pdfs:
            # Remove temporary PDFs when processing has succeeded
            target_fname = self.review_manager.path / Path(f'{record.data["ID"]}.pdf')
            linked_file = self.review_manager.path / Path(record.data["file"])

            if target_fname.name != linked_file.name:
                if target_fname.is_file():
                    os.remove(target_fname)
                linked_file.rename(target_fname)
                record.data["file"] = str(
                    target_fname.relative_to(self.review_manager.path)
                )

            if not self.review_manager.verbose_mode:
                # Delete temporary PDFs for which processing has failed:
                if target_fname.is_file():
                    for fpath in self.review_manager.pdf_dir.glob("*.pdf"):
                        if record.data["ID"] in str(fpath) and fpath != target_fname:
                            os.remove(fpath)

    # Note : no named arguments (multiprocessing)
    def prepare_pdf(self, item: dict) -> dict:
        """Prepare a PDF (based on package_endpoints in the settings)"""

        record_dict = item["record"]

        if (
            colrev.record.RecordState.pdf_imported != record_dict["colrev_status"]
            or "file" not in record_dict
        ):
            return record_dict

        pad = 50

        pdf_path = self.review_manager.path / Path(record_dict["file"])
        if not Path(pdf_path).is_file():
            self.review_manager.logger.error(
                f'{record_dict["ID"]}'.ljust(46, " ") + "Linked file/pdf does not exist"
            )
            return record_dict

        record = colrev.record.Record(data=record_dict)
        if record_dict["file"].endswith(".pdf"):
            record.set_text_from_pdf(project_path=self.review_manager.path)
        original_filename = record_dict["file"]

        self.review_manager.logger.debug(f'Start PDF prep of {record_dict["ID"]}')
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

                self.review_manager.logger.debug(
                    f'{endpoint.settings.endpoint}({record.data["ID"]}):'.ljust(  # type: ignore
                        50, " "
                    )
                    + "called"
                )

                record.data = endpoint.prep_pdf(self, record, pad)  # type: ignore
            except colrev_exceptions.PDFHashError:
                record.add_data_provenance_note(key="file", note="pdf-hash-error")

            except (
                subprocess.CalledProcessError,
                timeout_decorator.timeout_decorator.TimeoutError,
                colrev_exceptions.InvalidPDFException,
                colrev_exceptions.TEIException,
                requests.exceptions.ReadTimeout,
            ) as err:
                self.review_manager.logger.error(
                    f'Error for {record.data["ID"]} '  # type: ignore
                    f"(in {endpoint.settings.endpoint} : {err})"  # type: ignore
                )
                record.set_status(
                    target_state=colrev.record.RecordState.pdf_needs_manual_preparation
                )

            failed = (
                colrev.record.RecordState.pdf_needs_manual_preparation
                == record.data["colrev_status"]
            )

            if failed:
                msg_str = f"{endpoint.settings.endpoint}"  # type: ignore
                msg_str = msg_str.replace("colrev.", "")
                detailed_msgs.append(f"{colors.ORANGE}{msg_str}{colors.END}")

            if failed:
                break

        # Each pdf_prep_package_endpoint can create a new file
        # previous/temporary pdfs are deleted when the process is successful
        # The original PDF is never deleted automatically.
        # If successful, it is renamed to *_backup.pdf

        self.review_manager.logger.debug(f'Completed PDF prep of {record_dict["ID"]}')

        successfully_prepared = (
            colrev.record.RecordState.pdf_imported == record.data["colrev_status"]
        )

        if successfully_prepared:
            self.review_manager.logger.info(
                f" {colors.GREEN}{record_dict['ID']}".ljust(46)
                + f"pdf_imported → pdf_prepared{colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f" {colors.ORANGE}{record_dict['ID']} ".ljust(46)
                + f"pdf_imported → pdf_needs_manual_preparation {colors.END}"
                f"({', '.join(detailed_msgs)})"
            )

        if successfully_prepared:
            self.__complete_successful_pdf_prep(
                record=record, original_filename=original_filename
            )

        record.cleanup_pdf_processing_fields()

        return record.get_data()

    def __get_data(self, *, batch_size: int) -> dict:
        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())
        nr_tasks = len(
            [
                x
                for x in record_header_list
                if colrev.record.RecordState.pdf_imported == x["colrev_status"]
            ]
        )

        items = self.review_manager.dataset.read_next_record(
            conditions=[{"colrev_status": colrev.record.RecordState.pdf_imported}],
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

    def __set_to_reprocess(self) -> None:
        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if (
                colrev.record.RecordState.pdf_needs_manual_preparation
                != record_dict["colrev_stauts"]
            ):
                continue

            record = colrev.record.Record(data=record_dict)
            record.data.update(colrev_status=colrev.record.RecordState.pdf_imported)
            record.reset_pdf_provenance_notes()

        self.review_manager.dataset.save_records_dict(records=records)

    # Note : no named arguments (multiprocessing)
    def __update_colrev_pdf_ids(self, record_dict: dict) -> dict:
        if "file" in record_dict:
            pdf_path = self.review_manager.path / Path(record_dict["file"])
            record_dict.update(
                colrev_pdf_id=colrev.record.Record.get_colrev_pdf_id(pdf_path=pdf_path)
            )
        return record_dict

    def update_colrev_pdf_ids(self) -> None:
        """Update the colrev-pdf-ids"""
        self.review_manager.logger.info("Update colrev_pdf_ids")
        records = self.review_manager.dataset.load_records_dict()
        pool = Pool(self.cpus)
        records_list = pool.map(self.__update_colrev_pdf_ids, records.values())
        pool.close()
        pool.join()
        records = {r["ID"]: r for r in records_list}
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(msg="Update colrev_pdf_ids")

    def _print_stats(self, *, pdf_prep_record_list: list) -> None:
        self.pdf_prepared = len(
            [
                r
                for r in pdf_prep_record_list
                if colrev.record.RecordState.pdf_prepared == r["colrev_status"]
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
            prepared_string += f"{colors.GREEN}"
            prepared_string += f"{self.pdf_prepared}".rjust(3, " ")
            prepared_string += f"{colors.END} PDF"
        else:
            prepared_string += f"{colors.GREEN}"
            prepared_string += f"{self.pdf_prepared}".rjust(3, " ")
            prepared_string += f"{colors.END} PDFs"

        not_prepared_string = "Overall pdf_needs_manual_preparation".ljust(37)
        if self.not_prepared == 0:
            not_prepared_string += f"{self.not_prepared}".rjust(3, " ")
            not_prepared_string += " PDFs"
        elif self.not_prepared == 1:
            not_prepared_string += f"{colors.ORANGE}"
            not_prepared_string += f"{self.not_prepared}".rjust(3, " ")
            not_prepared_string += f"{colors.END} PDF"
        else:
            not_prepared_string += f"{colors.ORANGE}"
            not_prepared_string += f"{self.not_prepared}".rjust(3, " ")
            not_prepared_string += f"{colors.END} PDFs"

        self.review_manager.logger.info(prepared_string)
        self.review_manager.logger.info(not_prepared_string)

    def setup_custom_script(self) -> None:
        """Setup a custom pdf-prep script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_scripts/custom_pdf_prep_script.py")
        )

        if filedata:
            with open("custom_pdf_prep_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_pdf_prep_script.py"))

        self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints.append(
            {"endpoint": "custom_pdf_prep_script"}
        )

        self.review_manager.save_settings()

    def generate_tei(self) -> None:
        """Generate TEI documents for included records"""

        self.review_manager.logger.info("Generate TEI documents")
        endpoint = colrev.ops.built_in.pdf_prep.tei_prep.TEIPDFPrep(
            pdf_prep_operation=self, settings={"endpoint": "colrev.create_tei"}
        )
        records = self.review_manager.dataset.load_records_dict()
        for record_dict in records.values():
            if record_dict["colrev_status"] not in [
                colrev.record.RecordState.rev_included,
                colrev.record.RecordState.rev_synthesized,
            ]:
                continue
            self.review_manager.logger.info(record_dict["ID"])
            try:
                endpoint.prep_pdf(
                    pdf_prep_operation=self,
                    record=colrev.record.Record(data=record_dict),
                    pad=0,
                )
            except colrev_exceptions.TEIException:
                self.review_manager.logger.error("Eror generating TEI")

    def main(
        self,
        *,
        reprocess: bool = False,
        batch_size: int,
    ) -> None:
        """Prepare PDFs (main entrypoint)"""

        if self.review_manager.in_ci_environment():
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

        # temporary fix: remove all lines containing PDFType1Font from log.
        # https://github.com/pdfminer/pdfminer.six/issues/282

        self.review_manager.logger.info(
            "INFO: This operation is computationally intensive and may take longer."
        )
        if not self.review_manager.high_level_operation:
            print()

        if reprocess:
            self.__set_to_reprocess()

        pdf_prep_data = self.__get_data(batch_size=batch_size)

        package_manager = self.review_manager.get_package_manager()
        self.pdf_prep_package_endpoints = package_manager.load_packages(
            package_type=colrev.env.package_manager.PackageEndpointType.pdf_prep,
            selected_packages=self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints,
            operation=self,
            only_ci_supported=self.review_manager.in_ci_environment(),
        )

        self.review_manager.logger.info(
            "PDFs to prep".ljust(38) + f'{pdf_prep_data["nr_tasks"]} PDFs'
        )

        if self.review_manager.verbose_mode:
            for item in pdf_prep_data["items"]:
                record = item["record"]
                record = self.prepare_pdf(item)
                self.review_manager.dataset.save_records_dict(
                    records={record["ID"]: record}, partial=True
                )

        else:
            endpoint_names = [
                s["endpoint"]
                for s in self.review_manager.settings.pdf_prep.pdf_prep_package_endpoints
            ]
            if "colrev.create_tei" in endpoint_names:  # type: ignore
                pool = Pool(mp.cpu_count() // 2)
            else:
                pool = Pool(self.cpus)
            pdf_prep_record_list = pool.map(self.prepare_pdf, pdf_prep_data["items"])
            pool.close()
            pool.join()

            self.review_manager.dataset.save_records_dict(
                records={r["ID"]: r for r in pdf_prep_record_list}, partial=True
            )

            self._print_stats(pdf_prep_record_list=pdf_prep_record_list)

        # Note: for formatting...
        records = self.review_manager.dataset.load_records_dict()
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

        self.review_manager.create_commit(msg="Prepare PDFs")
        self.review_manager.logger.info(
            f"{colors.GREEN}Completed pdf-prep operation{colors.END}"
        )


if __name__ == "__main__":
    pass
