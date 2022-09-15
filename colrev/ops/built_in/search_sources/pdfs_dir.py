#! /usr/bin/env python
import re
import typing
from collections import Counter
from pathlib import Path

import zope.interface
from dacite import from_dict
from p_tqdm import p_map
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfparser import PDFParser

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.database_connectors
import colrev.ops.built_in.search_sources.pdf_backward_search as bws
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.env.package_manager.SearchSourcePackageInterface)
class PDFSearchSource:
    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "{{file}}"
    source_identifier_search = "{{file}}"
    search_mode = "all"

    def __init__(self, *, source_operation, settings: dict) -> None:

        if "sub_dir_pattern" in settings["search_parameters"]:
            if settings["search_parameters"]["sub_dir_pattern"] != [
                "NA",
                "volume_number",
                "year",
                "volume",
            ]:
                raise colrev_exceptions.InvalidQueryException(
                    "sub_dir_pattern not in [NA, volume_number, year, volume]"
                )

        if "scope" not in settings["search_parameters"]:
            raise colrev_exceptions.InvalidQueryException(
                "scope required in search_parameters"
            )
        if "path" not in settings["search_parameters"]["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "path required in search_parameters/scope"
            )

        self.settings = from_dict(data_class=self.settings_class, data=settings)
        self.source_operation = source_operation
        self.pdf_preparation_operation = (
            source_operation.review_manager.get_pdf_prep_operation(
                notify_state_transition_operation=False
            )
        )
        self.skip_duplicates = True
        self.pdfs_path = Path(self.settings.search_parameters["scope"]["path"])

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
            if f"{search_source}/{record_dict['ID']}" in r["colrev_origin"].split(";")
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

        search_operation.review_manager.logger.debug(
            "Checking for PDFs that no longer exist"
        )

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
                to_remove = to_remove + [
                    f"{self.settings.filename.name}/{id}" for id in search_rd.keys()
                ]

        search_rd = {x["ID"]: x for x in search_rd.values() if x_pdf_path.is_file()}
        if len(search_rd.values()) != 0:
            search_operation.review_manager.dataset.save_records_dict_to_file(
                records=search_rd, save_path=self.settings.filename
            )

        if search_operation.review_manager.dataset.records_file.is_file():
            # Note : origins may contain multiple links
            # but that should not be a major issue in indexing repositories

            to_remove = []
            source_ids = list(search_rd.keys())
            for record in records.values():
                if str(self.settings.filename.name) in record["colrev_origin"]:
                    if not any(
                        x.split("/")[1] in source_ids
                        for x in record["colrev_origin"].split(";")
                    ):
                        print("REMOVE " + record["colrev_origin"])
                        to_remove.append(record["colrev_origin"])

            for record_dict in to_remove:
                search_operation.review_manager.logger.debug(
                    f"remove from index (PDF path no longer exists): {record_dict}"
                )
                search_operation.review_manager.report_logger.info(
                    f"remove from index (PDF path no longer exists): {record_dict}"
                )

            records = {
                k: v for k, v in records.items() if v["colrev_origin"] not in to_remove
            }
            search_operation.review_manager.dataset.save_records_dict(records=records)
            search_operation.review_manager.dataset.add_record_changes()

    def __get_pdf_links(self, *, bib_file: Path) -> list:
        pdf_list = []
        if bib_file.is_file():
            with open(bib_file, encoding="utf8") as file:
                line = file.readline()
                while line:
                    if "file" == line.lstrip()[:4]:
                        pdf_file = line[line.find("{") + 1 : line.rfind("}")]
                        pdf_list.append(Path(pdf_file))
                    line = file.readline()
        return pdf_list

    def __update_fields_based_on_pdf_dirs(
        self, *, record_dict: dict, params: dict
    ) -> dict:

        if "params" not in params:
            return record_dict

        if "journal" in params["params"]:
            record_dict["journal"] = params["params"]["journal"]
            record_dict["ENTRYTYPE"] = "article"

        if "conference" in params["params"]:
            record_dict["booktitle"] = params["params"]["conference"]
            record_dict["ENTRYTYPE"] = "inproceedings"

        if "sub_dir_pattern" in params["params"]:
            sub_dir_pattern = params["params"]["sub_dir_pattern"]

            # Note : no file access here (just parsing the patterns)
            # no absolute paths needed
            partial_path = Path(record_dict["file"]).parents[0]
            if "year" == sub_dir_pattern:
                r_sub_dir_pattern = re.compile("([1-3][0-9]{3})")
                # Note: for year-patterns, we allow subfolders
                # (eg., conference tracks)
                match = r_sub_dir_pattern.search(str(partial_path))
                if match is not None:
                    year = match.group(1)
                    record_dict["year"] = year

            if "volume_number" == sub_dir_pattern:
                r_sub_dir_pattern = re.compile("([0-9]{1,3})(_|/)([0-9]{1,2})")
                match = r_sub_dir_pattern.search(str(partial_path))
                if match is not None:
                    volume = match.group(1)
                    number = match.group(3)
                    record_dict["volume"] = volume
                    record_dict["number"] = number
                else:
                    # sometimes, journals switch...
                    r_sub_dir_pattern = re.compile("([0-9]{1,3})")
                    match = r_sub_dir_pattern.search(str(partial_path))
                    if match is not None:
                        volume = match.group(1)
                        record_dict["volume"] = volume

            if "volume" == sub_dir_pattern:
                r_sub_dir_pattern = re.compile("([0-9]{1,4})")
                match = r_sub_dir_pattern.search(str(partial_path))
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

            environment_manager = (
                search_operation.review_manager.get_environment_manager()
            )
            # to allow users to update/reindex with newer version:
            record_dict["grobid-version"] = environment_manager.docker_images[
                "lfoppiano/grobid"
            ]
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

    def __load_records(
        self, *, search_operation: colrev.ops.search.Search
    ) -> typing.List[typing.Dict]:
        records = []
        if self.settings.filename.is_file():
            with open(self.settings.filename, encoding="utf8") as bibtex_file:
                feed_rd = search_operation.review_manager.dataset.load_records_dict(
                    load_str=bibtex_file.read()
                )
                records = list(feed_rd.values())
        return records

    def __fix_filenames(self) -> None:
        overall_pdfs = self.pdfs_path.glob("**/*.pdf")
        for pdf in overall_pdfs:
            if "  " in str(pdf):
                pdf.rename(str(pdf).replace("  ", " "))

    def __skip_duplicates(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        pdfs_to_index: typing.List[Path],
    ) -> typing.List[Path]:
        def get_pdf_cpid_path(path) -> typing.List[str]:
            try:
                cpid = colrev.record.Record.get_colrev_pdf_id(
                    review_manager=search_operation.review_manager, pdf_path=path
                )
            except colrev_exceptions.InvalidPDFException:
                cpid = "Exception"
            return [str(path), str(cpid)]

        search_operation.review_manager.logger.info(
            "Calculate PDF hashes to skip duplicates"
        )
        pdfs_path_cpid = p_map(get_pdf_cpid_path, pdfs_to_index)
        pdfs_cpid = [x[1] for x in pdfs_path_cpid if x[1] != "Exception"]
        duplicate_cpids = [
            item for item, count in Counter(pdfs_cpid).items() if count > 1
        ]
        duplicate_pdfs = [
            str(path) for path, cpid in pdfs_path_cpid if cpid in duplicate_cpids
        ]
        pdfs_to_index = [p for p in pdfs_to_index if str(p) not in duplicate_pdfs]
        return pdfs_to_index

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

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:

        records = self.__load_records(search_operation=search_operation)

        self.__fix_filenames()

        self.__remove_records_if_pdf_no_longer_exists(search_operation=search_operation)

        indexed_pdf_paths = self.__get_pdf_links(bib_file=self.settings.filename)
        overall_pdfs = self.pdfs_path.glob("**/*.pdf")
        pdfs_to_index = list(set(overall_pdfs).difference(set(indexed_pdf_paths)))

        print(len(pdfs_to_index))

        if self.skip_duplicates:
            pdfs_to_index = self.__skip_duplicates(
                search_operation=search_operation, pdfs_to_index=pdfs_to_index
            )
        print(len(pdfs_to_index))
        pdfs_to_index = self.__skip_broken_filepaths(
            search_operation=search_operation, pdfs_to_index=pdfs_to_index
        )

        if len(pdfs_to_index) == 0:
            search_operation.review_manager.logger.info("No additional PDFs to index")
            return

        grobid_service = search_operation.review_manager.get_grobid_service()
        grobid_service.start()

        batch_size = 10
        pdf_batches = [
            pdfs_to_index[i * batch_size : (i + 1) * batch_size]
            for i in range((len(pdfs_to_index) + batch_size - 1) // batch_size)
        ]

        record_id = int(
            search_operation.review_manager.dataset.get_next_id(
                bib_file=self.settings.filename
            )
        )
        input(len(list(overall_pdfs)))
        for pdf_batch in pdf_batches:

            new_records = []
            for pdf_path in pdf_batch:
                new_records.append(
                    self.__index_pdf(
                        search_operation=search_operation, pdf_path=pdf_path
                    )
                )
            # new_record_db.entries = p_map(self.index_pdf, pdf_batch)
            # p = Pool(ncpus=4)
            # new_records = p.map(index_pdf, pdf_batch)
            # alternatively:
            # new_records = p_map(index_pdf, pdf_batch)

            for new_r in new_records:
                indexed_pdf_paths.append(new_r["file"])
                record_id += 1
                new_r["ID"] = f"{record_id}".rjust(10, "0")

                if "colrev_status" in new_r:
                    if colrev.record.Record(data=new_r).masterdata_is_curated():
                        del new_r["colrev_status"]
                    else:
                        new_r["colrev_status"] = str(new_r["colrev_status"])

            records = records + new_records

            if len(records) > 0:
                records_dict = {r["ID"]: r for r in records}
                search_operation.save_feed_file(
                    records=records_dict, feed_file=self.settings.filename
                )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}

        if filename.suffix == ".pdf" and not bws.BackwardSearchSource.heuristic(
            filename=filename, data=data
        ):
            result["confidence"] = 1.0
            return result

        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:

        return record


if __name__ == "__main__":
    pass
