#! /usr/bin/env python
from __future__ import annotations

import logging
import os
import pkgutil
import subprocess
import typing
from pathlib import Path
from typing import TYPE_CHECKING

import timeout_decorator
from p_tqdm import p_map

import colrev.built_in.pdf_prep as built_in_pdf_prep
import colrev.cli_colors as colors
import colrev.process
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class PDFPrep(colrev.process.Process):

    to_prepare: int
    pdf_prepared: int
    not_prepared: int

    built_in_scripts: dict[str, dict[str, typing.Any]] = {
        "pdf_check_ocr": {
            "endpoint": built_in_pdf_prep.PDFCheckOCREndpoint,
        },
        "remove_coverpage": {
            "endpoint": built_in_pdf_prep.PDFCoverPageEndpoint,
        },
        "remove_last_page": {
            "endpoint": built_in_pdf_prep.PDFLastPageEndpoint,
        },
        "validate_pdf_metadata": {
            "endpoint": built_in_pdf_prep.PDFMetadataValidationEndpoint,
        },
        "validate_completeness": {
            "endpoint": built_in_pdf_prep.PDFCompletenessValidationEndpoint,
        },
        "create_tei": {
            "endpoint": built_in_pdf_prep.TEIEndpoint,
        },
    }

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        reprocess: bool = False,
        notify_state_transition_operation: bool = True,
        debug: bool = False,
    ) -> None:

        super().__init__(
            review_manager=review_manager,
            process_type=colrev.process.ProcessType.pdf_prep,
            notify_state_transition_operation=notify_state_transition_operation,
            debug=debug,
        )

        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        self.reprocess = reprocess
        self.verbose = False

        self.cpus = 8

        adapter_manager = self.review_manager.get_adapter_manager()
        self.pdf_prep_scripts: dict[str, typing.Any] = adapter_manager.load_scripts(
            process=self,
            scripts=review_manager.settings.pdf_prep.scripts,
        )

    # Note : no named arguments (multiprocessing)
    def prepare_pdf(self, item: dict) -> dict:
        record_dict = item["record"]

        if (
            colrev.record.RecordState.pdf_imported != record_dict["colrev_status"]
            or "file" not in record_dict
        ):
            return record_dict

        pad = len(record_dict["ID"]) + 35

        pdf_path = self.review_manager.path / Path(record_dict["file"])
        if not Path(pdf_path).is_file():
            msg = (
                f'{record_dict["ID"]}'.ljust(pad, " ")
                + "Linked file/pdf does not exist"
            )
            self.review_manager.report_logger.error(msg)
            self.review_manager.logger.error(msg)
            return record_dict

        # RECORD.data.update(colrev_status=RecordState.pdf_prepared)
        record = colrev.record.Record(data=record_dict)
        record.set_text_from_pdf(project_path=self.review_manager.path)
        original_filename = record_dict["file"]

        self.review_manager.report_logger.info(f'prepare({record.data["ID"]})')
        # Note: if there are problems
        # colrev_status is set to pdf_needs_manual_preparation
        # if it remains 'imported', all preparation checks have passed
        for pdf_prep_script in self.review_manager.settings.pdf_prep.scripts:

            try:
                endpoint = self.pdf_prep_scripts[pdf_prep_script["endpoint"]]
                self.review_manager.logger.debug(
                    f"{endpoint.settings.name}(...) called"
                )

                self.review_manager.report_logger.info(
                    f'{endpoint.settings.name}({record.data["ID"]}) called'
                )

                record.data = endpoint.prep_pdf(self, record, pad)
                # Note : the record should not be changed
                # if the prep_script throws an exception
                # prepped_record = prep_script["script"](*prep_script["params"])
                # if isinstance(prepped_record, dict):
                #     record = prepped_record
                # else:
                #     record["colrev_status"] = RecordState.pdf_needs_manual_preparation
            except (
                subprocess.CalledProcessError,
                timeout_decorator.timeout_decorator.TimeoutError,
            ) as err:
                self.review_manager.logger.error(
                    f'Error for {record.data["ID"]} '
                    f"(in {endpoint.settings.name} : {err})"
                )
                record.data[
                    "colrev_status"
                ] = colrev.record.RecordState.pdf_needs_manual_preparation

            except Exception as exc:  # pylint: disable=broad-except
                print(exc)
                record.data[
                    "colrev_status"
                ] = colrev.record.RecordState.pdf_needs_manual_preparation
                record.add_data_provenance_note(key="file", note=str(exc))
            failed = (
                colrev.record.RecordState.pdf_needs_manual_preparation
                == record.data["colrev_status"]
            )
            msg = (
                f'{endpoint.settings.name}({record.data["ID"]}):'.ljust(pad, " ") + " "
            )
            msg += "fail" if failed else "pass"
            self.review_manager.report_logger.info(msg)
            if failed:
                break

        # Each prep_scripts can create a new file
        # previous/temporary pdfs are deleted when the process is successful
        # The original PDF is never deleted automatically.
        # If successful, it is renamed to *_backup.pdf

        if colrev.record.RecordState.pdf_imported == record.data["colrev_status"]:
            record.data.update(colrev_status=colrev.record.RecordState.pdf_prepared)
            pdf_path = self.review_manager.path / Path(record.data["file"])
            record.data.update(
                colrev_pdf_id=record.get_colrev_pdf_id(
                    review_manager=self.review_manager, pdf_path=pdf_path
                )
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
                    bfp = backup_filename.relative_to(self.review_manager.path)
                    self.review_manager.report_logger.info(
                        f"created backup after successful pdf-prep: {bfp}"
                    )

        # Backup:
        # Create a copy of the original PDF if users cannot
        # restore it from git
        # linked_file.rename(str(linked_file).replace(".pdf", "_backup.pdf"))

        rm_temp_if_successful = False
        if rm_temp_if_successful:
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

            if not self.review_manager.debug_mode:
                # Delete temporary PDFs for which processing has failed:
                if target_fname.is_file():
                    for fpath in self.review_manager.pdf_directory.glob("*.pdf"):
                        if record.data["ID"] in str(fpath) and fpath != target_fname:
                            os.remove(fpath)

            # TODO : REVIEW_MANAGER not part of item!?
            git_repo = item["REVIEW_MANAGER"].get_repo()
            git_repo.index.add([record.data["file"]])

        record.cleanup_pdf_processing_fields()

        return record.get_data()

    def __get_data(self) -> dict:

        record_state_list = self.review_manager.dataset.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(colrev.record.RecordState.pdf_imported) == x["colrev_status"]
            ]
        )

        items = self.review_manager.dataset.read_next_record(
            conditions=[{"colrev_status": colrev.record.RecordState.pdf_imported}],
        )
        self.to_prepare = nr_tasks

        prep_data = {
            "nr_tasks": nr_tasks,
            "items": [{"record": item} for item in items],
        }
        self.review_manager.logger.debug(
            self.review_manager.p_printer.pformat(prep_data)
        )
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

    def __update_colrev_pdf_ids(self, *, record_dict: dict) -> dict:
        if "file" in record_dict:
            pdf_path = self.review_manager.path / Path(record_dict["file"])
            record_dict.update(
                colrev_pdf_id=colrev.record.Record(data=record_dict).get_colrev_pdf_id(
                    review_manager=self.review_manager, pdf_path=pdf_path
                )
            )
        return record_dict

    def update_colrev_pdf_ids(self) -> None:
        self.review_manager.logger.info("Update colrev_pdf_ids")
        records = self.review_manager.dataset.load_records_dict()
        records_list = p_map(self.__update_colrev_pdf_ids, records.values())
        records = {r["ID"]: r for r in records_list}
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(
            msg="Update colrev_pdf_ids", script_call="colrev pdf-prep"
        )

    def _print_stats(self, *, pdf_prep_record_list: list) -> None:

        self.pdf_prepared = len(
            [
                r
                for r in pdf_prep_record_list
                if colrev.record.RecordState.pdf_prepared == r["colrev_status"]
            ]
        )

        self.not_prepared = self.to_prepare - self.pdf_prepared

        prepared_string = "Prepared:    "
        if self.pdf_prepared == 0:
            prepared_string += f"{self.pdf_prepared}".rjust(11, " ")
            prepared_string += " PDFs"
        elif self.pdf_prepared == 1:
            prepared_string += f"{colors.GREEN}"
            prepared_string += f"{self.pdf_prepared}".rjust(10, " ")
            prepared_string += f"{colors.END} PDF"
        else:
            prepared_string += f"{colors.GREEN}"
            prepared_string += f"{self.pdf_prepared}".rjust(11, " ")
            prepared_string += f"{colors.END} PDFs"

        not_prepared_string = "Not prepared:"
        if self.not_prepared == 0:
            not_prepared_string += f"{self.not_prepared}".rjust(11, " ")
            not_prepared_string += " PDFs"
        elif self.not_prepared == 1:
            not_prepared_string += f"{colors.ORANGE}"
            not_prepared_string += f"{self.not_prepared}".rjust(10, " ")
            not_prepared_string += f"{colors.END} PDF"
        else:
            not_prepared_string += f"{colors.ORANGE}"
            not_prepared_string += f"{self.not_prepared}".rjust(11, " ")
            not_prepared_string += f"{colors.END} PDFs"

        self.review_manager.logger.info(prepared_string)
        self.review_manager.logger.info(not_prepared_string)

    def setup_custom_script(self) -> None:

        filedata = pkgutil.get_data(__name__, "template/custom_pdf_prep_script.py")
        if filedata:
            with open("custom_pdf_prep_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_pdf_prep_script.py"))

        self.review_manager.settings.pdf_prep.scripts.append(
            {"endpoint": "custom_pdf_prep_script"}
        )

        self.review_manager.save_settings()

    def main(
        self,
        *,
        reprocess: bool = False,
    ) -> None:

        saved_args = locals()

        # temporary fix: remove all lines containing PDFType1Font from log.
        # https://github.com/pdfminer/pdfminer.six/issues/282

        self.review_manager.logger.info("Prepare PDFs")

        if reprocess:
            self.__set_to_reprocess()

        pdf_prep_data = self.__get_data()

        if self.review_manager.debug_mode:
            for item in pdf_prep_data["items"]:
                record = item["record"]
                print(record["ID"])
                record = self.prepare_pdf(item)
                self.review_manager.p_printer.pprint(record)
                self.review_manager.dataset.save_record_list_by_id(record_list=[record])
        else:
            pdf_prep_record_list = p_map(self.prepare_pdf, pdf_prep_data["items"])
            self.review_manager.dataset.save_record_list_by_id(
                record_list=pdf_prep_record_list
            )

            # Multiprocessing mixes logs of different records.
            # For better readability:
            self.review_manager.reorder_log(ids=[x["ID"] for x in pdf_prep_record_list])

        self._print_stats(pdf_prep_record_list=pdf_prep_record_list)

        # Note: for formatting...
        records = self.review_manager.dataset.load_records_dict()
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

        self.review_manager.create_commit(
            msg="Prepare PDFs", script_call="colrev pdf-prep", saved_args=saved_args
        )


if __name__ == "__main__":
    pass
