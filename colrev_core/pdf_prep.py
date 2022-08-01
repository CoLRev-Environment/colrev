#! /usr/bin/env python
import logging
import os
import subprocess
import typing
from pathlib import Path

import timeout_decorator
from p_tqdm import p_map

from colrev_core.environment import AdapterManager
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


class PDF_Preparation(Process):

    from colrev_core.built_in import pdf_prep as built_in_pdf_prep

    built_in_scripts: typing.Dict[str, typing.Dict[str, typing.Any]] = {
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
    }

    def __init__(
        self,
        *,
        REVIEW_MANAGER,
        reprocess: bool = False,
        notify_state_transition_process: bool = True,
        debug: bool = False,
    ):

        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            type=ProcessType.pdf_prep,
            notify_state_transition_process=notify_state_transition_process,
            debug=debug,
        )

        logging.getLogger("pdfminer").setLevel(logging.ERROR)

        self.reprocess = reprocess
        self.verbose = False

        self.PDF_DIRECTORY = self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
        self.REPO_DIR = self.REVIEW_MANAGER.paths["REPO_DIR"]
        self.CPUS = 8

        self.pdf_prep_scripts: typing.Dict[
            str, typing.Any
        ] = AdapterManager.load_scripts(
            PROCESS=self,
            scripts=REVIEW_MANAGER.settings.pdf_prep.scripts,
        )

    def __cleanup_pdf_processing_fields(self, *, record: dict) -> dict:

        if "text_from_pdf" in record:
            del record["text_from_pdf"]
        if "pages_in_file" in record:
            del record["pages_in_file"]

        return record

    # Note : no named arguments (multiprocessing)
    def prepare_pdf(self, item: dict) -> dict:
        record = item["record"]

        if RecordState.pdf_imported != record["colrev_status"] or "file" not in record:
            return record

        PAD = len(record["ID"]) + 35

        pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
        if not Path(pdf_path).is_file():
            msg = f'{record["ID"]}'.ljust(PAD, " ") + "Linked file/pdf does not exist"
            self.REVIEW_MANAGER.report_logger.error(msg)
            self.REVIEW_MANAGER.logger.error(msg)
            return record

        # RECORD.data.update(colrev_status=RecordState.pdf_prepared)
        RECORD = Record(data=record)
        RECORD.get_text_from_pdf(project_path=self.REVIEW_MANAGER.path)
        original_filename = record["file"]

        self.REVIEW_MANAGER.report_logger.info(f'prepare({RECORD.data["ID"]})')
        # Note: if there are problems
        # colrev_status is set to pdf_needs_manual_preparation
        # if it remains 'imported', all preparation checks have passed
        for PDF_PREP_SCRIPT in self.REVIEW_MANAGER.settings.pdf_prep.scripts:

            try:
                ENDPOINT = self.pdf_prep_scripts[PDF_PREP_SCRIPT["endpoint"]]
                self.REVIEW_MANAGER.logger.debug(
                    f"{ENDPOINT.SETTINGS.name}(...) called"
                )

                self.REVIEW_MANAGER.report_logger.info(
                    f'{ENDPOINT.SETTINGS.name}({RECORD.data["ID"]}) called'
                )

                RECORD.data = ENDPOINT.prep_pdf(self, RECORD, PAD)
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
                self.REVIEW_MANAGER.logger.error(
                    f'Error for {RECORD.data["ID"]} '
                    f"(in {ENDPOINT.SETTINGS.name} : {err})"
                )
                pass
                RECORD.data["colrev_status"] = RecordState.pdf_needs_manual_preparation

            except Exception as e:
                print(e)
                RECORD.data["colrev_status"] = RecordState.pdf_needs_manual_preparation
            failed = (
                RecordState.pdf_needs_manual_preparation == RECORD.data["colrev_status"]
            )
            msg = (
                f'{ENDPOINT.SETTINGS.name}({RECORD.data["ID"]}):'.ljust(PAD, " ") + " "
            )
            msg += "fail" if failed else "pass"
            self.REVIEW_MANAGER.report_logger.info(msg)
            if failed:
                break

        # Each prep_scripts can create a new file
        # previous/temporary pdfs are deleted when the process is successful
        # The original PDF is never deleted automatically.
        # If successful, it is renamed to *_backup.pdf

        if RecordState.pdf_imported == RECORD.data["colrev_status"]:
            RECORD.data.update(colrev_status=RecordState.pdf_prepared)
            pdf_path = self.REVIEW_MANAGER.path / Path(RECORD.data["file"])
            RECORD.data.update(colrev_pdf_id=RECORD.get_colrev_pdf_id(path=pdf_path))

            # colrev_status == pdf_imported : means successful
            # create *_backup.pdf if record["file"] was changed
            if original_filename != RECORD.data["file"]:

                current_file = self.REVIEW_MANAGER.path / Path(RECORD.data["file"])
                original_file = self.REVIEW_MANAGER.path / Path(original_filename)
                if current_file.is_file() and original_file.is_file():
                    backup_filename = self.REVIEW_MANAGER.path / Path(
                        original_filename.replace(".pdf", "_backup.pdf")
                    )
                    original_file.rename(backup_filename)
                    current_file.rename(original_filename)
                    RECORD.data["file"] = str(
                        original_file.relative_to(self.REVIEW_MANAGER.path)
                    )
                    bfp = backup_filename.relative_to(self.REVIEW_MANAGER.path)
                    self.REVIEW_MANAGER.report_logger.info(
                        f"created backup after successful pdf-prep: {bfp}"
                    )

        # Backup:
        # Create a copy of the original PDF if users cannot
        # restore it from git
        # linked_file.rename(str(linked_file).replace(".pdf", "_backup.pdf"))

        rm_temp_if_successful = False
        if rm_temp_if_successful:
            # Remove temporary PDFs when processing has succeeded
            target_fname = self.REVIEW_MANAGER.path / Path(f'{RECORD.data["ID"]}.pdf')
            linked_file = self.REVIEW_MANAGER.path / Path(RECORD.data["file"])

            if target_fname.name != linked_file.name:
                if target_fname.is_file():
                    os.remove(target_fname)
                linked_file.rename(target_fname)
                RECORD.data["file"] = str(
                    target_fname.relative_to(self.REVIEW_MANAGER.path)
                )

            if not self.REVIEW_MANAGER.DEBUG_MODE:
                # Delete temporary PDFs for which processing has failed:
                if target_fname.is_file():
                    for fpath in self.PDF_DIRECTORY.glob("*.pdf"):
                        if RECORD.data["ID"] in str(fpath) and fpath != target_fname:
                            os.remove(fpath)

            git_repo = item["REVIEW_MANAGER"].get_repo()
            git_repo.index.add([RECORD.data["file"]])

        RECORD.data = self.__cleanup_pdf_processing_fields(record=RECORD.data)

        return RECORD.get_data()

    def __get_data(self) -> dict:

        record_state_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        nr_tasks = len(
            [
                x
                for x in record_state_list
                if str(RecordState.pdf_imported) == x["colrev_status"]
            ]
        )

        items = self.REVIEW_MANAGER.REVIEW_DATASET.read_next_record(
            conditions=[{"colrev_status": RecordState.pdf_imported}],
        )
        self.to_prepare = nr_tasks

        prep_data = {
            "nr_tasks": nr_tasks,
            "items": [{"record": item} for item in items],
        }
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prep_data))
        return prep_data

    def __set_to_reprocess(self):

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for record in records.values():
            if RecordState.pdf_needs_manual_preparation != record["colrev_stauts"]:
                continue

            RECORD = Record(record)
            RECORD.data.update(colrev_status=RecordState.pdf_imported)
            RECORD.reset_pdf_provenance_notes()
            record = RECORD.get_data()

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        return

    def __update_colrev_pdf_ids(self, *, record: dict) -> dict:
        if "file" in record:
            pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
            record.update(
                colrev_pdf_id=Record(data=record).get_colrev_pdf_id(path=pdf_path)
            )
        return record

    def update_colrev_pdf_ids(self) -> None:
        self.REVIEW_MANAGER.logger.info("Update colrev_pdf_ids")
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records_list = p_map(self.__update_colrev_pdf_ids, records.values())
        records = {r["ID"]: r for r in records_list}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(
            msg="Update colrev_pdf_ids", script_call="colrev pdf-prep"
        )
        return

    def _print_stats(self, *, pdf_prep_record_list) -> None:

        self.pdf_prepared = len(
            [
                r
                for r in pdf_prep_record_list
                if RecordState.pdf_prepared == r["colrev_status"]
            ]
        )

        self.not_prepared = self.to_prepare - self.pdf_prepared

        prepared_string = "Prepared:    "
        if self.pdf_prepared == 0:
            prepared_string += f"{self.pdf_prepared}".rjust(11, " ")
            prepared_string += " PDFs"
        elif self.pdf_prepared == 1:
            prepared_string += "\033[92m"
            prepared_string += f"{self.pdf_prepared}".rjust(10, " ")
            prepared_string += "\033[0m PDF"
        else:
            prepared_string += "\033[92m"
            prepared_string += f"{self.pdf_prepared}".rjust(11, " ")
            prepared_string += "\033[0m PDFs"

        not_prepared_string = "Not prepared:"
        if self.not_prepared == 0:
            not_prepared_string += f"{self.not_prepared}".rjust(11, " ")
            not_prepared_string += " PDFs"
        elif self.not_prepared == 1:
            not_prepared_string += "\033[93m"
            not_prepared_string += f"{self.not_prepared}".rjust(10, " ")
            not_prepared_string += "\033[0m PDF"
        else:
            not_prepared_string += "\033[93m"
            not_prepared_string += f"{self.not_prepared}".rjust(11, " ")
            not_prepared_string += "\033[0m PDFs"

        self.REVIEW_MANAGER.logger.info(prepared_string)
        self.REVIEW_MANAGER.logger.info(not_prepared_string)

        return

    def setup_custom_script(self) -> None:
        import pkgutil

        filedata = pkgutil.get_data(__name__, "template/custom_pdf_prep_script.py")
        if filedata:
            with open("custom_pdf_prep_script.py", "w") as file:
                file.write(filedata.decode("utf-8"))

        self.REVIEW_MANAGER.REVIEW_DATASET.add_changes(path="custom_pdf_prep_script.py")

        self.REVIEW_MANAGER.settings.pdf_prep.scripts.append(
            {"endpoint": "custom_pdf_prep_script"}
        )

        self.REVIEW_MANAGER.save_settings()

        return

    def main(
        self,
        *,
        reprocess: bool = False,
    ) -> None:

        saved_args = locals()

        # temporary fix: remove all lines containing PDFType1Font from log.
        # https://github.com/pdfminer/pdfminer.six/issues/282

        self.REVIEW_MANAGER.logger.info("Prepare PDFs")

        if reprocess:
            self.__set_to_reprocess()

        pdf_prep_data = self.__get_data()

        if self.REVIEW_MANAGER.DEBUG_MODE:
            for item in pdf_prep_data["items"]:
                record = item["record"]
                print(record["ID"])
                record = self.prepare_pdf(item)
                self.REVIEW_MANAGER.pp.pprint(record)
                self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
                    record_list=[record]
                )
        else:
            pdf_prep_record_list = p_map(self.prepare_pdf, pdf_prep_data["items"])
            self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
                record_list=pdf_prep_record_list
            )

            # Multiprocessing mixes logs of different records.
            # For better readability:
            self.REVIEW_MANAGER.reorder_log(IDs=[x["ID"] for x in pdf_prep_record_list])

        self._print_stats(pdf_prep_record_list=pdf_prep_record_list)

        # Note: for formatting...
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        self.REVIEW_MANAGER.create_commit(
            msg="Prepare PDFs", script_call="colrev pdf-prep", saved_args=saved_args
        )

        return


if __name__ == "__main__":
    pass
