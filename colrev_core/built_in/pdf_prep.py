#! /usr/bin/env python
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

import imagehash
import timeout_decorator
import zope.interface
from dacite import from_dict
from lingua.builder import LanguageDetectorBuilder
from pdf2image import convert_from_path

import colrev_core.exceptions as colrev_exceptions
from colrev_core.environment import LocalIndex
from colrev_core.process import DefaultSettings
from colrev_core.process import PDFPreparationEndpoint
from colrev_core.record import Record
from colrev_core.record import RecordState


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFCheckOCREndpoint:
    def __init__(self, *, PDF_PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    # TODO : test whether this is too slow:
    language_detector = (
        LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
    )

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

    def __apply_ocr(self, *, REVIEW_MANAGER, record: dict, PAD: int) -> None:

        pdf_path = REVIEW_MANAGER.path / Path(record["file"])
        ocred_filename = Path(pdf_path.replace(".pdf", "_ocr.pdf"))

        if pdf_path.is_file():
            orig_path = pdf_path.parents[0]
        else:
            orig_path = REVIEW_MANAGER.paths["PDF_DIRECTORY"]

        # TODO : use variable self.CPUS
        options = f"--jobs {4}"
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
        RECORD.add_data_provenance_note(key="file", note="pdf_processed with OCRMYPDF")
        RECORD.data["file"] = str(ocred_filename.relative_to(REVIEW_MANAGER.path))
        RECORD.get_text_from_pdf(project_path=REVIEW_MANAGER.path)

        return

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(self, PDF_PREPARATION, RECORD, PAD):
        if RecordState.pdf_imported != RECORD.data["colrev_status"]:
            return RECORD.data

        # TODO : allow for other languages in this and the following if statement
        if not self.__text_is_english(text=RECORD.data["text_from_pdf"]):
            PDF_PREPARATION.REVIEW_MANAGER.report_logger.info(
                f'apply_ocr({RECORD.data["ID"]})'
            )
            self.__apply_ocr(
                REVIEW_MANAGER=PDF_PREPARATION.REVIEW_MANAGER,
                record=RECORD.data,
                PAD=PAD,
            )

        if not self.__text_is_english(text=RECORD.data["text_from_pdf"]):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD, " ")
                + "Validation error (OCR problems)"
            )
            PDF_PREPARATION.REVIEW_MANAGER.report_logger.error(msg)

        if not self.__text_is_english(text=RECORD.data["text_from_pdf"]):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD, " ")
                + "Validation error (Language not English)"
            )
            PDF_PREPARATION.REVIEW_MANAGER.report_logger.error(msg)
            RECORD.add_data_provenance_note(key="file", note="pdf_language_not_english")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFCoverPageEndpoint:
    def __init__(self, *, PDF_PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(self, PDF_PREPARATION, RECORD, PAD):

        from PyPDF2 import PdfFileReader

        cp_path = LocalIndex.local_environment_path / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        def __get_coverpages(*, pdf):
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
            page0 = (
                res.stdout.decode("utf-8").replace(" ", "").replace("\n", "").lower()
            )

            res = subprocess.run(
                ["/usr/bin/pdftotext", pdf, "-f", "2", "-l", "2", "-enc", "UTF-8", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            page1 = (
                res.stdout.decode("utf-8").replace(" ", "").replace("\n", "").lower()
            )

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

        coverpages = __get_coverpages(pdf=RECORD.data["file"])
        if [] == coverpages:
            return RECORD.data
        if coverpages:
            original = PDF_PREPARATION.REVIEW_MANAGER.path / Path(RECORD.data["file"])
            file_copy = PDF_PREPARATION.REVIEW_MANAGER.path / Path(
                RECORD.data["file"].replace(".pdf", "_wo_cp.pdf")
            )
            shutil.copy(original, file_copy)
            RECORD.extract_pages(
                pages=coverpages,
                type="coverpage",
                project_path=PDF_PREPARATION.REVIEW_MANAGER,
                save_to_path=cp_path,
            )
            PDF_PREPARATION.REVIEW_MANAGER.report_logger.info(
                f'removed cover page for ({RECORD.data["ID"]})'
            )
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFLastPageEndpoint:
    def __init__(self, *, PDF_PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(self, PDF_PREPARATION, RECORD, PAD):
        from PyPDF2 import PdfFileReader

        lp_path = LocalIndex.local_environment_path / Path(".lastpages")
        lp_path.mkdir(exist_ok=True)

        def __get_last_pages(*, pdf):
            # for corrupted PDFs pdftotext seems to be more robust than
            # pdfReader.getPage(0).extractText()

            last_pages = []
            pdfReader = PdfFileReader(pdf, strict=False)
            last_page_nr = pdfReader.getNumPages()

            last_page_average_hash_16 = imagehash.average_hash(
                convert_from_path(pdf, first_page=last_page_nr, last_page=last_page_nr)[
                    0
                ],
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
                "propertyofm.e.sharpeinc.anditscontentmayno"
                + "tbecopiedoremailedtomultiplesi"
                + "tesorpostedtoalistservwithoutthecopyrightholder"
                in last_page_text
            ):
                last_pages.append(last_page_nr - 1)

            return list(set(last_pages))

        last_pages = __get_last_pages(pdf=RECORD.data["file"])
        if [] == last_pages:
            return RECORD.data
        if last_pages:
            original = PDF_PREPARATION.REVIEW_MANAGER.path / Path(RECORD.data["file"])
            file_copy = PDF_PREPARATION.REVIEW_MANAGER.path / Path(
                RECORD.data["file"].replace(".pdf", "_wo_lp.pdf")
            )
            shutil.copy(original, file_copy)

            RECORD.extract_pages(
                pages=last_pages,
                type="last_page",
                project_path=PDF_PREPARATION.REVIEW_MANAGER,
                save_to_path=lp_path,
            )
            PDF_PREPARATION.REVIEW_MANAGER.report_logger.info(
                f'removed last page for ({RECORD.data["ID"]})'
            )
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFMetadataValidationEndpoint:
    def __init__(self, *, PDF_PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def validates_based_on_metadata(self, *, REVIEW_MANAGER, RECORD) -> dict:
        def __rmdiacritics(*, char: str) -> str:
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

        def __remove_accents(*, text: str) -> str:
            try:
                nfkd_form = unicodedata.normalize("NFKD", text)
                wo_ac_str = [
                    __rmdiacritics(char=c)
                    for c in nfkd_form
                    if not unicodedata.combining(c)
                ]
                wo_ac = "".join(wo_ac_str)
            except ValueError:
                wo_ac = text
                pass
            return wo_ac

        validation_info = {"msgs": [], "pdf_prep_hints": [], "validates": True}

        if "text_from_pdf" not in RECORD.data:
            RECORD.get_text_from_pdf(project_path=REVIEW_MANAGER.path)

        text = RECORD.data["text_from_pdf"]
        text = text.replace(" ", "").replace("\n", "").lower()
        text = __remove_accents(text=text)
        text = re.sub("[^a-zA-Z ]+", "", text)

        title_words = re.sub("[^a-zA-Z ]+", "", RECORD.data["title"]).lower().split()

        match_count = 0
        for title_word in title_words:
            if title_word in text:
                match_count += 1

        if "title" not in RECORD.data or len(title_words) == 0:
            validation_info["msgs"].append(  # type: ignore
                f"{RECORD.data['ID']}: title not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info
        if "author" not in RECORD.data:
            validation_info["msgs"].append(  # type: ignore
                f"{RECORD.data['ID']}: author not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "author_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info

        if match_count / len(title_words) < 0.9:
            validation_info["msgs"].append(  # type: ignore
                f"{RECORD.data['ID']}: title not found in first pages"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_first_pages"
            )
            validation_info["validates"] = False

        text = text.replace("ue", "u").replace("ae", "a").replace("oe", "o")

        # Editorials often have no author in the PDF (or on the last page)
        if "editorial" not in title_words:

            match_count = 0
            for author_name in RECORD.data.get("author", "").split(" and "):
                author_name = author_name.split(",")[0].lower().replace(" ", "")
                author_name = __remove_accents(text=author_name)
                author_name = (
                    author_name.replace("ue", "u").replace("ae", "a").replace("oe", "o")
                )
                author_name = re.sub("[^a-zA-Z ]+", "", author_name)
                if author_name in text:
                    match_count += 1

            if match_count / len(RECORD.data.get("author", "").split(" and ")) < 0.8:

                validation_info["msgs"].append(  # type: ignore
                    f"{RECORD.data['file']}: author not found in first pages"
                )
                validation_info["pdf_prep_hints"].append(  # type: ignore
                    "author_not_in_first_pages"
                )
                validation_info["validates"] = False

        return validation_info

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(self, PDF_PREPARATION, RECORD, PAD=40):
        from colrev_core.environment import LocalIndex

        if RecordState.pdf_imported != RECORD.data["colrev_status"]:
            return RECORD.data

        LOCAL_INDEX = LocalIndex()

        try:
            retrieved_record = LOCAL_INDEX.retrieve(record=RECORD.data)

            pdf_path = PDF_PREPARATION.REVIEW_MANAGER.path / Path(RECORD.data["file"])
            current_cpid = RECORD.get_colrev_pdf_id(path=pdf_path)

            if "colrev_pdf_id" in retrieved_record:
                if retrieved_record["colrev_pdf_id"] == str(current_cpid):
                    PDF_PREPARATION.REVIEW_MANAGER.logger.debug(
                        "validated pdf metadata based on local_index "
                        f"({RECORD.data['ID']})"
                    )
                    return RECORD.data
                else:
                    print("colrev_pdf_ids not matching")
        except colrev_exceptions.RecordNotInIndexException:
            pass

        validation_info = self.validates_based_on_metadata(
            REVIEW_MANAGER=PDF_PREPARATION.REVIEW_MANAGER, RECORD=RECORD
        )
        if not validation_info["validates"]:
            for msg in validation_info["msgs"]:
                PDF_PREPARATION.REVIEW_MANAGER.report_logger.error(msg)

            notes = ",".join(validation_info["pdf_prep_hints"])
            RECORD.add_data_provenance_note(key="file", note=notes)
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)

        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFCompletenessValidationEndpoint:

    roman_pages_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?--"
        + r"M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$",
        re.IGNORECASE,
    )
    roman_page_pattern = re.compile(
        r"^M{0,3}(CM|CD|D?C{0,3})?(XC|XL|L?X{0,3})?(IX|IV|V?I{0,3})?$", re.IGNORECASE
    )

    def __init__(self, *, PDF_PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(data_class=DefaultSettings, data=SETTINGS)

    def __longer_with_appendix(self, *, REVIEW_MANAGER, RECORD, nr_pages_metadata):
        if nr_pages_metadata < RECORD.data["pages_in_file"] and nr_pages_metadata > 10:
            text = RECORD.extract_text_by_page(
                pages=[
                    RECORD.data["pages_in_file"] - 3,
                    RECORD.data["pages_in_file"] - 2,
                    RECORD.data["pages_in_file"] - 1,
                ],
                project_path=REVIEW_MANAGER.path,
            )
            if "appendi" in text.lower():
                return True
        return False

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(self, PDF_PREPARATION, RECORD, PAD):
        if RecordState.pdf_imported != RECORD.data["colrev_status"]:
            return RECORD.data

        def __romanToInt(*, s):
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

        def __get_nr_pages_in_metadata(*, pages_metadata):
            if "--" in pages_metadata:
                nr_pages_metadata = (
                    int(pages_metadata.split("--")[1])
                    - int(pages_metadata.split("--")[0])
                    + 1
                )
            else:
                nr_pages_metadata = 1
            return nr_pages_metadata

        full_version_purchase_notice = (
            "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
        )
        if full_version_purchase_notice in RECORD.extract_text_by_page(
            pages=[0, 1], project_path=PDF_PREPARATION.REVIEW_MANAGER.path
        ).replace(" ", ""):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD - 1, " ")
                + " Not the full version of the paper"
            )
            PDF_PREPARATION.REVIEW_MANAGER.report_logger.error(msg)
            RECORD.add_data_provenance_note(key="file", note="not_full_version")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            return RECORD.data

        pages_metadata = RECORD.data.get("pages", "NA")

        roman_pages_matched = re.match(self.roman_pages_pattern, pages_metadata)
        if roman_pages_matched:
            start_page, end_page = roman_pages_matched.group().split("--")
            pages_metadata = f"{__romanToInt(s=start_page)}--{__romanToInt(s=end_page)}"
        roman_page_matched = re.match(self.roman_page_pattern, pages_metadata)
        if roman_page_matched:
            page = roman_page_matched.group()
            pages_metadata = f"{__romanToInt(s=page)}"

        if "NA" == pages_metadata or not re.match(r"^\d+--\d+|\d+$", pages_metadata):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD - 1, " ")
                + "Could not validate completeness: no pages in metadata"
            )
            RECORD.add_data_provenance_note(key="file", note="no_pages_in_metadata")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            return RECORD.data

        nr_pages_metadata = __get_nr_pages_in_metadata(pages_metadata=pages_metadata)

        RECORD.get_pages_in_pdf(project_path=PDF_PREPARATION.REVIEW_MANAGER.path)
        if nr_pages_metadata != RECORD.data["pages_in_file"]:
            if nr_pages_metadata == int(RECORD.data["pages_in_file"]) - 1:

                RECORD.add_data_provenance_note(key="file", note="more_pages_in_pdf")

            elif self.__longer_with_appendix(
                REVIEW_MANAGER=PDF_PREPARATION.REVIEW_MANAGER,
                RECORD=RECORD,
                nr_pages_metadata=nr_pages_metadata,
            ):
                pass
            else:

                msg = (
                    f'{RECORD.data["ID"]}'.ljust(PAD, " ")
                    + f'Nr of pages in file ({RECORD.data["pages_in_file"]}) '
                    + "not identical with record "
                    + f"({nr_pages_metadata} pages)"
                )

                RECORD.add_data_provenance_note(
                    key="file", note="nr_pages_not_matching"
                )
                RECORD.data.update(
                    colrev_status=RecordState.pdf_needs_manual_preparation
                )

        return RECORD.data
