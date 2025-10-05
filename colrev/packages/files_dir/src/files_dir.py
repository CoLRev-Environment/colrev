#! /usr/bin/env python
"""SearchSource: directory containing PDF files (based on GROBID)"""
from __future__ import annotations

import logging
import re
import typing
from pathlib import Path

import pymupdf
from pydantic import Field

import colrev.env.tei_parser
import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
import colrev.package_manager.package_base_classes as base_classes
import colrev.packages.pdf_backward_search.src.pdf_backward_search as bws
import colrev.record.record
import colrev.record.record_pdf
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.search_file
from colrev import utils
from colrev.constants import Colors
from colrev.constants import ENTRYTYPES
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.crossref.src.crossref_api import query_doi
from colrev.writer.write_utils import write_file

# pylint: disable=unused-argument
# pylint: disable=duplicate-code
# pylint: disable=too-many-instance-attributes


class FilesSearchSource(base_classes.SearchSourcePackageBaseClass):
    """Files directories (PDFs based on GROBID)"""

    CURRENT_SYNTAX_VERSION = "0.1.0"

    # pylint: disable=too-many-instance-attributes

    endpoint = "colrev.files_dir"
    source_identifier = Fields.FILE
    search_types = [SearchType.FILES]

    ci_supported: bool = Field(default=False)
    heuristic_status = SearchSourceHeuristicStatus.supported

    _batch_size = 20
    rerun: bool

    def __init__(
        self,
        *,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: typing.Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode

        self.search_source = search_file

        # self.review_manager.path /
        self.pdfs_path = Path(search_file.search_parameters["scope"]["path"])

        self.subdir_pattern: re.Pattern = re.compile("")
        self.r_subdir_pattern: re.Pattern = re.compile("")
        if "subdir_pattern" in self.search_source.search_parameters.get("scope", {}):
            self.subdir_pattern = self.search_source.search_parameters["scope"][
                "subdir_pattern"
            ]
            self.logger.info(f"Activate subdir_pattern: {self.subdir_pattern}")
            if self.subdir_pattern == Fields.YEAR:
                self.r_subdir_pattern = re.compile("([1-3][0-9]{3})")
            if self.subdir_pattern == "volume_number":
                self.r_subdir_pattern = re.compile("([0-9]{1,3})(_|/)([0-9]{1,2})")
            if self.subdir_pattern == Fields.VOLUME:
                self.r_subdir_pattern = re.compile("([0-9]{1,4})")

        self.local_index = colrev.env.local_index.LocalIndex()

    def _update_if_pdf_renamed(
        self,
        *,
        record_dict: dict,
        records: dict,
        search_results_path: Path,
    ) -> bool:
        updated = True
        not_updated = False

        c_rec_l = [
            r
            for r in records.values()
            if f"{search_results_path}/{record_dict['ID']}" in r[Fields.ORIGIN]
        ]
        if len(c_rec_l) == 1:
            c_rec = c_rec_l.pop()
            if "colrev_pdf_id" in c_rec:
                cpid = c_rec["colrev_pdf_id"]
                pdf_fp = self.review_manager.path / Path(record_dict[Fields.FILE])
                file_path = pdf_fp.parents[0]
                potential_pdfs = file_path.glob("*.pdf")

                for potential_pdf in potential_pdfs:
                    cpid_potential_pdf = colrev.record.record.Record.get_colrev_pdf_id(
                        potential_pdf,
                    )

                    if cpid == cpid_potential_pdf:
                        record_dict[Fields.FILE] = str(
                            potential_pdf.relative_to(self.review_manager.path)
                        )
                        c_rec[Fields.FILE] = str(
                            potential_pdf.relative_to(self.review_manager.path)
                        )
                        return updated
        return not_updated

    def _remove_records_if_pdf_no_longer_exists(self) -> None:
        # self.logger.debug(
        #     "Checking for PDFs that no longer exist"
        # )

        if not self.search_source.search_results_path.is_file():
            return

        search_rd = colrev.loader.load_utils.load(
            filename=self.search_source.search_results_path,
            logger=self.logger,
            unique_id_field="ID",
        )

        records = self.review_manager.dataset.load_records_dict()

        to_remove: typing.List[str] = []
        files_removed = []
        for record_dict in search_rd.values():
            x_file_path = self.review_manager.path / Path(record_dict[Fields.FILE])
            if not x_file_path.is_file():
                if records:
                    updated = self._update_if_pdf_renamed(
                        record_dict=record_dict,
                        records=records,
                        search_results_path=self.search_source.search_results_path,
                    )
                    if updated:
                        continue
                to_remove.append(
                    f"{self.search_source.search_results_path.name}/{record_dict['ID']}"
                )
                files_removed.append(record_dict[Fields.FILE])

        search_rd = {
            x[Fields.ID]: x
            for x in search_rd.values()
            if (self.review_manager.path / Path(x[Fields.FILE])).is_file()
        }

        if len(search_rd.values()) != 0:

            write_file(
                records_dict=search_rd, filename=self.search_source.search_results_path
            )

        if records:
            for record_dict in records.values():
                for origin_to_remove in to_remove:
                    if origin_to_remove in record_dict[Fields.ORIGIN]:
                        record_dict[Fields.ORIGIN].remove(origin_to_remove)
            if to_remove:
                self.logger.info(
                    f" {Colors.RED}Removed {len(to_remove)} records "
                    f"(PDFs no longer available){Colors.END}"
                )
                for file_removed in files_removed:
                    self.logger.info(" %s%s%s", Colors.RED, file_removed, Colors.END)
            records = {k: v for k, v in records.items() if v[Fields.ORIGIN]}
            self.review_manager.dataset.save_records_dict(records)

    def _update_fields_based_on_pdf_dirs(
        self, *, record_dict: dict, params: dict
    ) -> dict:
        if not self.subdir_pattern:
            return record_dict

        if Fields.JOURNAL in params["scope"]:
            record_dict[Fields.JOURNAL] = params["scope"][Fields.JOURNAL]
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE

        if "conference" in params["scope"]:
            record_dict[Fields.BOOKTITLE] = params["scope"]["conference"]
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS

        if self.subdir_pattern:
            # Note : no file access here (just parsing the patterns)
            # no absolute paths needed
            partial_path = Path(record_dict[Fields.FILE]).parents[0]

            if self.subdir_pattern == Fields.YEAR:
                # Note: for year-patterns, we allow subfolders
                # (eg., conference tracks)
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    year = match.group(1)
                    record_dict[Fields.YEAR] = year

            elif self.subdir_pattern == "volume_number":
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    volume = match.group(1)
                    number = match.group(3)
                    record_dict[Fields.VOLUME] = volume
                    record_dict[Fields.NUMBER] = number
                else:
                    # sometimes, journals switch...
                    r_subdir_pattern = re.compile("([0-9]{1,3})")
                    match = r_subdir_pattern.search(str(partial_path))
                    if match is not None:
                        volume = match.group(1)
                        record_dict[Fields.VOLUME] = volume

            elif self.subdir_pattern == Fields.VOLUME:
                match = self.r_subdir_pattern.search(str(partial_path))
                if match is not None:
                    volume = match.group(1)
                    record_dict[Fields.VOLUME] = volume

        return record_dict

    def _get_missing_fields_from_doc_info(self, *, record_dict: dict) -> None:
        file_path = self.review_manager.path / Path(record_dict[Fields.FILE])
        doc = pymupdf.Document(file_path)

        # pylint: disable=no-member
        if record_dict.get(Fields.TITLE, "NA") in ["NA", ""]:
            if "title" in doc.metadata:
                try:
                    record_dict[Fields.TITLE] = doc.metadata["title"]
                except UnicodeDecodeError:
                    pass
        if record_dict.get(Fields.AUTHOR, "NA") in ["NA", ""]:
            if "author" in doc.metadata:
                try:
                    pdf_md_author = doc.metadata["author"]
                    if (
                        "Mirko Janc" not in pdf_md_author
                        and "wendy" != pdf_md_author
                        and "yolanda" != pdf_md_author
                    ):
                        record_dict[Fields.AUTHOR] = pdf_md_author
                except UnicodeDecodeError:
                    pass

    def _get_grobid_metadata(self, *, file_path: Path) -> dict:

        try:
            record_dict = colrev.env.tei_parser.get_record_from_pdf(
                self.review_manager.path / file_path, add_doi_from_pdf=True
            )
            record_dict[Fields.FILE] = file_path

            self._get_missing_fields_from_doc_info(record_dict=record_dict)

            if Fields.ABSTRACT in record_dict:
                del record_dict[Fields.ABSTRACT]
            if Fields.KEYWORDS in record_dict:
                del record_dict[Fields.KEYWORDS]

            with pymupdf.open(file_path) as doc:
                pages_in_file = doc.page_count
                if pages_in_file < 6:
                    record = colrev.record.record_pdf.PDFRecord(
                        record_dict, path=self.review_manager.path
                    )
                    record.set_text_from_pdf(first_pages=True)
                    record_dict = record.get_data()
                    if Fields.TEXT_FROM_PDF in record_dict:
                        text: str = record_dict[Fields.TEXT_FROM_PDF]
                        if "bookreview" in text.replace(" ", "").lower():
                            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
                            record_dict["note"] = "Book review"
                        if "erratum" in text.replace(" ", "").lower():
                            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
                            record_dict["note"] = "Erratum"
                        if "correction" in text.replace(" ", "").lower():
                            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
                            record_dict["note"] = "Correction"
                        if "contents" in text.replace(" ", "").lower():
                            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
                            record_dict["note"] = "Contents"
                        if "withdrawal" in text.replace(" ", "").lower():
                            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC
                            record_dict["note"] = "Withdrawal"
                        del record_dict[Fields.TEXT_FROM_PDF]
                    # else:
                    #     print(f'text extraction error in {record_dict[Fields.ID]}')

                record_dict = {k: v for k, v in record_dict.items() if v is not None}
                record_dict = {k: v for k, v in record_dict.items() if v != "NA"}

                # add details based on path
                record_dict = self._update_fields_based_on_pdf_dirs(
                    record_dict=record_dict, params=self.search_source.search_parameters
                )

        except colrev_exceptions.TEIException:
            pass

        return record_dict

    def _is_broken_filepath(
        self,
        file_path: Path,
    ) -> bool:
        if ";" in str(file_path):
            self.logger.error(f'skipping PDF with ";" in filepath: \n{file_path}')
            return True

        if (
            "_ocr.pdf" == str(file_path)[-8:]
            or "_with_cp.pdf" == str(file_path)[-10:]
            or "_with_lp.pdf" == str(file_path)[-10:]
            or "_backup.pdf" == str(file_path)[-11:]
        ):
            self.logger.info(f"Skipping PDF with _ocr.pdf/_with_cp.pdf: {file_path}")
            return True

        return False

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""

        source = self.search_source

        self.logger.debug(f"Validate SearchSource {source.search_results_path}")

        assert source.search_type == SearchType.FILES

        if "subdir_pattern" in source.search_parameters:
            if source.search_parameters["subdir_pattern"] != [
                "NA",
                "volume_number",
                Fields.YEAR,
                Fields.VOLUME,
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
        self.logger.debug("SearchSource %s validated", source.search_results_path)

    def _add_md_string(self, *, record_dict: dict) -> dict:
        # To identify potential duplicates
        if Path(record_dict[Fields.FILE]).suffix != ".pdf":
            return record_dict

        md_copy = record_dict.copy()
        try:
            fsize = str(
                (self.review_manager.path / Path(record_dict[Fields.FILE]))
                .stat()
                .st_size
            )
        except FileNotFoundError:
            fsize = "NOT_FOUND"
        for key in [Fields.ID, Fields.GROBID_VERSION, Fields.FILE]:
            if key in md_copy:
                md_copy.pop(key)
        md_string = ",".join([f"{k}:{v}" for k, v in md_copy.items()])
        record_dict["md_string"] = str(fsize) + md_string
        return record_dict

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.record.Record:
        """Not implemented"""
        return record

    def _index_file(
        self,
        *,
        file_path: Path,
        files_dir_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        linked_file_paths: list,
    ) -> dict:
        if file_path.suffix == ".pdf":
            return self._index_pdf(
                file_path=file_path,
                files_dir_feed=files_dir_feed,
                linked_file_paths=linked_file_paths,
            )
        if file_path.suffix == ".mp4":
            return self._index_mp4(
                file_path=file_path,
                files_dir_feed=files_dir_feed,
                linked_file_paths=linked_file_paths,
            )
        raise NotImplementedError

    def _fix_grobid_errors(self, new_record: dict) -> None:
        # Fix common GROBID errors that would cause problems in deduplication

        # drop title if it is identical with journal
        if Fields.TITLE in new_record and Fields.JOURNAL in new_record:
            if new_record[Fields.TITLE] == new_record[Fields.JOURNAL]:
                new_record.pop(Fields.TITLE)
        # drop title if it starts with "doi:"
        if Fields.TITLE in new_record:
            if new_record[Fields.TITLE].lower().startswith("doi:"):
                new_record.pop(Fields.TITLE)

        # drop title with erroneous terms
        if Fields.TITLE in new_record:
            if any(
                x in new_record[Fields.TITLE].lower()
                for x in [
                    "papers must be in english",
                    "please contact",
                    "before submission",
                    "chairman of the editorial board",
                    "received his ph",
                    "received her ph",
                    "can be submitted to",
                ]
            ):
                new_record.pop(Fields.TITLE)
        # drop title based on erroneous list
        if Fields.TITLE in new_record:
            if new_record[Fields.TITLE].lower() in [
                "the international journal of information systems applications",
                "c ommunications of the a i s ssociation for nformation ystems",
                "communications of the association for information systems "
                + "communications of the association for information systems",
            ]:
                new_record.pop(Fields.TITLE)

        # drop title if longer than 200 characters
        if Fields.TITLE in new_record:
            if len(new_record[Fields.TITLE]) > 200:
                new_record.pop(Fields.TITLE)

        # drop title if it has more numbers than characters
        if Fields.TITLE in new_record:
            if sum(c.isdigit() for c in new_record[Fields.TITLE]) > sum(
                c.isalpha() for c in new_record[Fields.TITLE]
            ):
                new_record.pop(Fields.TITLE)

    def _index_pdf(
        self,
        *,
        file_path: Path,
        files_dir_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        linked_file_paths: list,
    ) -> dict:
        new_record: dict = {}
        relative_path = file_path.relative_to(self.review_manager.path)

        file_path_abs = self.review_manager.path / file_path
        if self._is_broken_filepath(file_path=relative_path):
            return new_record

        if not self.review_manager.force_mode:
            # note: for curations, we want all pdfs indexed/merged separately,
            # in other projects, it is generally sufficient if the pdf is linked
            if not self.review_manager.settings.is_curated_masterdata_repo():
                if file_path in linked_file_paths:
                    # Otherwise: skip linked PDFs
                    return new_record

        if not self.rerun:

            if relative_path in [
                Path(r[Fields.FILE])
                for r in files_dir_feed.feed_records.values()
                if Fields.FILE in r
            ]:
                return new_record
        # otherwise: reindex all

        self.logger.info(" extract metadata from %s", relative_path)
        try:
            if not self.review_manager.settings.is_curated_masterdata_repo():
                # retrieve_based_on_colrev_pdf_id
                colrev_pdf_id = colrev.record.record.Record.get_colrev_pdf_id(
                    pdf_path=file_path_abs
                )
                new_record_object = self.local_index.retrieve_based_on_colrev_pdf_id(
                    colrev_pdf_id=colrev_pdf_id
                )
                new_record = new_record_object.data
                # Note : an alternative to replacing all data with the curated version
                # is to just add the curation_ID
                # (and retrieve the curated metadata separately/non-redundantly)
            else:
                new_record = self._get_grobid_metadata(file_path=file_path)
        except FileNotFoundError:
            self.logger.error("File not found: %s (skipping)", relative_path)
            return {}
        except (
            colrev_exceptions.PDFHashError,
            colrev_exceptions.RecordNotInIndexException,
        ):
            # otherwise, get metadata from grobid (indexing)
            new_record = self._get_grobid_metadata(file_path=file_path_abs)

        self._fix_grobid_errors(new_record)
        new_record[Fields.FILE] = str(relative_path)
        new_record = self._add_md_string(record_dict=new_record)

        # Note: identical md_string as a heuristic for duplicates
        potential_duplicates = [
            r
            for r in files_dir_feed.feed_records.values()
            if r["md_string"] == new_record["md_string"]
            and not r[Fields.FILE] == new_record[Fields.FILE]
        ]
        if potential_duplicates:
            self.logger.warning(
                " %sskip record (PDF potential duplicate):%s",
                Colors.RED,
                Colors.END,
            )

            self.logger.warning(
                " %s %s %s",
                Colors.RED,
                new_record["file"],
                Colors.END,
            )

            self.logger.warning(
                " %s %s %s",
                Colors.RED,
                ",".join([r["file"] for r in potential_duplicates]),
                Colors.END,
            )

        return new_record

    def _index_mp4(
        self,
        *,
        file_path: Path,
        files_dir_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        linked_file_paths: list,
    ) -> dict:
        record_dict = {Fields.ENTRYTYPE: "online", Fields.FILE: file_path}
        return record_dict

    def _get_file_batches(self) -> list:
        types = ("**/*.pdf", "**/*.mp4")
        files_grabbed: typing.List[Path] = []
        for suffix in types:
            files_grabbed.extend(self.pdfs_path.glob(suffix))

        files_to_index = [self.review_manager.path / x for x in files_grabbed]

        file_batches = [
            files_to_index[i * self._batch_size : (i + 1) * self._batch_size]
            for i in range(
                (len(files_to_index) + self._batch_size - 1) // self._batch_size
            )
        ]
        return file_batches

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-nested-blocks
    # pylint: disable=too-many-locals
    def _run_dir_search(
        self,
        *,
        files_dir_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        linked_file_paths: list,
    ) -> None:
        file_batches = self._get_file_batches()
        if not file_batches:
            files_dir_feed.save()
            return
        for i, file_batch in enumerate(file_batches):
            for record in files_dir_feed.feed_records.values():
                record = self._add_md_string(record_dict=record)

            for file_path in file_batch:
                new_record = self._index_file(
                    file_path=file_path,
                    files_dir_feed=files_dir_feed,
                    linked_file_paths=linked_file_paths,
                )
                if new_record == {}:
                    continue

                retrieved_record = colrev.record.record.Record(new_record)

                # Generally: add to feed but do not "update" records
                prev_feed_record = files_dir_feed.get_prev_feed_record(retrieved_record)
                files_dir_feed.add_record_to_feed(retrieved_record, prev_feed_record)

                if self.rerun:
                    # If rerun: fix_grobid_fields: in feed and records (if only pdf-file origin)
                    prefix = self.search_source.get_origin_prefix()
                    origin = f"{prefix}/{retrieved_record.data['ID']}"
                    for record_dict in files_dir_feed.records.values():
                        if origin in record_dict[Fields.ORIGIN]:
                            if len(record_dict[Fields.ORIGIN]) == 1:
                                self._fix_grobid_errors(record_dict)
                                if Fields.TITLE not in record_dict:
                                    record_dict[Fields.STATUS] = (
                                        RecordState.md_needs_manual_preparation
                                    )

            for record in files_dir_feed.feed_records.values():
                record.pop("md_string")

            last_round = i == len(file_batches) - 1
            files_dir_feed.save(skip_print=not last_round)

    def search(self, rerun: bool) -> None:
        """Run a search of a Files directory"""

        # TODO / TBD: replace review_manager?
        import colrev.review_manager

        self.review_manager = colrev.review_manager.ReviewManager()
        colrev.ops.check.CheckOperation(self.review_manager)

        self.rerun = rerun
        self._validate_source()

        # Do not run in continuous-integration environment
        if utils.in_ci_environment():
            raise colrev_exceptions.SearchNotAutomated("PDFs Dir Search not automated.")

        if self.review_manager.force_mode:  # i.e., reindex all
            self.logger.info("Reindex all")

        # Removing records/origins for which PDFs were removed makes sense for curated repositories
        # In regular repositories, it may be confusing (e.g., if PDFs are renamed)
        # In these cases, we may simply print a warning instead of modifying/removing records?
        if self.review_manager.settings.is_curated_masterdata_repo():
            self._remove_records_if_pdf_no_longer_exists()

        records = self.review_manager.dataset.load_records_dict()
        files_dir_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )

        linked_file_paths = [
            Path(r[Fields.FILE]) for r in records.values() if Fields.FILE in r
        ]

        self._run_dir_search(
            files_dir_feed=files_dir_feed,
            linked_file_paths=linked_file_paths,
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
        cls,
        params: str,
        path: Path,
        logger: typing.Optional[logging.Logger] = None,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        filename = utils.get_unique_filename(
            base_path=path,
            file_path_string="files",
        )
        # pylint: disable=no-value-for-parameter
        search_source = colrev.search_file.ExtendedSearchFile(
            version=cls.CURRENT_SYNTAX_VERSION,
            platform="colrev.files_dir",
            search_results_path=filename,
            search_type=SearchType.FILES,
            search_string="",
            comment="",
        )
        return search_source

    @classmethod
    def _update_based_on_doi(cls, *, record_dict: dict) -> None:
        if Fields.DOI not in record_dict:
            return
        try:
            retrieved_record = query_doi(
                doi=record_dict[Fields.DOI],
            )

            if not colrev.record.record_similarity.matches(
                colrev.record.record.Record(record_dict), retrieved_record
            ):
                del record_dict[Fields.DOI]
                return

            for key in [
                Fields.JOURNAL,
                Fields.BOOKTITLE,
                Fields.VOLUME,
                Fields.NUMBER,
                Fields.YEAR,
                Fields.PAGES,
            ]:
                if key in retrieved_record.data:
                    record_dict[key] = retrieved_record.data[key]
        except (colrev_exceptions.RecordNotFoundInPrepSourceException,):
            pass

    def load(self) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.search_results_path.suffix == ".bib":

            def field_mapper(record_dict: dict) -> None:
                if "note" in record_dict:
                    record_dict[f"{self.endpoint}.note"] = record_dict.pop("note")

            records = colrev.loader.load_utils.load(
                filename=self.search_source.search_results_path,
                unique_id_field="ID",
                field_mapper=field_mapper,
                logger=self.logger,
            )

            for record_dict in records.values():
                if Fields.GROBID_VERSION in record_dict:
                    del record_dict[Fields.GROBID_VERSION]

                self._update_based_on_doi(record_dict=record_dict)

            return records

        raise NotImplementedError

    def _fix_special_chars(self, *, record: colrev.record.record.Record) -> None:
        # We may also apply the following upon loading tei content
        if Fields.TITLE in record.data:
            record.data[Fields.TITLE] = (
                record.data[Fields.TITLE]
                .replace("n ˜", "ñ")
                .replace("u ´", "ú")
                .replace("ı ´", "í")
                .replace("a ´", "á")
                .replace("o ´", "ó")
                .replace("e ´", "é")
                .replace("c ¸", "ç")
                .replace("a ˜", "ã")
            )

        if Fields.AUTHOR in record.data:
            record.data[Fields.AUTHOR] = (
                record.data[Fields.AUTHOR]
                .replace("n ˜", "ñ")
                .replace("u ´", "ú")
                .replace("ı ´", "í")
                .replace("a ´", "á")
                .replace("o ´", "ó")
                .replace("e ´", "é")
                .replace("c ¸", "ç")
                .replace("a ˜", "ã")
            )

    def _fix_title_suffix(self, *, record: colrev.record.record.Record) -> None:
        if Fields.TITLE not in record.data:
            return
        if record.data[Fields.TITLE].endswith("Formula 1"):
            return
        if re.match(r"\d{4}$", record.data[Fields.TITLE]):
            return
        if record.data.get(Fields.TITLE, "").endswith(" 1"):
            record.data[Fields.TITLE] = record.data[Fields.TITLE][:-2]

    def _fix_special_outlets(self, *, record: colrev.record.record.Record) -> None:
        # Erroneous suffixes in IS conferences
        if record.data.get(Fields.BOOKTITLE, "") in [
            "Americas Conference on Information Systems",
            "International Conference on Information Systems",
            "European Conference on Information Systems",
            "Pacific Asia Conference on Information Systems",
        ]:
            for suffix in [
                "completed research paper",
                "completed research",
                "complete research",
                "full research paper",
                "research in progress",
                "(research in progress)",
            ]:
                if record.data[Fields.TITLE].lower().endswith(suffix):
                    record.data[Fields.TITLE] = record.data[Fields.TITLE][
                        : -len(suffix)
                    ].rstrip(" -:")
        # elif ...

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record.Record:
        """Source-specific preparation for files"""

        if Fields.FILE not in record.data:
            return record

        if Path(record.data[Fields.FILE]).suffix == ".pdf":

            record.format_if_mostly_upper(Fields.TITLE, case="sentence")
            record.format_if_mostly_upper(Fields.JOURNAL, case=Fields.TITLE)
            record.format_if_mostly_upper(Fields.BOOKTITLE, case=Fields.TITLE)
            record.format_if_mostly_upper(Fields.AUTHOR, case=Fields.TITLE)

            if Fields.AUTHOR in record.data:
                record.data[Fields.AUTHOR] = (
                    record.data[Fields.AUTHOR]
                    .replace(" and T I C L E I N F O, A. R", "")
                    .replace(" and Quarterly, Mis", "")
                )

            # Typical error in old papers: title fields are equal to journal/booktitle fields
            if (
                record.data.get(Fields.TITLE, "no_title").lower()
                == record.data.get(Fields.JOURNAL, "no_journal").lower()
            ):
                record.remove_field(key=Fields.TITLE, source="files_dir_prepare")
                record.set_status(RecordState.md_needs_manual_preparation)
            if record.data.get(Fields.TITLE, "no_title").lower() == record.data.get(
                Fields.BOOKTITLE, "no_booktitle"
            ):
                record.remove_field(key=Fields.TITLE, source="files_dir_prepare")
                record.set_status(RecordState.md_needs_manual_preparation)

            self._fix_title_suffix(record=record)
            self._fix_special_chars(record=record)
            self._fix_special_outlets(record=record)

            if record.data.get(Fields.TITLE, "").startswith("Microsoft Word"):
                record.data[Fields.TITLE] = FieldValues.UNKNOWN
                record.set_status(RecordState.md_needs_manual_preparation)
            if any(
                x in record.data.get(Fields.TITLE, "").lower()
                for x in [
                    "reproduced with permission",
                    "further reproduction prohibited",
                ]
            ):
                record.data[Fields.TITLE] = FieldValues.UNKNOWN
                record.set_status(RecordState.md_needs_manual_preparation)

        return record
