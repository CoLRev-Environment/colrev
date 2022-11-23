#! /usr/bin/env python
"""SearchSource: directory containing PDF files (based on GROBID)"""
from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfparser import PDFParser

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.pdf_backward_search as bws
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class PDFSearchSource(JsonSchemaMixin):
    """SearchSource for PDF directories (based on GROBID)"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{file}}"
    search_type = colrev.settings.SearchType.PDFS

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        self.settings = from_dict(data_class=self.settings_class, data=settings)
        self.source_operation = source_operation
        self.pdf_preparation_operation = (
            source_operation.review_manager.get_pdf_prep_operation(
                notify_state_transition_operation=False
            )
        )

        self.pdfs_path = source_operation.review_manager.path / Path(
            self.settings.search_parameters["scope"]["path"]
        )
        self.review_manager = source_operation.review_manager

        self.subdir_pattern: re.Pattern = re.compile("")
        self.r_subdir_pattern: re.Pattern = re.compile("")
        if "subdir_pattern" in self.settings.search_parameters.get("scope", {}):
            self.subdir_pattern = self.settings.search_parameters["scope"][
                "subdir_pattern"
            ]
            source_operation.review_manager.logger.info(
                f"Activate subdir_pattern: {self.subdir_pattern}"
            )
            if "year" == self.subdir_pattern:
                self.r_subdir_pattern = re.compile("([1-3][0-9]{3})")
            if "volume_number" == self.subdir_pattern:
                self.r_subdir_pattern = re.compile("([0-9]{1,3})(_|/)([0-9]{1,2})")
            if "volume" == self.subdir_pattern:
                self.r_subdir_pattern = re.compile("([0-9]{1,4})")

    def __update_if_pdf_renamed(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        record_dict: dict,
        records: dict,
        search_source: Path,
    ) -> bool:
        updated = True
        not_updated = False

        c_rec_l = [
            r
            for r in records.values()
            if f"{search_source}/{record_dict['ID']}" in r["colrev_origin"]
        ]
        if len(c_rec_l) == 1:
            c_rec = c_rec_l.pop()
            if "colrev_pdf_id" in c_rec:
                cpid = c_rec["colrev_pdf_id"]
                pdf_fp = search_operation.review_manager.path / Path(
                    record_dict["file"]
                )
                pdf_path = pdf_fp.parents[0]
                potential_pdfs = pdf_path.glob("*.pdf")

                for potential_pdf in potential_pdfs:
                    cpid_potential_pdf = colrev.record.Record.get_colrev_pdf_id(
                        review_manager=search_operation.review_manager,
                        pdf_path=potential_pdf,
                    )

                    if cpid == cpid_potential_pdf:
                        record_dict["file"] = str(
                            potential_pdf.relative_to(
                                search_operation.review_manager.path
                            )
                        )
                        c_rec["file"] = str(
                            potential_pdf.relative_to(
                                search_operation.review_manager.path
                            )
                        )
                        return updated
        return not_updated

    def __remove_records_if_pdf_no_longer_exists(
        self, *, search_operation: colrev.ops.search.Search
    ) -> None:

        # search_operation.review_manager.logger.debug(
        #     "Checking for PDFs that no longer exist"
        # )

        if not self.settings.filename.is_file():
            return

        with open(self.settings.filename, encoding="utf8") as target_db:

            search_rd = search_operation.review_manager.dataset.load_records_dict(
                load_str=target_db.read()
            )

        records = {}
        if search_operation.review_manager.dataset.records_file.is_file():
            records = search_operation.review_manager.dataset.load_records_dict()

        to_remove: typing.List[str] = []
        files_removed = []
        for record_dict in search_rd.values():
            x_pdf_path = search_operation.review_manager.path / Path(
                record_dict["file"]
            )
            if not x_pdf_path.is_file():
                if records:
                    updated = self.__update_if_pdf_renamed(
                        search_operation=search_operation,
                        record_dict=record_dict,
                        records=records,
                        search_source=self.settings.filename,
                    )
                    if updated:
                        continue
                to_remove.append(f"{self.settings.filename.name}/{record_dict['ID']}")
                files_removed.append(record_dict["file"])

        search_rd = {
            x["ID"]: x
            for x in search_rd.values()
            if (search_operation.review_manager.path / Path(x["file"])).is_file()
        }

        if len(search_rd.values()) != 0:
            search_operation.review_manager.dataset.save_records_dict_to_file(
                records=search_rd, save_path=self.settings.filename
            )

        if search_operation.review_manager.dataset.records_file.is_file():
            for record_dict in records.values():
                for origin_to_remove in to_remove:
                    if origin_to_remove in record_dict["colrev_origin"]:
                        record_dict["colrev_origin"].remove(origin_to_remove)
            if to_remove:
                search_operation.review_manager.logger.info(
                    f" {colors.RED}Removed {len(to_remove)} records "
                    f"(PDFs no longer available){colors.END}"
                )
                print(" " + "\n ".join(files_removed))
            records = {k: v for k, v in records.items() if v["colrev_origin"]}
            search_operation.review_manager.dataset.save_records_dict(records=records)
            search_operation.review_manager.dataset.add_record_changes()

    def __update_fields_based_on_pdf_dirs(
        self, *, record_dict: dict, params: dict
    ) -> dict:
        if not self.subdir_pattern:
            return record_dict

        if "journal" in params["scope"]:
            record_dict["journal"] = params["scope"]["journal"]
            record_dict["ENTRYTYPE"] = "article"

        if "conference" in params["scope"]:
            record_dict["booktitle"] = params["scope"]["conference"]
            record_dict["ENTRYTYPE"] = "inproceedings"

        if self.subdir_pattern:

            # Note : no file access here (just parsing the patterns)
            # no absolute paths needed
            partial_path = Path(record_dict["file"]).parents[0]

            if "year" == self.subdir_pattern:
                # Note: for year-patterns, we allow subfolders
                # (eg., conference tracks)
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    year = match.group(1)
                    record_dict["year"] = year

            elif "volume_number" == self.subdir_pattern:
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    volume = match.group(1)
                    number = match.group(3)
                    record_dict["volume"] = volume
                    record_dict["number"] = number
                else:
                    # sometimes, journals switch...
                    r_subdir_pattern = re.compile("([0-9]{1,3})")
                    match = r_subdir_pattern.search(str(partial_path))
                    if match is not None:
                        volume = match.group(1)
                        record_dict["volume"] = volume

            elif "volume" == self.subdir_pattern:
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    volume = match.group(1)
                    record_dict["volume"] = volume

        return record_dict

    # curl -v --form input=@./profit.pdf localhost:8070/api/processHeaderDocument
    # curl -v --form input=@./thefile.pdf -H "Accept: application/x-bibtex"
    # -d "consolidateHeader=0" localhost:8070/api/processHeaderDocument
    def __get_record_from_pdf_grobid(
        self, *, search_operation: colrev.ops.search.Search, record_dict: dict
    ) -> dict:

        if colrev.record.RecordState.md_prepared == record_dict.get(
            "colrev_status", "NA"
        ):
            return record_dict

        pdf_path = search_operation.review_manager.path / Path(record_dict["file"])
        tei = search_operation.review_manager.get_tei(
            pdf_path=pdf_path,
        )

        extracted_record = tei.get_metadata()

        for key, val in extracted_record.items():
            if val:
                record_dict[key] = str(val)

        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            doc = PDFDocument(parser)

            if record_dict.get("title", "NA") in ["NA", ""]:
                if "Title" in doc.info[0]:
                    try:
                        record_dict["title"] = doc.info[0]["Title"].decode("utf-8")
                    except UnicodeDecodeError:
                        pass
            if record_dict.get("author", "NA") in ["NA", ""]:
                if "Author" in doc.info[0]:
                    try:
                        pdf_md_author = doc.info[0]["Author"].decode("utf-8")
                        if (
                            "Mirko Janc" not in pdf_md_author
                            and "wendy" != pdf_md_author
                            and "yolanda" != pdf_md_author
                        ):
                            record_dict["author"] = pdf_md_author
                    except UnicodeDecodeError:
                        pass

            if "abstract" in record_dict:
                del record_dict["abstract"]
            if "keywords" in record_dict:
                del record_dict["keywords"]

            # to allow users to update/reindex with newer version:
            record_dict["grobid-version"] = (
                "lfoppiano/grobid:" + tei.get_grobid_version()
            )

            return record_dict

    def __index_pdf(
        self, *, search_operation: colrev.ops.search.Search, pdf_path: Path
    ) -> dict:

        search_operation.review_manager.report_logger.info(
            f" extract metadata from {pdf_path}"
        )
        search_operation.review_manager.logger.info(
            f" extract metadata from {pdf_path}"
        )

        record_dict: typing.Dict[str, typing.Any] = {
            "file": str(pdf_path),
            "ENTRYTYPE": "misc",
        }
        try:
            record_dict = self.__get_record_from_pdf_grobid(
                search_operation=search_operation, record_dict=record_dict
            )

            with open(pdf_path, "rb") as file:
                parser = PDFParser(file)
                document = PDFDocument(parser)
                pages_in_file = resolve1(document.catalog["Pages"])["Count"]
                if pages_in_file < 6:
                    record = colrev.record.Record(data=record_dict)
                    record.set_text_from_pdf(
                        project_path=search_operation.review_manager.path
                    )
                    record_dict = record.get_data()
                    if "text_from_pdf" in record_dict:
                        text: str = record_dict["text_from_pdf"]
                        if "bookreview" in text.replace(" ", "").lower():
                            record_dict["ENTRYTYPE"] = "misc"
                            record_dict["note"] = "Book review"
                        if "erratum" in text.replace(" ", "").lower():
                            record_dict["ENTRYTYPE"] = "misc"
                            record_dict["note"] = "Erratum"
                        if "correction" in text.replace(" ", "").lower():
                            record_dict["ENTRYTYPE"] = "misc"
                            record_dict["note"] = "Correction"
                        if "contents" in text.replace(" ", "").lower():
                            record_dict["ENTRYTYPE"] = "misc"
                            record_dict["note"] = "Contents"
                        if "withdrawal" in text.replace(" ", "").lower():
                            record_dict["ENTRYTYPE"] = "misc"
                            record_dict["note"] = "Withdrawal"
                        del record_dict["text_from_pdf"]
                    # else:
                    #     print(f'text extraction error in {record_dict["ID"]}')
                    if "pages_in_file" in record_dict:
                        del record_dict["pages_in_file"]

                record_dict = {k: v for k, v in record_dict.items() if v is not None}
                record_dict = {k: v for k, v in record_dict.items() if v != "NA"}

                # add details based on path
                record_dict = self.__update_fields_based_on_pdf_dirs(
                    record_dict=record_dict, params=self.settings.search_parameters
                )

        except colrev_exceptions.TEIException:
            pass

        return record_dict

    def __fix_filenames(self) -> None:
        overall_pdfs = self.pdfs_path.glob("**/*.pdf")
        for pdf in overall_pdfs:
            if "  " in str(pdf):
                pdf.rename(str(pdf).replace("  ", " "))

    def __skip_broken_filepaths(
        self,
        search_operation: colrev.ops.search.Search,
        pdfs_to_index: typing.List[Path],
    ) -> typing.List[Path]:
        broken_filepaths = [str(x) for x in pdfs_to_index if ";" in str(x)]
        if len(broken_filepaths) > 0:
            broken_filepath_str = "\n ".join(broken_filepaths)
            search_operation.review_manager.logger.error(
                f'skipping PDFs with ";" in filepath: \n{broken_filepath_str}'
            )
            pdfs_to_index = [x for x in pdfs_to_index if str(x) not in broken_filepaths]

        filepaths_to_skip = [
            str(x)
            for x in pdfs_to_index
            if "_ocr.pdf" == str(x)[-8:]
            or "_wo_cp.pdf" == str(x)[-10:]
            or "_wo_lp.pdf" == str(x)[-10:]
            or "_backup.pdf" == str(x)[-11:]
        ]
        if len(filepaths_to_skip) > 0:
            fp_to_skip_str = "\n ".join(filepaths_to_skip)
            search_operation.review_manager.logger.info(
                f"Skipping PDFs with _ocr.pdf/_wo_cp.pdf: {fp_to_skip_str}"
            )
            pdfs_to_index = [
                x for x in pdfs_to_index if str(x) not in filepaths_to_skip
            ]
        return pdfs_to_index

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if source.source_identifier != self.source_identifier:
            raise colrev_exceptions.InvalidQueryException(
                f"Invalid source_identifier: {source.source_identifier} "
                f"(should be {self.source_identifier})"
            )

        if "subdir_pattern" in source.search_parameters:
            if source.search_parameters["subdir_pattern"] != [
                "NA",
                "volume_number",
                "year",
                "volume",
            ]:
                raise colrev_exceptions.InvalidQueryException(
                    "subdir_pattern not in [NA, volume_number, year, volume]"
                )

        if "sub_dir_pattern" in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "sub_dir_pattern: deprecated. use subdir_pattern"
            )

        if "scope" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "path" not in source.search_parameters["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "path required in search_parameters/scope"
            )
        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __add_md_string(self, *, record_dict: dict) -> dict:

        md_copy = record_dict.copy()
        try:
            fsize = str(
                (self.review_manager.path / Path(record_dict["file"])).stat().st_size
            )
        except FileNotFoundError:
            fsize = "NOT_FOUND"
        for key in ["ID", "grobid-version", "file"]:
            if key in md_copy:
                md_copy.pop(key)
        md_string = ",".join([f"{k}:{v}" for k, v in md_copy.items()])
        record_dict["md_string"] = str(fsize) + md_string
        return record_dict

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of a PDF directory (based on GROBID)"""

        # pylint: disable=too-many-locals

        feed_file = self.settings.filename

        self.__fix_filenames()

        self.__remove_records_if_pdf_no_longer_exists(search_operation=search_operation)

        available_ids = {}
        max_id = 1
        if not feed_file.is_file():
            records = {}
        else:
            with open(feed_file, encoding="utf8") as bibtex_file:
                records = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )

            available_ids = {
                x["file"]: x["ID"] for x in records.values() if "file" in x
            }
            max_id = (
                max([int(x["ID"]) for x in records.values() if x["ID"].isdigit()] + [1])
                + 1
            )

        overall_pdfs = [
            x.relative_to(search_operation.review_manager.path)
            for x in self.pdfs_path.glob("**/*.pdf")
        ]

        pdfs_to_index = list(
            set(overall_pdfs).difference({Path(x) for x in available_ids})
        )

        if search_operation.review_manager.force_mode:  # i.e., reindex all
            search_operation.review_manager.logger.info("Reindex all")
            pdfs_to_index = overall_pdfs

        search_operation.review_manager.logger.info(
            f"PDFs to index: {len(pdfs_to_index)}"
        )

        pdfs_to_index = self.__skip_broken_filepaths(
            search_operation=search_operation, pdfs_to_index=pdfs_to_index
        )

        if len(pdfs_to_index) == 0:
            search_operation.review_manager.logger.info("No additional PDFs to index")
            return

        grobid_service = search_operation.review_manager.get_grobid_service()
        grobid_service.start()

        batch_size = 20
        pdf_batches = [
            pdfs_to_index[i * batch_size : (i + 1) * batch_size]
            for i in range((len(pdfs_to_index) + batch_size - 1) // batch_size)
        ]

        for pdf_batch in pdf_batches:
            for record in records.values():
                record = self.__add_md_string(record_dict=record)

            for pdf_path in pdf_batch:
                new_record = self.__index_pdf(
                    search_operation=search_operation, pdf_path=pdf_path
                )

                new_record = self.__add_md_string(record_dict=new_record)

                # Note: identical md_string as a heuristic for duplicates
                potential_duplicates = [
                    r
                    for r in records.values()
                    if r["md_string"] == new_record["md_string"]
                    and not r["file"] == new_record["file"]
                ]
                if potential_duplicates:
                    search_operation.review_manager.logger.warning(
                        f" {colors.RED}skip record (PDF potential duplicate): "
                        f"{new_record['file']} {colors.END} "
                        f"({','.join([r['file'] for r in potential_duplicates])})"
                    )
                    continue

                if new_record["file"] in available_ids:
                    new_record["ID"] = available_ids[new_record["file"]]
                    records[available_ids[new_record["file"]]] = new_record
                else:
                    new_record["ID"] = f"{max_id}".rjust(10, "0")
                    max_id += 1
                    records[new_record["ID"]] = new_record

            for record in records.values():
                record.pop("md_string")

            if len(records) > 0:
                search_operation.save_feed_file(
                    records=records, feed_file=self.settings.filename
                )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for PDF directories (GROBID)"""

        result = {"confidence": 0.0}

        if filename.suffix == ".pdf" and not bws.BackwardSearchSource.heuristic(
            filename=filename, data=data
        ):
            result["confidence"] = 1.0
            return result

        return result

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for PDF directories (GROBID)"""

        for record in records.values():
            if "grobid-version" in record:
                del record["grobid-version"]

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for PDF directories (GROBID)"""

        # Typical error in old papers: title fields are equal to journal/booktitle fields
        if record.data.get("title", "no_title").lower() == record.data.get(
            "journal", "no_journal"
        ):
            record.remove_field(key="title", source="pdfs_dir_prepare")
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
        if record.data.get("title", "no_title").lower() == record.data.get(
            "booktitle", "no_booktitle"
        ):
            record.remove_field(key="title", source="pdfs_dir_prepare")
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )

        return record


if __name__ == "__main__":
    pass
