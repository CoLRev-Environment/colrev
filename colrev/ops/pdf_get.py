#! /usr/bin/env python
"""CoLRev pdf_get operation: Get PDF documents."""
from __future__ import annotations

import shutil
import typing
from glob import glob
from multiprocessing.pool import ThreadPool as Pool
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.process.operation
import colrev.record.record_pdf
from colrev.constants import Colors
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import PDFPathType
from colrev.constants import RecordState
from colrev.writer.write_utils import write_file


class PDFGet(colrev.process.operation.Operation):
    """Get the PDFs"""

    to_retrieve: int
    retrieved: int
    not_retrieved: int

    type = OperationsType.pdf_get

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

        pdf_dir = self.review_manager.paths.pdf
        pdf_dir.mkdir(exist_ok=True, parents=True)

        self.pdf_qm = self.review_manager.get_pdf_qm()

        self.filepath_directory_pattern = ""
        pdf_endpoints = [
            s
            for s in self.review_manager.settings.sources
            if s.endpoint == "colrev.files_dir"
        ]
        if pdf_endpoints:
            self.filepath_directory_pattern = (
                pdf_endpoints[0].search_parameters["scope"].get("subdir_pattern", {})
            )

    def copy_pdfs_to_repo(self) -> None:
        """Copy the PDFs to the repository"""
        self.review_manager.logger.info("Copy PDFs to dir")
        records = self.review_manager.dataset.load_records_dict()

        for record_dict in records.values():
            if Fields.FILE not in record_dict:
                continue
            fpath = Path(record_dict[Fields.FILE])
            new_fpath = fpath.absolute()
            if fpath.is_symlink():
                linked_file = fpath.resolve()
                if linked_file.is_file():
                    fpath.unlink()
                    shutil.copyfile(linked_file, new_fpath)
                    self.review_manager.logger.info(
                        f" {Colors.GREEN}copied PDF for {record_dict[Fields.ID]} {Colors.END}"
                    )

            elif new_fpath.is_file() and self.review_manager.verbose_mode:
                self.review_manager.logger.info(
                    f"No need to copy PDF - already exits ({record_dict[Fields.ID]})"
                )

    def link_pdf(
        self, record: colrev.record.record.Record
    ) -> colrev.record.record.Record:
        """Link the PDF in its record (should be {ID}.pdf)"""

        pdf_filepath = self.review_manager.paths.PDF_DIR / Path(
            f"{record.data['ID']}.pdf"
        )
        if (self.review_manager.path / pdf_filepath).is_file() and str(
            pdf_filepath
        ) != record.data.get(Fields.FILE, "NA"):
            record.update_field(
                key=Fields.FILE, value=str(pdf_filepath), source="link_pdf"
            )
            self.import_pdf(record)
            if RecordState.rev_prescreen_included == record.data[Fields.STATUS]:
                record.set_status(RecordState.pdf_imported)

        return record

    def get_target_filepath(self, record: colrev.record.record.Record) -> Path:
        """Get the target filepath for a PDF"""

        if self.filepath_directory_pattern == Fields.YEAR:
            target_filepath = self.review_manager.paths.PDF_DIR / Path(
                f"{record.data.get('year', 'no_year')}/{record.data['ID']}.pdf"
            )

        elif self.filepath_directory_pattern == "volume_number":
            if Fields.VOLUME in record.data and Fields.NUMBER in record.data:
                target_filepath = self.review_manager.paths.PDF_DIR / Path(
                    f"{record.data['volume']}/{record.data['number']}/{record.data['ID']}.pdf"
                )

            if Fields.VOLUME in record.data and Fields.NUMBER not in record.data:
                target_filepath = self.review_manager.paths.PDF_DIR / Path(
                    f"{record.data['volume']}/{record.data['ID']}.pdf"
                )
        else:
            target_filepath = self.review_manager.paths.PDF_DIR / Path(
                f"{record.data['ID']}.pdf"
            )

        return target_filepath

    def import_pdf(self, record: colrev.record.record.Record) -> None:
        """Import a file (PDF) and copy/symlink it"""
        # self.review_manager.pdf_dir.mkdir(exist_ok=True)
        # new_fp = self.review_manager.PDF_DIR_RELATIVE / Path(record.data[Fields.ID] + ".pdf").name
        new_fp = self.get_target_filepath(record)
        original_fp = Path(record.data[Fields.FILE])

        if new_fp != original_fp and not new_fp.is_file():
            new_fp.parents[0].mkdir(exist_ok=True, parents=True)
            if (
                PDFPathType.symlink
                == self.review_manager.settings.pdf_get.pdf_path_type
            ):
                new_fp.symlink_to(original_fp)
            elif PDFPathType.copy == self.review_manager.settings.pdf_get.pdf_path_type:
                shutil.copyfile(original_fp, new_fp.resolve())
            # Note : else: leave absolute paths

        record.data[Fields.FILE] = str(new_fp)

    def _log_infos(self, record: colrev.record.record.Record) -> None:
        if Fields.FILE not in record.data:
            if (
                not self.review_manager.settings.pdf_get.pdf_required_for_screen_and_synthesis
            ):
                return
            self.review_manager.logger.info(
                f" {Colors.ORANGE}{record.data['ID']}".ljust(46)
                + f"rev_prescreen_included → pdf_needs_manual_retrieval{Colors.END}"
            )
            return

        if RecordState.pdf_prepared == record.data[Fields.STATUS]:
            self.review_manager.logger.info(
                f" {Colors.GREEN}{record.data['ID']}".ljust(46)
                + f"rev_prescreen_included → pdf_prepared{Colors.END}"
            )
        elif RecordState.pdf_needs_manual_preparation == record.data[Fields.STATUS]:
            self.review_manager.logger.info(
                f" {Colors.ORANGE}{record.data['ID']}".ljust(46)
                + f"rev_prescreen_included → pdf_needs_manual_preparation{Colors.END}"
            )

    # Note : no named arguments (multiprocessing)
    def get_pdf(self, item: dict) -> dict:
        """Get PDFs (based on the package endpoints in the settings)"""

        record_dict = item["record"]

        if record_dict[Fields.STATUS] not in [
            RecordState.rev_prescreen_included,
            RecordState.pdf_needs_manual_retrieval,
        ]:
            if Fields.FILE in record_dict:
                record = colrev.record.record_pdf.PDFRecord(record_dict)
                record.remove_field(key=Fields.FILE)
                return record.get_data()
            return record_dict

        record = colrev.record.record_pdf.PDFRecord(record_dict)

        for (
            pdf_get_package_endpoint
        ) in self.review_manager.settings.pdf_get.pdf_get_package_endpoints:

            pdf_get_class = self.package_manager.get_package_endpoint_class(
                package_type=EndpointType.pdf_get,
                package_identifier=pdf_get_package_endpoint["endpoint"],
            )
            endpoint = pdf_get_class(
                pdf_get_operation=self, settings=pdf_get_package_endpoint
            )

            endpoint.get_pdf(record)  # type: ignore

            if Fields.FILE in record.data:
                self.review_manager.report_logger.info(
                    f"{endpoint.settings.endpoint}"  # type: ignore
                    f"({record.data[Fields.ID]}): retrieved .../"
                    f"{Path(record.data[Fields.FILE]).name}"
                )
                break

        if Fields.FILE in record.data:
            record.run_pdf_quality_model(self.pdf_qm, set_prepared=True)
        else:
            record.set_status(RecordState.pdf_needs_manual_retrieval)

        self._log_infos(record)

        return record.get_data()

    def _relink_pdfs(
        self,
        records: typing.Dict[str, typing.Dict],
    ) -> typing.Dict[str, typing.Dict]:
        # pylint: disable=too-many-branches

        pdf_dir = self.review_manager.paths.pdf

        # Relink files in source file
        corresponding_origin: str
        source_records: typing.List[typing.Dict] = []
        for source in self.review_manager.settings.sources:
            if source.endpoint != "colrev.files_dir":
                continue

            if not source.filename.is_file():
                continue

            corresponding_origin = str(source.filename)

            source_records_dict = colrev.loader.load_utils.load(
                filename=source.filename,
                logger=self.review_manager.logger,
            )
            source_records = list(source_records_dict.values())

            self.review_manager.logger.info("Calculate colrev_pdf_ids")
            pdf_candidates = {
                pdf_candidate.relative_to(
                    self.review_manager.path
                ): colrev.record.record_pdf.PDFRecord.get_colrev_pdf_id(pdf_candidate)
                for pdf_candidate in list(pdf_dir.glob("**/*.pdf"))
            }

            for record in records.values():
                if Fields.FILE not in record:
                    continue

                # Note: we check the source_records based on the cpids
                # in the record because cpids are not stored in the source_record
                # (pdf hashes may change after import/preparation)
                source_rec = {}
                if corresponding_origin != "":
                    source_origin_l = [
                        o for o in record[Fields.ORIGIN] if corresponding_origin in o
                    ]
                    if len(source_origin_l) == 1:
                        source_origin = source_origin_l[0]
                        source_origin = source_origin.replace(
                            f"{corresponding_origin}/", ""
                        )
                        source_rec_l = [
                            s for s in source_records if s[Fields.ID] == source_origin
                        ]
                        if len(source_rec_l) == 1:
                            source_rec = source_rec_l[0]

                if source_rec:
                    if (
                        self.review_manager.path / Path(record[Fields.FILE])
                    ).is_file() and (
                        self.review_manager.path / Path(source_rec[Fields.FILE])
                    ).is_file():
                        continue
                else:
                    if (self.review_manager.path / Path(record[Fields.FILE])).is_file():
                        continue

                self.review_manager.logger.info(record[Fields.ID])

                for pdf_candidate, cpid in pdf_candidates.items():
                    if record.get("colrev_pdf_id", "") == cpid:
                        record[Fields.FILE] = str(pdf_candidate)
                        source_rec[Fields.FILE] = str(pdf_candidate)

                        self.review_manager.logger.info(
                            f"Found and linked PDF: {pdf_candidate}"
                        )
                        break

            if len(source_records) > 0:
                source_records_dict = {r[Fields.ID]: r for r in source_records}

                write_file(records_dict=source_records_dict, filename=source.filename)

            self.review_manager.dataset.add_changes(source.filename)

        return records

    def relink_pdfs(self) -> None:
        """Relink record files to the corresponding PDFs (if available)"""

        self.review_manager.logger.info(
            "Checking PDFs in same directory to reassig when the cpid is identical"
        )
        records = self.review_manager.dataset.load_records_dict()
        records = self._relink_pdfs(records)

        self.review_manager.dataset.save_records_dict(records)
        self.review_manager.dataset.create_commit(msg="Relink PDFs")

    def check_existing_unlinked_pdfs(
        self,
        records: dict,
    ) -> dict:
        """Check for PDFs that are in the pdfs directory but not linked in the record file"""

        linked_pdfs = [
            str(Path(x[Fields.FILE]).resolve())
            for x in records.values()
            if Fields.FILE in x
        ]
        pdf_dir = self.review_manager.paths.pdf
        pdf_files = glob(str(pdf_dir) + "/**.pdf", recursive=True)
        unlinked_pdfs = [
            Path(x)
            for x in pdf_files
            if str(Path(x).resolve()) not in linked_pdfs
            and not any(kw in x for kw in ["_with_lp.pdf", "_with_cp.pdf", "_ocr.pdf"])
        ]

        if len(unlinked_pdfs) == 0:
            return records

        grobid_service = self.review_manager.get_grobid_service()
        grobid_service.start()
        self.review_manager.logger.info("Check unlinked PDFs")
        for file in unlinked_pdfs:
            msg = f"Check unlinked PDF: {file.relative_to(self.review_manager.path)}"
            self.review_manager.logger.info(msg)
            if file.stem not in records.keys():
                tei = self.review_manager.get_tei(pdf_path=file)
                pdf_record = tei.get_metadata()

                if "error" in pdf_record:
                    continue

                max_similarity = 0.0
                max_sim_record = None
                for record in records.values():
                    sim = colrev.record.record_pdf.PDFRecord.get_record_similarity(
                        colrev.record.record_pdf.PDFRecord(pdf_record),
                        colrev.record.record_pdf.PDFRecord(record.copy()),
                    )
                    if sim > max_similarity:
                        max_similarity = sim
                        max_sim_record = record
                if max_sim_record:
                    if max_similarity > 0.5:
                        if RecordState.pdf_prepared == max_sim_record[Fields.STATUS]:
                            continue

                        record = colrev.record.record_pdf.PDFRecord(max_sim_record)
                        record.update_field(
                            key=Fields.FILE,
                            value=str(file),
                            source="linking-available-files",
                        )
                        self.import_pdf(record)
                        if (
                            RecordState.rev_prescreen_included
                            == record.data[Fields.STATUS]
                        ):
                            record.set_status(RecordState.pdf_imported)

                        self.review_manager.report_logger.info(
                            "linked unlinked pdf:" f" {file.name}"
                        )
                        self.review_manager.logger.info(
                            "linked unlinked pdf:" f" {file.name}"
                        )
                        # max_sim_record = \
                        #     pdf_prep.validate_pdf_metadata(max_sim_record)
                        # colrev_status = max_sim_record['colrev_status']
                        # if RecordState.pdf_needs_manual_preparation == colrev_status:
                        #     # revert?
            else:
                record = records[file.stem]
                self.link_pdf(colrev.record.record_pdf.PDFRecord(record))

        self.review_manager.dataset.save_records_dict(records)

        return records

    def _rename_pdf(
        self,
        *,
        record_dict: dict,
        file: Path,
        new_filename: Path,
        pdfs_search_file: Path,
    ) -> None:
        record_dict[Fields.FILE] = new_filename
        if pdfs_search_file.is_file():
            colrev.env.utils.inplace_change(
                filename=pdfs_search_file,
                old_string="{" + str(file) + "}",
                new_string="{" + str(new_filename) + "}",
            )

        if not file.is_file():
            corrected_path = Path(str(file).replace("  ", " "))
            if corrected_path.is_file():
                file = corrected_path

        if file.is_file():
            shutil.move(str(file), str(new_filename))
        elif file.is_symlink():
            shutil.move(str(file), str(new_filename))

        record_dict[Fields.FILE] = str(new_filename)
        self.review_manager.logger.info(f"rename {file.name} > {new_filename}")
        if RecordState.rev_prescreen_included == record_dict[Fields.STATUS]:
            record = colrev.record.record_pdf.PDFRecord(record_dict)
            record.set_status(RecordState.pdf_imported)

    def rename_pdfs(self) -> None:
        """Rename the PDFs"""

        self.review_manager.logger.info("Rename PDFs")

        records = self.review_manager.dataset.load_records_dict()

        # We may use other pdfs_search_files from the sources:
        # review_manager.settings.sources
        pdfs_search_file = Path("data/search/pdfs.bib")

        for record_dict in records.values():
            if Fields.FILE not in record_dict:
                continue
            if record_dict[Fields.STATUS] not in RecordState.get_post_x_states(
                state=RecordState.md_processed
            ):
                continue

            file = Path(record_dict[Fields.FILE])
            new_filename = file.parents[0] / Path(f"{record_dict['ID']}{file.suffix}")
            # Possible option: move to top (pdfs) directory:
            # new_filename = self.review_manager.PDF_DIR_RELATIVE / Path(
            #     f"{record['ID']}.pdf"
            # )
            if str(file) == str(new_filename):
                continue

            self._rename_pdf(
                record_dict=record_dict,
                file=file,
                new_filename=new_filename,
                pdfs_search_file=pdfs_search_file,
            )

        self.review_manager.dataset.save_records_dict(records)

        if pdfs_search_file.is_file():
            self.review_manager.dataset.add_changes(pdfs_search_file)

    def _get_data(self) -> dict:
        # pylint: disable=duplicate-code

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())

        nr_tasks = len(
            [
                x
                for x in record_header_list
                if x[Fields.STATUS]
                in [
                    RecordState.pdf_needs_manual_retrieval,
                    RecordState.rev_prescreen_included,
                ]
            ]
        )

        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {Fields.STATUS: RecordState.rev_prescreen_included},
                {Fields.STATUS: RecordState.pdf_needs_manual_retrieval},
            ],
        )

        self.to_retrieve = nr_tasks

        pdf_get_data = {
            "nr_tasks": nr_tasks,
            "items": [{"record": item} for item in items],
        }

        return pdf_get_data

    def _print_stats(self, retrieved_record_list: list) -> None:
        self.retrieved = len([r for r in retrieved_record_list if Fields.FILE in r])

        self.not_retrieved = self.to_retrieve - self.retrieved

        retrieved_string = "Overall pdf_imported".ljust(34)
        if self.retrieved == 0:
            retrieved_string += f"{self.retrieved}".rjust(6, " ")
            retrieved_string += " PDFs"
        elif self.retrieved == 1:
            retrieved_string += f"{Colors.GREEN}"
            retrieved_string += f"{self.retrieved}".rjust(6, " ")
            retrieved_string += f"{Colors.END} PDF"
        else:
            retrieved_string += f"{Colors.GREEN}"
            retrieved_string += f"{self.retrieved}".rjust(6, " ")
            retrieved_string += f"{Colors.END} PDFs"

        not_retrieved_string = "Overall pdf_needs_manual_retrieval".ljust(34)
        if self.not_retrieved == 0:
            not_retrieved_string += f"{self.not_retrieved}".rjust(6, " ")
            not_retrieved_string += " PDFs"
        elif self.not_retrieved == 1:
            not_retrieved_string += f"{Colors.ORANGE}"
            not_retrieved_string += f"{self.not_retrieved}".rjust(6, " ")
            not_retrieved_string += f"{Colors.END} PDF"
        else:
            not_retrieved_string += f"{Colors.ORANGE}"
            not_retrieved_string += f"{self.not_retrieved}".rjust(6, " ")
            not_retrieved_string += f"{Colors.END} PDFs"

        self.review_manager.logger.info(retrieved_string)
        self.review_manager.logger.info(not_retrieved_string)

    def _set_status_if_pdf_linked(self, records: dict) -> dict:
        for record_dict in records.values():
            if record_dict[Fields.STATUS] in [
                RecordState.rev_prescreen_included,
                RecordState.pdf_needs_manual_retrieval,
            ]:
                record = colrev.record.record_pdf.PDFRecord(record_dict)
                if Fields.FILE in record_dict:
                    if any(
                        Path(fpath).is_file()
                        for fpath in record.data[Fields.FILE].split(";")
                    ):
                        if (
                            RecordState.rev_prescreen_included
                            == record.data[Fields.STATUS]
                        ):
                            record.set_status(RecordState.pdf_imported)
                    else:
                        self.review_manager.logger.warning(
                            "Remove non-existent file link "
                            f"({record_dict[Fields.ID]}: {record_dict[Fields.FILE]}"
                        )
                        record.remove_field(key=Fields.FILE)
        self.review_manager.dataset.save_records_dict(records)

        return records

    def setup_custom_script(self) -> None:
        """Setup a custom pfd-get script"""

        filedata = colrev.env.utils.get_package_file_content(
            module="colrev.ops",
            filename=Path("custom_scripts/custom_pdf_get_script.py"),
        )
        if filedata:
            with open("custom_pdf_get_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(Path("custom_pdf_get_script.py"))

        self.review_manager.settings.pdf_get.pdf_get_man_package_endpoints.append(
            {"endpoint": "custom_pdf_get_script"}
        )

        self.review_manager.save_settings()

    @colrev.process.operation.Operation.decorate()
    def main(self) -> None:
        """Get PDFs (main entrypoint)"""

        if (
            self.review_manager.in_ci_environment()
            and not self.review_manager.in_test_environment()
        ):
            raise colrev_exceptions.ServiceNotAvailableException(
                dep="colrev pdf-prep",
                detailed_trace="pdf-prep not available in ci environment",
            )

        self.review_manager.logger.info("Get PDFs")
        self.review_manager.logger.info(
            "Get PDFs of prescreen-included records from local and remote sources."
        )
        self.review_manager.logger.info(
            "PDFs are stored in the directory data/pdfs "
            f"({Colors.ORANGE}colrev pdfs --dir{Colors.END})"
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_get.html"
        )

        records = self.review_manager.dataset.load_records_dict()
        records = self._set_status_if_pdf_linked(records)
        records = self.check_existing_unlinked_pdfs(records)

        pdf_get_data = self._get_data()

        if pdf_get_data["nr_tasks"] == 0:
            self.review_manager.logger.info("No additional pdfs to retrieve")
        else:
            self.review_manager.logger.info(
                "PDFs to get".ljust(38) + f'{pdf_get_data["nr_tasks"]} PDFs'
            )

            pool = Pool(4)
            retrieved_record_list = pool.map(self.get_pdf, pdf_get_data["items"])
            pool.close()
            pool.join()

            self.review_manager.dataset.save_records_dict(
                {r[Fields.ID]: r for r in retrieved_record_list}, partial=True
            )

            self._print_stats(retrieved_record_list)

        # Note: rename should be after copy.
        # Note : do not pass records as an argument.
        if self.review_manager.settings.pdf_get.rename_pdfs:
            self.rename_pdfs()

        self.review_manager.dataset.create_commit(msg="Get PDFs")
        self.review_manager.logger.info(
            f"{Colors.GREEN}Completed pdf-get operation{Colors.END}"
        )
