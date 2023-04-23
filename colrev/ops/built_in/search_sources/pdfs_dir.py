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
import colrev.ops.built_in.search_sources.crossref
import colrev.ops.built_in.search_sources.pdf_backward_search as bws
import colrev.ops.search
import colrev.qm.colrev_pdf_id
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

    # pylint: disable=too-many-instance-attributes

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "file"
    search_type = colrev.settings.SearchType.PDFS
    api_search_supported = True
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "PDF directory"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/pdfs_dir.md"
    )

    __doi_regex = re.compile(r"10\.\d{4,9}/[-._;/:A-Za-z0-9]*")
    __batch_size = 20

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.source_operation = source_operation

        if not source_operation.review_manager.in_ci_environment():
            self.pdf_preparation_operation = (
                source_operation.review_manager.get_pdf_prep_operation(
                    notify_state_transition_operation=False
                )
            )

        self.pdfs_path = source_operation.review_manager.path / Path(
            self.search_source.search_parameters["scope"]["path"]
        )
        self.review_manager = source_operation.review_manager

        self.subdir_pattern: re.Pattern = re.compile("")
        self.r_subdir_pattern: re.Pattern = re.compile("")
        if "subdir_pattern" in self.search_source.search_parameters.get("scope", {}):
            self.subdir_pattern = self.search_source.search_parameters["scope"][
                "subdir_pattern"
            ]
            source_operation.review_manager.logger.info(
                f"Activate subdir_pattern: {self.subdir_pattern}"
            )
            if self.subdir_pattern == "year":
                self.r_subdir_pattern = re.compile("([1-3][0-9]{3})")
            if self.subdir_pattern == "volume_number":
                self.r_subdir_pattern = re.compile("([0-9]{1,3})(_|/)([0-9]{1,2})")
            if self.subdir_pattern == "volume":
                self.r_subdir_pattern = re.compile("([0-9]{1,4})")
        self.crossref_connector = (
            colrev.ops.built_in.search_sources.crossref.CrossrefSearchSource(
                source_operation=source_operation
            )
        )

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

        if not self.search_source.filename.is_file():
            return

        with open(self.search_source.filename, encoding="utf8") as target_db:
            search_rd = search_operation.review_manager.dataset.load_records_dict(
                load_str=target_db.read()
            )

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
                        search_source=self.search_source.filename,
                    )
                    if updated:
                        continue
                to_remove.append(
                    f"{self.search_source.filename.name}/{record_dict['ID']}"
                )
                files_removed.append(record_dict["file"])

        search_rd = {
            x["ID"]: x
            for x in search_rd.values()
            if (search_operation.review_manager.path / Path(x["file"])).is_file()
        }

        if len(search_rd.values()) != 0:
            search_operation.review_manager.dataset.save_records_dict_to_file(
                records=search_rd, save_path=self.search_source.filename
            )

        if records:
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

            if self.subdir_pattern == "year":
                # Note: for year-patterns, we allow subfolders
                # (eg., conference tracks)
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    year = match.group(1)
                    record_dict["year"] = year

            elif self.subdir_pattern == "volume_number":
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

            elif self.subdir_pattern == "volume":
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

    def __get_grobid_metadata(
        self, *, search_operation: colrev.ops.search.Search, pdf_path: Path
    ) -> dict:
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
                    record_dict=record_dict, params=self.search_source.search_parameters
                )

        except colrev_exceptions.TEIException:
            pass

        return record_dict

    def __is_broken_filepath(
        self,
        pdf_path: Path,
    ) -> bool:
        if ";" in str(pdf_path):
            self.review_manager.logger.error(
                f'skipping PDF with ";" in filepath: \n{pdf_path}'
            )
            return True

        if (
            "_ocr.pdf" == str(pdf_path)[-8:]
            or "_wo_cp.pdf" == str(pdf_path)[-10:]
            or "_wo_lp.pdf" == str(pdf_path)[-10:]
            or "_backup.pdf" == str(pdf_path)[-11:]
        ):
            self.review_manager.logger.info(
                f"Skipping PDF with _ocr.pdf/_wo_cp.pdf: {pdf_path}"
            )
            return True

        return False

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
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

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def __index_pdf(
        self,
        *,
        pdf_path: Path,
        search_operation: colrev.ops.search.Search,
        pdfs_dir_feed: colrev.ops.search.GeneralOriginFeed,
        linked_pdf_paths: list,
        local_index: colrev.env.local_index.LocalIndex,
    ) -> dict:
        new_record: dict = {}

        if self.__is_broken_filepath(pdf_path=pdf_path):
            return new_record

        if search_operation.review_manager.force_mode:
            # i.e., reindex all
            pass
        else:
            # note: for curations, we want all pdfs indexed/merged separately,
            # in other projects, it is generally sufficient if the pdf is linked
            if not self.review_manager.settings.is_curated_masterdata_repo():
                if pdf_path in linked_pdf_paths:
                    # Otherwise: skip linked PDFs
                    return new_record

            if pdf_path in [
                Path(r["file"])
                for r in pdfs_dir_feed.feed_records.values()
                if "file" in r
            ]:
                return new_record

        self.review_manager.logger.info(f" extract metadata from {pdf_path}")
        try:
            if not self.review_manager.settings.is_curated_masterdata_repo():
                # retrieve_based_on_colrev_pdf_id
                colrev_pdf_id = colrev.qm.colrev_pdf_id.get_pdf_hash(
                    pdf_path=Path(pdf_path),
                    page_nr=1,
                    hash_size=32,
                )
                new_record = local_index.retrieve_based_on_colrev_pdf_id(
                    colrev_pdf_id="cpid1:" + colrev_pdf_id
                )
                new_record["file"] = str(pdf_path)
                # Note : an alternative to replacing all data with the curated version
                # is to just add the curation_ID
                # (and retrieve the curated metadata separately/non-redundantly)
            else:
                new_record = self.__get_grobid_metadata(
                    search_operation=search_operation, pdf_path=pdf_path
                )
        except (
            colrev_exceptions.PDFHashError,
            colrev_exceptions.RecordNotInIndexException,
        ):
            # otherwise, get metadata from grobid (indexing)
            new_record = self.__get_grobid_metadata(
                search_operation=search_operation, pdf_path=pdf_path
            )

        new_record = self.__add_md_string(record_dict=new_record)

        # Note: identical md_string as a heuristic for duplicates
        potential_duplicates = [
            r
            for r in pdfs_dir_feed.feed_records.values()
            if r["md_string"] == new_record["md_string"]
            and not r["file"] == new_record["file"]
        ]
        if potential_duplicates:
            self.review_manager.logger.warning(
                f" {colors.RED}skip record (PDF potential duplicate): "
                f"{new_record['file']} {colors.END} "
                f"({','.join([r['file'] for r in potential_duplicates])})"
            )
            return new_record

        try:
            pdfs_dir_feed.set_id(record_dict=new_record)
        except colrev_exceptions.NotFeedIdentifiableException:
            return new_record
        return new_record

    def __print_run_search_stats(
        self, *, records: dict, nr_added: int, nr_changed: int
    ) -> None:
        if nr_added > 0:
            self.review_manager.logger.info(
                f"{colors.GREEN}Retrieved {nr_added} records{colors.END}"
            )
        else:
            self.review_manager.logger.info(
                f"{colors.GREEN}No additional records retrieved{colors.END}"
            )

        if self.review_manager.force_mode:
            if nr_changed > 0:
                self.review_manager.logger.info(
                    f"{colors.GREEN}Updated {nr_changed} records{colors.END}"
                )
            else:
                if records:
                    self.review_manager.logger.info(
                        f"{colors.GREEN}Records (data/records.bib) up-to-date{colors.END}"
                    )

    def __get_pdf_batches(self) -> list:
        pdfs_to_index = [
            x.relative_to(self.review_manager.path)
            for x in self.pdfs_path.glob("**/*.pdf")
        ]

        pdf_batches = [
            pdfs_to_index[i * self.__batch_size : (i + 1) * self.__batch_size]
            for i in range(
                (len(pdfs_to_index) + self.__batch_size - 1) // self.__batch_size
            )
        ]
        return pdf_batches

    def __run_pdfs_dir_search(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        records: dict,
        pdfs_dir_feed: colrev.ops.search.GeneralOriginFeed,
        local_index: colrev.env.local_index.LocalIndex,
        linked_pdf_paths: list,
        rerun: bool,
    ) -> None:
        nr_added, nr_changed = 0, 0
        for pdf_batch in self.__get_pdf_batches():
            for record in pdfs_dir_feed.feed_records.values():
                record = self.__add_md_string(record_dict=record)

            for pdf_path in pdf_batch:
                new_record = self.__index_pdf(
                    pdf_path=pdf_path,
                    search_operation=search_operation,
                    pdfs_dir_feed=pdfs_dir_feed,
                    linked_pdf_paths=linked_pdf_paths,
                    local_index=local_index,
                )
                if new_record == {}:
                    continue

                prev_record_dict_version = pdfs_dir_feed.feed_records.get(
                    new_record["ID"], {}
                )

                added = pdfs_dir_feed.add_record(
                    record=colrev.record.Record(data=new_record),
                )
                if added:
                    nr_added += 1
                    self.__add_doi_from_pdf_if_not_available(record_dict=new_record)

                elif self.review_manager.force_mode:
                    # Note : only re-index/update
                    if search_operation.update_existing_record(
                        records=records,
                        record_dict=new_record,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    ):
                        nr_changed += 1

            for record in pdfs_dir_feed.feed_records.values():
                record.pop("md_string")

            pdfs_dir_feed.save_feed_file()

        self.__print_run_search_stats(
            records=records, nr_added=nr_added, nr_changed=nr_changed
        )

    def __add_doi_from_pdf_if_not_available(self, *, record_dict: dict) -> None:
        if "doi" in record_dict:
            return
        record = colrev.record.Record(data=record_dict)
        record.set_text_from_pdf(project_path=self.review_manager.path)
        res = re.findall(self.__doi_regex, record.data["text_from_pdf"])
        if res:
            record.data["doi"] = res[0].upper()
        del record.data["text_from_pdf"]

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of a PDF directory (based on GROBID)"""

        # Do not run in continuous-integration environment
        if search_operation.review_manager.in_ci_environment():
            return

        if search_operation.review_manager.force_mode:  # i.e., reindex all
            search_operation.review_manager.logger.info("Reindex all")

        # Removing records/origins for which PDFs were removed makes sense for curated repositories
        # In regular repositories, it may be confusing (e.g., if PDFs are renamed)
        # In these cases, we may simply print a warning instead of modifying/removing records?
        if self.review_manager.settings.is_curated_masterdata_repo():
            self.__remove_records_if_pdf_no_longer_exists(
                search_operation=search_operation
            )

        grobid_service = self.review_manager.get_grobid_service()
        grobid_service.start()

        local_index = self.review_manager.get_local_index()

        records = self.review_manager.dataset.load_records_dict()
        pdfs_dir_feed = self.search_source.get_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        linked_pdf_paths = [Path(r["file"]) for r in records.values() if "file" in r]

        self.__run_pdfs_dir_search(
            search_operation=search_operation,
            records=records,
            pdfs_dir_feed=pdfs_dir_feed,
            linked_pdf_paths=linked_pdf_paths,
            local_index=local_index,
            rerun=rerun,
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

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if query == "pdfs":
            filename = search_operation.get_unique_filename(file_path_string="pdfs")
            # pylint: disable=no-value-for-parameter
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.pdfs_dir",
                filename=filename,
                search_type=colrev.settings.SearchType.PDFS,
                search_parameters={"scope": {"path": "data/pdfs"}},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        return None

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

            if "doi" in record:
                try:
                    retrieved_record = self.crossref_connector.query_doi(
                        doi=record["doi"]
                    )

                    for key in [
                        "journal",
                        "booktitle",
                        "volume",
                        "number",
                        "year",
                        "pages",
                    ]:
                        if key in retrieved_record.data:
                            record[key] = retrieved_record.data[key]
                except colrev_exceptions.RecordNotFoundInPrepSourceException:
                    pass

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
