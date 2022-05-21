#! /usr/bin/env python
import io
import logging
import os
import re
import shutil
import subprocess
import typing
import unicodedata
from pathlib import Path

import imagehash
import timeout_decorator
from lingua.builder import LanguageDetectorBuilder
from p_tqdm import p_map
from pdf2image import convert_from_path
from pdfminer.converter import TextConverter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter

from colrev_core.environment import LocalIndex
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


class PDF_Preparation(Process):

    roman_pages_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?--"
        + r"M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$",
        re.IGNORECASE,
    )
    roman_page_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$", re.IGNORECASE
    )

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

        self.cp_path = LocalIndex.local_environment_path / Path(".coverpages")
        self.cp_path.mkdir(exist_ok=True)

        self.lp_path = LocalIndex.local_environment_path / Path(".lastpages")
        self.lp_path.mkdir(exist_ok=True)

        self.PDF_DIRECTORY = self.REVIEW_MANAGER.paths["PDF_DIRECTORY"]
        self.REPO_DIR = self.REVIEW_MANAGER.paths["REPO_DIR"]
        self.CPUS = 8

        self.language_detector = (
            LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
        )

    def __extract_text_by_page(self, *, record: dict, pages: list = None) -> str:

        text_list: list = []
        pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
        with open(pdf_path, "rb") as fh:
            try:
                for page in PDFPage.get_pages(
                    fh,
                    pagenos=pages,  # note: maybe skip potential cover pages?
                    caching=True,
                    check_extractable=True,
                ):
                    resource_manager = PDFResourceManager()
                    fake_file_handle = io.StringIO()
                    converter = TextConverter(resource_manager, fake_file_handle)
                    page_interpreter = PDFPageInterpreter(resource_manager, converter)
                    page_interpreter.process_page(page)

                    text = fake_file_handle.getvalue()
                    text_list += text

                    # close open handles
                    converter.close()
                    fake_file_handle.close()
            except TypeError:
                pass
        return "".join(text_list)

    def __get_pages_in_pdf(self, *, record: dict) -> dict:
        pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
        with open(pdf_path, "rb") as file:
            parser = PDFParser(file)
            document = PDFDocument(parser)
            pages_in_file = resolve1(document.catalog["Pages"])["Count"]
        record["pages_in_file"] = pages_in_file
        return record

    def get_text_from_pdf(self, *, record: dict, PAD: int = 30) -> dict:
        from pdfminer.pdfparser import PDFSyntaxError

        record["text_from_pdf"] = ""
        try:
            record = self.__get_pages_in_pdf(record=record)
            text = self.__extract_text_by_page(record=record, pages=[0, 1, 2])
            record["text_from_pdf"] = text

        except PDFSyntaxError:
            msg = (
                f'{record["file"]}'.ljust(PAD, " ")
                + "PDF reader error: check whether is a pdf"
            )
            self.REVIEW_MANAGER.report_logger.error(msg)
            self.REVIEW_MANAGER.logger.error(msg)
            RECORD = Record(data=record)
            RECORD.add_data_provenance_hint(field="file", hint="pdf_reader_error")
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        except PDFTextExtractionNotAllowed:
            msg = f'{record["file"]}'.ljust(PAD, " ") + "PDF reader error: protection"
            self.REVIEW_MANAGER.report_logger.error(msg)
            self.REVIEW_MANAGER.logger.error(msg)
            RECORD = Record(data=record)
            RECORD.add_data_provenance_hint(field="file", hint="pdf_protected")
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        except PDFSyntaxError:
            msg = f'{record["file"]}'.ljust(PAD, " ") + "PDFSyntaxError"
            self.REVIEW_MANAGER.report_logger.error(msg)
            self.REVIEW_MANAGER.logger.error(msg)
            RECORD = Record(data=record)
            RECORD.add_data_provenance_hint(field="file", hint="pdf_syntax_error")
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            pass
        return record

    def __text_is_english(self, *, text: str) -> bool:
        # Format: ENGLISH
        confidenceValues = self.language_detector.compute_language_confidence_values(
            text=text
        )
        for lang, conf in confidenceValues:
            if "ENGLISH" == lang.name:
                if conf > 0.85:
                    return True
            # else:
            #     print(text)
            #     print(conf)
        return False

    def __apply_ocr(self, *, record: dict, PAD: int) -> dict:

        pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
        ocred_filename = Path(pdf_path.replace(".pdf", "_ocr.pdf"))

        if pdf_path.is_file():
            orig_path = pdf_path.parents[0]
        else:
            orig_path = self.PDF_DIRECTORY

        options = f"--jobs {self.CPUS}"
        # if rotate:
        #     options = options + '--rotate-pages '
        # if deskew:
        #     options = options + '--deskew '
        docker_home_path = Path("/home/docker")
        command = (
            'docker run --rm --user "$(id -u):$(id -g)" -v "'
            + str(orig_path)
            + ':/home/docker" jbarlow83/ocrmypdf --force-ocr '
            + options
            + ' -l eng "'
            + str(docker_home_path / pdf_path.name)
            + '"  "'
            + str(docker_home_path / ocred_filename.name)
            + '"'
        )
        subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

        RECORD = Record(data=record)
        RECORD.add_data_provenance_hint(
            field="file", hint="pdf_processed with OCRMYPDF"
        )
        record = RECORD.get_data()
        record["file"] = str(ocred_filename.relative_to(self.REVIEW_MANAGER.path))
        record = self.get_text_from_pdf(record=record, PAD=PAD)

        return record

    @timeout_decorator.timeout(60, use_signals=False)
    def pdf_check_ocr(self, *, record: dict, PAD: int) -> dict:

        if RecordState.pdf_imported != record["colrev_status"]:
            return record

        # TODO : allow for other languages in this and the following if statement
        if not self.__text_is_english(text=record["text_from_pdf"]):
            self.REVIEW_MANAGER.report_logger.info(f'apply_ocr({record["ID"]})')
            record = self.__apply_ocr(record=record, PAD=PAD)

        if not self.__text_is_english(text=record["text_from_pdf"]):
            msg = f'{record["ID"]}'.ljust(PAD, " ") + "Validation error (OCR problems)"
            self.REVIEW_MANAGER.report_logger.error(msg)

        if not self.__text_is_english(text=record["text_from_pdf"]):
            msg = (
                f'{record["ID"]}'.ljust(PAD, " ")
                + "Validation error (Language not English)"
            )
            self.REVIEW_MANAGER.report_logger.error(msg)
            RECORD = Record(data=record)
            RECORD.add_data_provenance_hint(
                field="file", hint="pdf_language_not_english"
            )
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)

        return record

    def __rmdiacritics(self, *, char: str) -> str:
        """
        Return the base character of char, by "removing" any
        diacritics like accents or curls and strokes and the like.
        """
        try:
            desc = unicodedata.name(char)
        except ValueError:
            pass
            return ""
        cutoff = desc.find(" WITH ")
        if cutoff != -1:
            desc = desc[:cutoff]
            try:
                char = unicodedata.lookup(desc)
            except KeyError:
                pass  # removing "WITH ..." produced an invalid name
        return char

    def __remove_accents(self, *, text: str) -> str:
        try:
            nfkd_form = unicodedata.normalize("NFKD", text)
            wo_ac_str = [
                self.__rmdiacritics(char=c)
                for c in nfkd_form
                if not unicodedata.combining(c)
            ]
            wo_ac = "".join(wo_ac_str)
        except ValueError:
            wo_ac = text
            pass
        return wo_ac

    def validates_based_on_metadata(self, *, record: dict) -> dict:

        validation_info = {"msgs": [], "pdf_prep_hints": [], "validates": True}

        if "text_from_pdf" not in record:
            record = self.get_text_from_pdf(record=record)

        text = record["text_from_pdf"]
        text = text.replace(" ", "").replace("\n", "").lower()
        text = self.__remove_accents(text=text)
        text = re.sub("[^a-zA-Z ]+", "", text)

        title_words = re.sub("[^a-zA-Z ]+", "", record["title"]).lower().split()

        match_count = 0
        for title_word in title_words:
            if title_word in text:
                match_count += 1

        if "title" not in record or len(title_words) == 0:
            validation_info["msgs"].append(  # type: ignore
                f"{record['ID']}: title not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info
        if "author" not in record:
            validation_info["msgs"].append(  # type: ignore
                f"{record['ID']}: author not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "author_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info

        if match_count / len(title_words) < 0.9:
            validation_info["msgs"].append(  # type: ignore
                f"{record['ID']}: title not found in first pages"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_first_pages"
            )
            validation_info["validates"] = False

        text = text.replace("ue", "u").replace("ae", "a").replace("oe", "o")

        # Editorials often have no author in the PDF (or on the last page)
        if "editorial" not in title_words:

            match_count = 0
            for author_name in record.get("author", "").split(" and "):
                author_name = author_name.split(",")[0].lower().replace(" ", "")
                author_name = self.__remove_accents(text=author_name)
                author_name = (
                    author_name.replace("ue", "u").replace("ae", "a").replace("oe", "o")
                )
                author_name = re.sub("[^a-zA-Z ]+", "", author_name)
                if author_name in text:
                    match_count += 1

            if match_count / len(record.get("author", "").split(" and ")) < 0.8:

                validation_info["msgs"].append(  # type: ignore
                    f"{record['file']}: author not found in first pages"
                )
                validation_info["pdf_prep_hints"].append(  # type: ignore
                    "author_not_in_first_pages"
                )
                validation_info["validates"] = False

        return validation_info

    @timeout_decorator.timeout(60, use_signals=False)
    def validate_pdf_metadata(self, *, record: dict, PAD: int) -> dict:
        from colrev_core.environment import LocalIndex, RecordNotInIndexException

        if RecordState.pdf_imported != record["colrev_status"]:
            return record

        LOCAL_INDEX = LocalIndex()

        try:
            retrieved_record = LOCAL_INDEX.retrieve(record=record)

            pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
            current_cpid = self.get_colrev_pdf_id(path=pdf_path)

            if "colrev_pdf_id" in retrieved_record:
                if retrieved_record["colrev_pdf_id"] == str(current_cpid):
                    self.REVIEW_MANAGER.logger.debug(
                        f"validated pdf metadata based on local_index ({record['ID']})"
                    )
                    return record
                else:
                    print("colrev_pdf_ids not matching")
        except RecordNotInIndexException:
            pass

        validation_info = self.validates_based_on_metadata(record=record)
        if not validation_info["validates"]:
            RECORD = Record(data=record)
            for msg in validation_info["msgs"]:
                self.REVIEW_MANAGER.report_logger.error(msg)

            hints = ",".join([hint for hint in validation_info["pdf_prep_hints"]])
            RECORD.add_data_provenance_hint(field="file", hint=hints)
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)

        return record

    def __romanToInt(self, *, s):
        s = s.lower()
        roman = {
            "i": 1,
            "v": 5,
            "x": 10,
            "l": 50,
            "c": 100,
            "d": 500,
            "m": 1000,
            "iv": 4,
            "ix": 9,
            "xl": 40,
            "xc": 90,
            "cd": 400,
            "cm": 900,
        }
        i = 0
        num = 0
        while i < len(s):
            if i + 1 < len(s) and s[i : i + 2] in roman:
                num += roman[s[i : i + 2]]
                i += 2
            else:
                num += roman[s[i]]
                i += 1
        return num

    def __longer_with_appendix(self, *, record, nr_pages_metadata):
        if nr_pages_metadata < record["pages_in_file"] and nr_pages_metadata > 10:
            text = self.__extract_text_by_page(
                record=record,
                pages=[
                    record["pages_in_file"] - 3,
                    record["pages_in_file"] - 2,
                    record["pages_in_file"] - 1,
                ],
            )
            if "appendi" in text.lower():
                return True
        return False

    def __get_nr_pages_in_metadata(self, *, pages_metadata):
        if "--" in pages_metadata:
            nr_pages_metadata = (
                int(pages_metadata.split("--")[1])
                - int(pages_metadata.split("--")[0])
                + 1
            )
        else:
            nr_pages_metadata = 1
        return nr_pages_metadata

    @timeout_decorator.timeout(60, use_signals=False)
    def validate_completeness(self, *, record: dict, PAD: int) -> dict:

        if RecordState.pdf_imported != record["colrev_status"]:
            return record

        full_version_purchase_notice = (
            "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
        )
        if full_version_purchase_notice in self.__extract_text_by_page(
            record=record
        ).replace(" ", ""):
            msg = (
                f'{record["ID"]}'.ljust(PAD - 1, " ")
                + " Not the full version of the paper"
            )
            self.REVIEW_MANAGER.report_logger.error(msg)
            RECORD = Record(data=record)
            RECORD.add_data_provenance_hint(field="file", hint="not_full_version")
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            return record

        pages_metadata = record.get("pages", "NA")

        roman_pages_matched = re.match(self.roman_pages_pattern, pages_metadata)
        if roman_pages_matched:
            start_page, end_page = roman_pages_matched.group().split("--")
            pages_metadata = (
                f"{self.__romanToInt(s=start_page)}--{self.__romanToInt(s=end_page)}"
            )
        roman_page_matched = re.match(self.roman_page_pattern, pages_metadata)
        if roman_page_matched:
            page = roman_page_matched.group()
            pages_metadata = f"{self.__romanToInt(s=page)}"

        if "NA" == pages_metadata or not re.match(r"^\d+--\d+|\d+$", pages_metadata):
            msg = (
                f'{record["ID"]}'.ljust(PAD - 1, " ")
                + "Could not validate completeness: no pages in metadata"
            )
            RECORD = Record(data=record)
            RECORD.add_data_provenance_hint(field="file", hint="no_pages_in_metadata")
            record = RECORD.get_data()
            record.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            return record

        nr_pages_metadata = self.__get_nr_pages_in_metadata(
            pages_metadata=pages_metadata
        )

        record = self.__get_pages_in_pdf(record=record)
        if nr_pages_metadata != record["pages_in_file"]:
            if nr_pages_metadata == int(record["pages_in_file"]) - 1:

                RECORD = Record(data=record)
                RECORD.add_data_provenance_hint(field="file", hint="more_pages_in_pdf")
                record = RECORD.get_data()

            elif self.__longer_with_appendix(
                record=record, nr_pages_metadata=nr_pages_metadata
            ):
                pass
            else:

                msg = (
                    f'{record["ID"]}'.ljust(PAD, " ")
                    + f'Nr of pages in file ({record["pages_in_file"]}) '
                    + "not identical with record "
                    + f"({nr_pages_metadata} pages)"
                )

                RECORD = Record(data=record)
                RECORD.add_data_provenance_hint(
                    field="file", hint="nr_pages_not_matching"
                )
                record = RECORD.get_data()
                record.update(colrev_status=RecordState.pdf_needs_manual_preparation)

        return record

    def __get_coverpages(self, *, pdf):
        # for corrupted PDFs pdftotext seems to be more robust than
        # pdfReader.getPage(0).extractText()
        coverpages = []

        pdfReader = PdfFileReader(pdf, strict=False)
        if pdfReader.getNumPages() == 1:
            return coverpages

        first_page_average_hash_16 = imagehash.average_hash(
            convert_from_path(pdf, first_page=1, last_page=1)[0],
            hash_size=16,
        )

        # Note : to generate hashes from a directory containing single-page PDFs:
        # colrev pdf-prep --get_hashes path
        first_page_hashes = [
            "ffff83ff81ff81ffc3ff803f81ff80ffc03fffffffffffffffff96ff9fffffff",
            "ffffffffc0ffc781c007c007cfffc7ffffffffffffffc03fc007c003c827ffff",
            "84ff847ffeff83ff800783ff801f800180038fffffffffffbfff8007bffff83f",
            "83ff03ff03ff83ffffff807f807f9fff87ffffffffffffffffff809fbfffffff",
            "ffffffffc0ffc781c03fc01fffffffffffffffffffffc03fc01fc003ffffffff",
            "ffffffffc0ffc781c007c007cfffc7ffffffffffffffc03fc007c003ce27ffff",
            "ffffe7ffe3ffc3fffeff802780ff8001c01fffffffffffffffff80079ffffe3f",
            "ffffffffc0ffc781c00fc00fc0ffc7ffffffffffffffc03fc007c003cf27ffff",
            "ffffffffc0ffc781c007c003cfffcfffffffffffffffc03fc003c003cc27ffff",
            "ffffe7ffe3ffc3ffffff80e780ff80018001ffffffffffffffff93ff83ff9fff",
        ]

        if str(first_page_average_hash_16) in first_page_hashes:
            coverpages.append(0)

        res = subprocess.run(
            ["/usr/bin/pdftotext", pdf, "-f", "1", "-l", "1", "-enc", "UTF-8", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        page0 = res.stdout.decode("utf-8").replace(" ", "").replace("\n", "").lower()

        res = subprocess.run(
            ["/usr/bin/pdftotext", pdf, "-f", "2", "-l", "2", "-enc", "UTF-8", "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        page1 = res.stdout.decode("utf-8").replace(" ", "").replace("\n", "").lower()

        # input(page0)

        # scholarworks.lib.csusb first page
        if "followthisandadditionalworksat:https://scholarworks" in page0:
            coverpages.append(0)

        # Researchgate First Page
        if (
            "discussions,stats,andauthorprofilesforthispublicationat:"
            + "https://www.researchgate.net/publication"
            in page0
            or "discussions,stats,andauthorproﬁlesforthispublicationat:"
            + "https://www.researchgate.net/publication"
            in page0
        ):
            coverpages.append(0)

        # JSTOR  First Page
        if (
            "pleasecontactsupport@jstor.org.youruseofthejstorarchiveindicatesy"
            + "ouracceptanceoftheterms&conditionsofuse"
            in page0
            or "formoreinformationregardingjstor,pleasecontactsupport@jstor.org"
            in page0
        ):
            coverpages.append(0)

        # Emerald first page
        if (
            "emeraldisbothcounter4andtransfercompliant.theorganizationisapartnero"
            "fthecommitteeonpublicationethics(cope)andalsoworkswithporticoandthe"
            "lockssinitiativefordigitalarchivepreservation.*relatedcontentand"
            "downloadinformationcorrectattimeofdownload" in page0
        ):
            coverpages.append(0)

        # INFORMS First Page
        if (
            "thisarticlewasdownloadedby" in page0
            and "fulltermsandconditionsofuse:" in page0
        ) or (
            "thisarticlemaybeusedonlyforthepurposesofresearch" in page0
            and "abstract" not in page0
            and "keywords" not in page0
            and "abstract" in page1
            and "keywords" in page1
        ):
            coverpages.append(0)

        # AIS First Page
        if (
            "associationforinformationsystemsaiselectroniclibrary(aisel)" in page0
            and "abstract" not in page0
            and "keywords" not in page0
        ):
            coverpages.append(0)

        # Remove Taylor and Francis First Page
        if (
            "pleasescrolldownforarticle" in page0
            and "abstract" not in page0
            and "keywords" not in page0
        ) or (
            "viewrelatedarticles" in page0
            and "abstract" not in page0
            and "keywords" not in page0
        ):
            coverpages.append(0)
            if (
                "terms-and-conditions" in page1
                and "abstract" not in page1
                and "keywords" not in page1
            ):
                coverpages.append(1)

        return list(set(coverpages))

    def __extract_pages(self, *, record: dict, pages: list, type: str) -> None:
        pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
        pdfReader = PdfFileReader(pdf_path, strict=False)
        writer = PdfFileWriter()
        for i in range(0, pdfReader.getNumPages()):
            if i in pages:
                continue
            writer.addPage(pdfReader.getPage(i))
        with open(pdf_path, "wb") as outfile:
            writer.write(outfile)
        if type == "coverpage":
            writer_cp = PdfFileWriter()
            writer_cp.addPage(pdfReader.getPage(0))
            filepath = Path(pdf_path)
            with open(self.cp_path / filepath.name, "wb") as outfile:
                writer_cp.write(outfile)
        if type == "last_page":
            writer_lp = PdfFileWriter()
            writer_lp.addPage(pdfReader.getPage(pdfReader.getNumPages()))
            filepath = Path(pdf_path)
            with open(self.lp_path / filepath.name, "wb") as outfile:
                writer_lp.write(outfile)
        return

    @timeout_decorator.timeout(60, use_signals=False)
    def remove_coverpage(self, *, record: dict, PAD: int) -> dict:
        coverpages = self.__get_coverpages(pdf=record["file"])
        if [] == coverpages:
            return record
        if coverpages:
            original = self.REVIEW_MANAGER.path / Path(record["file"])
            file_copy = self.REVIEW_MANAGER.path / Path(
                record["file"].replace(".pdf", "_wo_cp.pdf")
            )
            shutil.copy(original, file_copy)
            self.__extract_pages(record=record, pages=coverpages, type="coverpage")
            self.REVIEW_MANAGER.report_logger.info(
                f'removed cover page for ({record["ID"]})'
            )
        return record

    def __get_last_pages(self, *, pdf):
        # for corrupted PDFs pdftotext seems to be more robust than
        # pdfReader.getPage(0).extractText()

        last_pages = []
        pdfReader = PdfFileReader(pdf, strict=False)
        last_page_nr = pdfReader.getNumPages()

        last_page_average_hash_16 = imagehash.average_hash(
            convert_from_path(pdf, first_page=last_page_nr, last_page=last_page_nr)[0],
            hash_size=16,
        )

        if last_page_nr == 1:
            return last_pages

        # Note : to generate hashes from a directory containing single-page PDFs:
        # colrev pdf-prep --get_hashes path
        last_page_hashes = [
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffff83ff83ff",
            "ffff80038007ffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "c3fbc003c003ffc3ff83ffc3ffffffffffffffffffffffffffffffffffffffff",
            "ffff80038007ffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "ffff80038001ffff7fff7fff7fff7fff7fff7fff7fff7fffffffffffffffffff",
            "ffff80008003ffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "ffff80038007ffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ]

        if str(last_page_average_hash_16) in last_page_hashes:
            last_pages.append(last_page_nr - 1)

        res = subprocess.run(
            [
                "/usr/bin/pdftotext",
                pdf,
                "-f",
                str(last_page_nr),
                "-l",
                str(last_page_nr),
                "-enc",
                "UTF-8",
                "-",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        last_page_text = (
            res.stdout.decode("utf-8").replace(" ", "").replace("\n", "").lower()
        )

        # ME Sharpe last page
        if (
            "propertyofm.e.sharpeinc.anditscontentmaynotbecopiedoremailedtomultiplesi"
            + "tesorpostedtoalistservwithoutthecopyrightholder"
            in last_page_text
        ):
            last_pages.append(last_page_nr - 1)

        return list(set(last_pages))

    def remove_last_page(self, *, record, PAD):

        last_pages = self.__get_last_pages(record["file"])
        if [] == last_pages:
            return record
        if last_pages:
            original = self.REVIEW_MANAGER.path / Path(record["file"])
            file_copy = self.REVIEW_MANAGER.path / Path(
                record["file"].replace(".pdf", "_wo_lp.pdf")
            )
            shutil.copy(original, file_copy)

            self.__extract_pages(record=record, pages=last_pages, type="last_page")
            self.REVIEW_MANAGER.report_logger.info(
                f'removed last page for ({record["ID"]})'
            )

        return record

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

        prep_scripts: typing.List[typing.Dict[str, typing.Any]] = [
            {"script": self.get_text_from_pdf, "params": [record, PAD]},
            {"script": self.pdf_check_ocr, "params": [record, PAD]},
            {"script": self.remove_coverpage, "params": [record, PAD]},
            {"script": self.remove_last_page, "params": [record, PAD]},
            {"script": self.validate_pdf_metadata, "params": [record, PAD]},
            {"script": self.validate_completeness, "params": [record, PAD]},
        ]

        original_filename = record["file"]

        # Note: if there are problems
        # colrev_status is set to pdf_needs_manual_preparation
        # if it remains 'imported', all preparation checks have passed
        self.REVIEW_MANAGER.report_logger.info(f'prepare({record["ID"]})')
        for prep_script in prep_scripts:
            try:
                # Note : the record should not be changed
                # if the prep_script throws an exception
                prepped_record = prep_script["script"](*prep_script["params"])
                if isinstance(prepped_record, dict):
                    record = prepped_record
                else:
                    record["colrev_status"] = RecordState.pdf_needs_manual_preparation
            except (
                subprocess.CalledProcessError,
                timeout_decorator.timeout_decorator.TimeoutError,
            ) as err:
                self.REVIEW_MANAGER.logger.error(
                    f'Error for {record["ID"]} '
                    f'(in {prep_script["script"].__name__} : {err})'
                )
                pass
                record["colrev_status"] = RecordState.pdf_needs_manual_preparation

            except Exception as e:
                print(e)
                record["colrev_status"] = RecordState.pdf_needs_manual_preparation

            failed = RecordState.pdf_needs_manual_preparation == record["colrev_status"]
            msg = (
                f'{prep_script["script"].__name__}({record["ID"]}):'.ljust(PAD, " ")
                + " "
            )
            msg += "fail" if failed else "pass"
            self.REVIEW_MANAGER.report_logger.info(msg)
            if failed:
                break

        # Each prep_scripts can create a new file
        # previous/temporary pdfs are deleted when the process is successful
        # The original PDF is never deleted automatically.
        # If successful, it is renamed to *_backup.pdf

        if RecordState.pdf_imported == record["colrev_status"]:
            record.update(colrev_status=RecordState.pdf_prepared)
            pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
            record.update(colrev_pdf_id=self.get_colrev_pdf_id(path=pdf_path))

            # colrev_status == pdf_imported : means successful
            # create *_backup.pdf if record["file"] was changed
            if original_filename != record["file"]:

                current_file = self.REVIEW_MANAGER.path / Path(record["file"])
                original_file = self.REVIEW_MANAGER.path / Path(original_filename)
                if current_file.is_file() and original_file.is_file():
                    backup_filename = self.REVIEW_MANAGER.path / Path(
                        original_filename.replace(".pdf", "_backup.pdf")
                    )
                    original_file.rename(backup_filename)
                    current_file.rename(original_filename)
                    record["file"] = str(
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
            target_fname = self.REVIEW_MANAGER.path / Path(f'{record["ID"]}.pdf')
            linked_file = self.REVIEW_MANAGER.path / Path(record["file"])

            if target_fname.name != linked_file.name:
                if target_fname.is_file():
                    os.remove(target_fname)
                linked_file.rename(target_fname)
                record["file"] = str(target_fname.relative_to(self.REVIEW_MANAGER.path))

            if not self.REVIEW_MANAGER.DEBUG_MODE:
                # Delete temporary PDFs for which processing has failed:
                if target_fname.is_file():
                    for fpath in self.PDF_DIRECTORY.glob("*.pdf"):
                        if record["ID"] in str(fpath) and fpath != target_fname:
                            os.remove(fpath)

            git_repo = item["REVIEW_MANAGER"].get_repo()
            git_repo.index.add([record["file"]])

        record = self.__cleanup_pdf_processing_fields(record=record)

        return record

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

        prep_data = {
            "nr_tasks": nr_tasks,
            "items": items,
        }
        self.REVIEW_MANAGER.logger.debug(self.REVIEW_MANAGER.pp.pformat(prep_data))
        return prep_data

    def __batch(self, *, items: dict):
        batch = []
        for item in items:

            # (Quick) fix if there are multiple files linked:
            if ";" in item.get("file", ""):
                item["file"] = item["file"].split(";")[0]
            batch.append(
                {
                    "record": item,
                }
            )
        return batch

    def __set_to_reprocess(self):

        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        for record in records.values():
            if RecordState.pdf_needs_manual_preparation != record["colrev_stauts"]:
                continue

            record.update(colrev_status=RecordState.pdf_imported)
            RECORD = Record(record)
            RECORD.reset_pdf_provenance_hints()
            record = RECORD.get_data()

        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        return

    def get_colrev_pdf_id(self, *, path: Path) -> str:
        cpid1 = "cpid1:" + str(
            imagehash.average_hash(
                convert_from_path(path, first_page=1, last_page=1)[0],
                hash_size=32,
            )
        )
        return cpid1

    def __update_colrev_pdf_ids(self, *, record: dict) -> dict:
        if "file" in record:
            pdf_path = self.REVIEW_MANAGER.path / Path(record["file"])
            record.update(colrev_pdf_id=self.get_colrev_pdf_id(path=pdf_path))
        return record

    def update_colrev_pdf_ids(self) -> None:
        self.REVIEW_MANAGER.logger.info("Update colrev_pdf_ids")
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        records_list = p_map(self.__update_colrev_pdf_ids, records.values())
        records = {r["ID"]: r for r in records_list}
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()
        self.REVIEW_MANAGER.create_commit(msg="Update colrev_pdf_ids")
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

        pdf_prep_data_batch = self.__get_data()

        pdf_prep_batch = self.__batch(items=pdf_prep_data_batch["items"])

        if self.REVIEW_MANAGER.DEBUG_MODE:
            for item in pdf_prep_batch:
                record = item["record"]
                print(record["ID"])
                record = self.prepare_pdf(item)
                self.REVIEW_MANAGER.save_record_list_by_ID(record_list=[record])
        else:
            pdf_prep_batch = p_map(self.prepare_pdf, pdf_prep_batch)

        self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
            record_list=pdf_prep_batch
        )

        # Multiprocessing mixes logs of different records.
        # For better readability:
        self.REVIEW_MANAGER.reorder_log(IDs=[x["ID"] for x in pdf_prep_batch])

        # Note: for formatting...
        records = self.REVIEW_MANAGER.REVIEW_DATASET.load_records_dict()
        self.REVIEW_MANAGER.REVIEW_DATASET.save_records_dict(records=records)
        self.REVIEW_MANAGER.REVIEW_DATASET.add_record_changes()

        self.REVIEW_MANAGER.create_commit(msg="Prepare PDFs", saved_args=saved_args)

        return


if __name__ == "__main__":
    pass
