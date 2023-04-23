#! /usr/bin/env python
"""CoLRev pdf_get operation: Get PDF documents."""
from __future__ import annotations

import os
import shutil
import typing
from glob import glob
from multiprocessing.pool import ThreadPool as Pool
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.operation
import colrev.record
import colrev.ui_cli.cli_colors as colors


class PDFGet(colrev.operation.Operation):
    """Get the PDFs"""

    to_retrieve: int
    retrieved: int
    not_retrieved: int

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        notify_state_transition_operation: bool = True,
    ) -> None:
        super().__init__(
            review_manager=review_manager,
            operations_type=colrev.operation.OperationsType.pdf_get,
            notify_state_transition_operation=notify_state_transition_operation,
        )

        self.package_manager = self.review_manager.get_package_manager()

        self.review_manager.pdf_dir.mkdir(exist_ok=True, parents=True)

        self.filepath_directory_pattern = ""
        pdf_endpoints = [
            s
            for s in self.review_manager.settings.sources
            if s.endpoint == "colrev.pdfs_dir"
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
            if "file" in record_dict:
                fpath = Path(record_dict["file"])
                new_fpath = fpath.absolute()
                if fpath.is_symlink():
                    linked_file = fpath.resolve()
                    if linked_file.is_file():
                        fpath.unlink()
                        shutil.copyfile(linked_file, new_fpath)
                        self.review_manager.logger.info(
                            f' {colors.GREEN}copied PDF for {record_dict["ID"]} {colors.END}'
                        )

                elif new_fpath.is_file():
                    if self.review_manager.verbose_mode:
                        self.review_manager.logger.info(
                            f'No need to copy PDF - already exits ({record_dict["ID"]})'
                        )

    def link_pdf(self, *, record: colrev.record.Record) -> colrev.record.Record:
        """Link the PDF in its record (should be {ID}.pdf)"""

        pdf_filepath = self.review_manager.PDF_DIR_RELATIVE / Path(
            f"{record.data['ID']}.pdf"
        )
        if pdf_filepath.is_file() and str(pdf_filepath) != record.data.get(
            "file", "NA"
        ):
            record.update_field(key="file", value=str(pdf_filepath), source="link_pdf")
            self.import_file(record=record)
            if (
                colrev.record.RecordState.rev_prescreen_included
                == record.data["colrev_status"]
            ):
                record.set_status(target_state=colrev.record.RecordState.pdf_imported)

        return record

    def get_target_filepath(self, *, record: colrev.record.Record) -> Path:
        """Get the target filepath for a PDF"""

        if self.filepath_directory_pattern == "year":
            target_filepath = self.review_manager.PDF_DIR_RELATIVE / Path(
                f"{record.data.get('year', 'no_year')}/{record.data['ID']}.pdf"
            )

        elif self.filepath_directory_pattern == "volume_number":
            if "volume" in record.data and "number" in record.data:
                target_filepath = self.review_manager.PDF_DIR_RELATIVE / Path(
                    f"{record.data['volume']}/{record.data['number']}/{record.data['ID']}.pdf"
                )

            if "volume" in record.data and "number" not in record.data:
                target_filepath = self.review_manager.PDF_DIR_RELATIVE / Path(
                    f"{record.data['volume']}/{record.data['ID']}.pdf"
                )
        else:
            target_filepath = self.review_manager.PDF_DIR_RELATIVE / Path(
                f"{record.data['ID']}.pdf"
            )

        return target_filepath

    def import_file(self, *, record: colrev.record.Record) -> None:
        """Import a file (PDF) and copy/symlink it"""
        # self.review_manager.pdf_dir.mkdir(exist_ok=True)
        # new_fp = self.review_manager.PDF_DIR_RELATIVE / Path(record.data["ID"] + ".pdf").name
        new_fp = self.get_target_filepath(record=record)
        original_fp = Path(record.data["file"])

        if new_fp != original_fp:
            new_fp.parents[0].mkdir(exist_ok=True, parents=True)
            if (
                colrev.settings.PDFPathType.symlink
                == self.review_manager.settings.pdf_get.pdf_path_type
            ):
                if not new_fp.is_file():
                    new_fp.symlink_to(original_fp)
            elif (
                colrev.settings.PDFPathType.copy
                == self.review_manager.settings.pdf_get.pdf_path_type
            ):
                if not new_fp.is_file():
                    shutil.copyfile(original_fp, new_fp.resolve())
            # Note : else: leave absolute paths

        record.data["file"] = str(new_fp)

    # Note : no named arguments (multiprocessing)
    def get_pdf(self, item: dict) -> dict:
        """Get PDFs (based on the package endpoints in the settings)"""

        record_dict = item["record"]

        if str(colrev.record.RecordState.rev_prescreen_included) != str(
            record_dict["colrev_status"]
        ):
            if "file" in record_dict:
                record = colrev.record.Record(data=record_dict)
                record.remove_field(key="file")
                return record.get_data()
            return record_dict

        record = colrev.record.Record(data=record_dict)

        for (
            pdf_get_package_endpoint
        ) in self.review_manager.settings.pdf_get.pdf_get_package_endpoints:
            endpoint_dict = self.package_manager.load_packages(
                package_type=colrev.env.package_manager.PackageEndpointType.pdf_get,
                selected_packages=[pdf_get_package_endpoint],
                operation=self,
                only_ci_supported=self.review_manager.in_ci_environment(),
            )
            if pdf_get_package_endpoint["endpoint"] not in endpoint_dict:
                self.review_manager.logger.info(
                    f'Skip {pdf_get_package_endpoint["endpoint"]} (not available)'
                )
                continue

            endpoint = endpoint_dict[pdf_get_package_endpoint["endpoint"]]
            endpoint.get_pdf(self, record)  # type: ignore

            if "file" in record.data:
                self.review_manager.report_logger.info(
                    f"{endpoint.settings.endpoint}"  # type: ignore
                    f'({record_dict["ID"]}): retrieved .../{Path(record_dict["file"]).name}'
                )
                if (
                    colrev.record.RecordState.rev_prescreen_included
                    == record.data["colrev_status"]
                ):
                    record.data.update(
                        colrev_status=colrev.record.RecordState.pdf_imported
                    )
                    self.review_manager.logger.info(
                        f" {colors.GREEN}{record.data['ID']}".ljust(46)
                        + f"rev_prescreen_included → pdf_imported{colors.END}"
                    )
                return record.get_data()

        if self.review_manager.settings.pdf_get.pdf_required_for_screen_and_synthesis:
            self.review_manager.logger.info(
                f" {colors.ORANGE}{record.data['ID']}".ljust(46)
                + f"rev_prescreen_included → pdf_needs_manual_retrieval{colors.END}"
            )

            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_retrieval
            )
        else:
            self.review_manager.logger.info(
                f" {colors.ORANGE}{record.data['ID']}".ljust(46)
                + f"rev_prescreen_included → pdf_prepared{colors.END}"
            )

            record.data.update(colrev_status=colrev.record.RecordState.pdf_prepared)

        return record.get_data()

    def __relink_pdf_files(
        self,
        *,
        records: typing.Dict[str, typing.Dict],
    ) -> typing.Dict[str, typing.Dict]:
        # pylint: disable=too-many-branches

        # Relink files in source file
        corresponding_origin: str
        source_records: typing.List[typing.Dict] = []
        for source in self.review_manager.settings.sources:
            if source.endpoint != "colrev.pdfs_dir":
                continue

            if not source.filename.is_file():
                continue

            corresponding_origin = str(source.filename)
            with open(source.filename, encoding="utf8") as target_db:
                source_records_dict = self.review_manager.dataset.load_records_dict(
                    load_str=target_db.read()
                )
            source_records = list(source_records_dict.values())

            self.review_manager.logger.info("Calculate colrev_pdf_ids")
            pdf_candidates = {
                pdf_candidate.relative_to(
                    self.review_manager.path
                ): colrev.record.Record.get_colrev_pdf_id(pdf_path=pdf_candidate)
                for pdf_candidate in list(self.review_manager.pdf_dir.glob("**/*.pdf"))
            }

            for record in records.values():
                if "file" not in record:
                    continue

                # Note: we check the source_records based on the cpids
                # in the record because cpids are not stored in the source_record
                # (pdf hashes may change after import/preparation)
                source_rec = {}
                if corresponding_origin != "":
                    source_origin_l = [
                        o for o in record["colrev_origin"] if corresponding_origin in o
                    ]
                    if len(source_origin_l) == 1:
                        source_origin = source_origin_l[0]
                        source_origin = source_origin.replace(
                            f"{corresponding_origin}/", ""
                        )
                        source_rec_l = [
                            s for s in source_records if s["ID"] == source_origin
                        ]
                        if len(source_rec_l) == 1:
                            source_rec = source_rec_l[0]

                if source_rec:
                    if (self.review_manager.path / Path(record["file"])).is_file() and (
                        self.review_manager.path / Path(source_rec["file"])
                    ).is_file():
                        continue
                else:
                    if (self.review_manager.path / Path(record["file"])).is_file():
                        continue

                self.review_manager.logger.info(record["ID"])

                for pdf_candidate, cpid in pdf_candidates.items():
                    if record.get("colrev_pdf_id", "") == cpid:
                        record["file"] = str(pdf_candidate)
                        source_rec["file"] = str(pdf_candidate)

                        self.review_manager.logger.info(
                            f"Found and linked PDF: {pdf_candidate}"
                        )
                        break

            if len(source_records) > 0:
                source_records_dict = {r["ID"]: r for r in source_records}
                self.review_manager.dataset.save_records_dict_to_file(
                    records=source_records_dict, save_path=source.filename
                )

            self.review_manager.dataset.add_changes(path=source.filename)

        return records

    def relink_files(self) -> None:
        """Relink record files to the corresponding PDFs (if available)"""

        self.review_manager.logger.info(
            "Checking PDFs in same directory to reassig when the cpid is identical"
        )
        records = self.review_manager.dataset.load_records_dict()
        records = self.__relink_pdf_files(records=records)

        self.review_manager.dataset.save_records_dict(records=records)

        self.review_manager.dataset.add_record_changes()
        self.review_manager.create_commit(msg="Relink PDFs")

    def check_existing_unlinked_pdfs(
        self,
        *,
        records: dict,
    ) -> dict:
        """Check for PDFs that are in the pdfs directory but not linked in the record file"""

        linked_pdfs = [
            str(Path(x["file"]).resolve()) for x in records.values() if "file" in x
        ]

        pdf_files = glob(str(self.review_manager.pdf_dir) + "/**.pdf", recursive=True)
        unlinked_pdfs = [
            Path(x)
            for x in pdf_files
            if str(Path(x).resolve()) not in linked_pdfs
            and not any(kw in x for kw in ["_wo_lp.pdf", "_wo_cp.pdf", "_ocr.pdf"])
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
                    sim = colrev.record.Record.get_record_similarity(
                        record_a=colrev.record.Record(data=pdf_record),
                        record_b=colrev.record.Record(data=record.copy()),
                    )
                    if sim > max_similarity:
                        max_similarity = sim
                        max_sim_record = record
                if max_sim_record:
                    if max_similarity > 0.5:
                        if (
                            colrev.record.RecordState.pdf_prepared
                            == max_sim_record["colrev_status"]
                        ):
                            continue

                        record = colrev.record.Record(data=max_sim_record)
                        record.update_field(
                            key="file",
                            value=str(file),
                            source="linking-available-files",
                        )
                        self.import_file(record=record)
                        if (
                            colrev.record.RecordState.rev_prescreen_included
                            == record.data["colrev_status"]
                        ):
                            record.set_status(
                                target_state=colrev.record.RecordState.pdf_imported
                            )

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
                self.link_pdf(record=colrev.record.Record(data=record))

        self.review_manager.dataset.save_records_dict(records=records)

        return records

    def __rename_pdf(
        self,
        *,
        record_dict: dict,
        file: Path,
        new_filename: Path,
        pdfs_search_file: Path,
    ) -> None:
        record_dict["file"] = new_filename

        if "colrev_masterdata_provenance" in record_dict:
            for value in record_dict["colrev_masterdata_provenance"].values():
                if str(file) == value.get("source", ""):
                    value["source"] = str(new_filename)

        if "data_provenance" in record_dict:
            for value in record_dict["data_provenance"].values():
                if str(file) == value.get("source", ""):
                    value["source"] = str(new_filename)

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
            file.rename(new_filename)
        elif file.is_symlink():
            os.rename(str(file), str(new_filename))

        record_dict["file"] = str(new_filename)
        self.review_manager.logger.info(f"rename {file.name} > {new_filename}")
        if (
            colrev.record.RecordState.rev_prescreen_included
            == record_dict["colrev_status"]
        ):
            record = colrev.record.Record(data=record_dict)
            record.set_status(target_state=colrev.record.RecordState.pdf_imported)

    def rename_pdfs(self) -> None:
        """Rename the PDFs"""

        self.review_manager.logger.info("Rename PDFs")

        records = self.review_manager.dataset.load_records_dict()

        # We may use other pdfs_search_files from the sources:
        # review_manager.settings.sources
        pdfs_search_file = Path("data/search/pdfs.bib")

        for record_dict in records.values():
            if "file" not in record_dict:
                continue
            if record_dict[
                "colrev_status"
            ] not in colrev.record.RecordState.get_post_x_states(
                state=colrev.record.RecordState.md_processed
            ):
                continue

            file = Path(record_dict["file"])
            new_filename = file.parents[0] / Path(f"{record_dict['ID']}{file.suffix}")
            # Possible option: move to top (pdfs) directory:
            # new_filename = self.review_manager.PDF_DIR_RELATIVE / Path(
            #     f"{record['ID']}.pdf"
            # )
            if str(file) == str(new_filename):
                continue

            self.__rename_pdf(
                record_dict=record_dict,
                file=file,
                new_filename=new_filename,
                pdfs_search_file=pdfs_search_file,
            )

        self.review_manager.dataset.save_records_dict(records=records)

        if pdfs_search_file.is_file():
            self.review_manager.dataset.add_changes(path=pdfs_search_file)
        self.review_manager.dataset.add_record_changes()

    def __get_data(self) -> dict:
        # pylint: disable=duplicate-code

        records_headers = self.review_manager.dataset.load_records_dict(
            header_only=True
        )
        record_header_list = list(records_headers.values())

        nr_tasks = len(
            [
                x
                for x in record_header_list
                if colrev.record.RecordState.rev_prescreen_included
                == x["colrev_status"]
            ]
        )

        items = self.review_manager.dataset.read_next_record(
            conditions=[
                {"colrev_status": colrev.record.RecordState.rev_prescreen_included}
            ],
        )

        self.to_retrieve = nr_tasks

        pdf_get_data = {
            "nr_tasks": nr_tasks,
            "items": [{"record": item} for item in items],
        }

        return pdf_get_data

    def _print_stats(self, *, retrieved_record_list: list) -> None:
        self.retrieved = len([r for r in retrieved_record_list if "file" in r])

        self.not_retrieved = self.to_retrieve - self.retrieved

        retrieved_string = "Overall pdf_imported".ljust(34)
        if self.retrieved == 0:
            retrieved_string += f"{self.retrieved}".rjust(6, " ")
            retrieved_string += " PDFs"
        elif self.retrieved == 1:
            retrieved_string += f"{colors.GREEN}"
            retrieved_string += f"{self.retrieved}".rjust(6, " ")
            retrieved_string += f"{colors.END} PDF"
        else:
            retrieved_string += f"{colors.GREEN}"
            retrieved_string += f"{self.retrieved}".rjust(6, " ")
            retrieved_string += f"{colors.END} PDFs"

        not_retrieved_string = "Overall pdf_needs_manual_retrieval".ljust(34)
        if self.not_retrieved == 0:
            not_retrieved_string += f"{self.not_retrieved}".rjust(6, " ")
            not_retrieved_string += " PDFs"
        elif self.not_retrieved == 1:
            not_retrieved_string += f"{colors.ORANGE}"
            not_retrieved_string += f"{self.not_retrieved}".rjust(6, " ")
            not_retrieved_string += f"{colors.END} PDF"
        else:
            not_retrieved_string += f"{colors.ORANGE}"
            not_retrieved_string += f"{self.not_retrieved}".rjust(6, " ")
            not_retrieved_string += f"{colors.END} PDFs"

        self.review_manager.logger.info(retrieved_string)
        self.review_manager.logger.info(not_retrieved_string)

    def __set_status_if_file_linked(self, *, records: dict) -> dict:
        for record_dict in records.values():
            if record_dict["colrev_status"] in [
                colrev.record.RecordState.rev_prescreen_included,
                colrev.record.RecordState.pdf_needs_manual_retrieval,
            ]:
                record = colrev.record.Record(data=record_dict)
                if "file" in record_dict:
                    if any(
                        Path(fpath).is_file()
                        for fpath in record.data["file"].split(";")
                    ):
                        if (
                            colrev.record.RecordState.rev_prescreen_included
                            == record.data["colrev_status"]
                        ):
                            record.set_status(
                                target_state=colrev.record.RecordState.pdf_imported
                            )
                    else:
                        self.review_manager.logger.warning(
                            "Remove non-existent file link "
                            f'({record_dict["ID"]}: {record_dict["file"]}'
                        )
                        record.remove_field(key="file")
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

        return records

    def setup_custom_script(self) -> None:
        """Setup a custom pfd-get script"""

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/custom_scripts/custom_pdf_get_script.py")
        )
        if filedata:
            with open("custom_pdf_get_script.py", "w", encoding="utf-8") as file:
                file.write(filedata.decode("utf-8"))

        self.review_manager.dataset.add_changes(path=Path("custom_pdf_get_script.py"))

        self.review_manager.settings.pdf_get.pdf_get_man_package_endpoints.append(
            {"endpoint": "custom_pdf_get_script"}
        )

        self.review_manager.save_settings()

    def main(self) -> None:
        """Get PDFs (main entrypoint)"""

        if self.review_manager.in_ci_environment():
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
            f"({colors.ORANGE}colrev pdfs --dir{colors.END})"
        )
        self.review_manager.logger.info(
            "See https://colrev.readthedocs.io/en/latest/manual/pdf_retrieval/pdf_get.html"
        )

        records = self.review_manager.dataset.load_records_dict()
        records = self.__set_status_if_file_linked(records=records)
        records = self.check_existing_unlinked_pdfs(records=records)

        pdf_get_data = self.__get_data()

        if pdf_get_data["nr_tasks"] > 0:
            self.review_manager.logger.info(
                "PDFs to get".ljust(38) + f'{pdf_get_data["nr_tasks"]} PDFs'
            )

            pool = Pool(4)
            retrieved_record_list = pool.map(self.get_pdf, pdf_get_data["items"])
            pool.close()
            pool.join()

            self.review_manager.dataset.save_records_dict(
                records={r["ID"]: r for r in retrieved_record_list}, partial=True
            )

            self._print_stats(retrieved_record_list=retrieved_record_list)

            # Note: rename should be after copy.
            # Note : do not pass records as an argument.
            if self.review_manager.settings.pdf_get.rename_pdfs:
                self.rename_pdfs()

        else:
            self.review_manager.logger.info("No additional pdfs to retrieve")

            # Note: rename should be after copy.
            # Note : do not pass records as an argument.
            if self.review_manager.settings.pdf_get.rename_pdfs:
                self.rename_pdfs()

        self.review_manager.create_commit(msg="Get PDFs")
        self.review_manager.logger.info(
            f"{colors.GREEN}Completed pdf-get operation{colors.END}"
        )


if __name__ == "__main__":
    pass
