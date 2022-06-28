#! /usr/bin/env python
import importlib
import logging
import os
import re
import shutil
import subprocess
import sys
import typing
import unicodedata
from pathlib import Path

import imagehash
import timeout_decorator
import zope.interface
from lingua.builder import LanguageDetectorBuilder
from p_tqdm import p_map
from pdf2image import convert_from_path
from zope.interface.verify import verifyObject

from colrev_core.environment import LocalIndex
from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.record import Record
from colrev_core.record import RecordState


class PDFPreparationEndpoint(zope.interface.Interface):
    def prep_pdf(REVIEW_MANAGER, RECORD, PAD) -> dict:
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFCheckOCREndpoint:

    # TODO : test whether this is too slow:
    language_detector = (
        LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
    )

    @classmethod
    def __text_is_english(cls, *, text: str) -> bool:
        # Format: ENGLISH
        confidenceValues = cls.language_detector.compute_language_confidence_values(
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

    @classmethod
    def __apply_ocr(cls, *, REVIEW_MANAGER, record: dict, PAD: int) -> None:

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
        RECORD.add_data_provenance_hint(key="file", hint="pdf_processed with OCRMYPDF")
        RECORD.data["file"] = str(ocred_filename.relative_to(REVIEW_MANAGER.path))
        RECORD.get_text_from_pdf(project_path=REVIEW_MANAGER.path)

        return

    @classmethod
    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(cls, REVIEW_MANAGER, RECORD, PAD):
        if RecordState.pdf_imported != RECORD.data["colrev_status"]:
            return RECORD.data

        # TODO : allow for other languages in this and the following if statement
        if not cls.__text_is_english(text=RECORD.data["text_from_pdf"]):
            REVIEW_MANAGER.report_logger.info(f'apply_ocr({RECORD.data["ID"]})')
            cls.__apply_ocr(record=RECORD.data, PAD=PAD)

        if not cls.__text_is_english(text=RECORD.data["text_from_pdf"]):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD, " ")
                + "Validation error (OCR problems)"
            )
            REVIEW_MANAGER.report_logger.error(msg)

        if not cls.__text_is_english(text=RECORD.data["text_from_pdf"]):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD, " ")
                + "Validation error (Language not English)"
            )
            REVIEW_MANAGER.report_logger.error(msg)
            RECORD.add_data_provenance_hint(key="file", hint="pdf_language_not_english")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFCoverPageEndpoint:
    @classmethod
    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(cls, REVIEW_MANAGER, RECORD, PAD):

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
            original = REVIEW_MANAGER.path / Path(RECORD.data["file"])
            file_copy = REVIEW_MANAGER.path / Path(
                RECORD.data["file"].replace(".pdf", "_wo_cp.pdf")
            )
            shutil.copy(original, file_copy)
            RECORD.extract_pages(
                pages=coverpages,
                type="coverpage",
                project_path=REVIEW_MANAGER,
                save_to_path=cp_path,
            )
            REVIEW_MANAGER.report_logger.info(
                f'removed cover page for ({RECORD.data["ID"]})'
            )
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFLastPageEndpoint:
    @classmethod
    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(cls, REVIEW_MANAGER, RECORD, PAD):
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
            original = REVIEW_MANAGER.path / Path(RECORD.data["file"])
            file_copy = REVIEW_MANAGER.path / Path(
                RECORD.data["file"].replace(".pdf", "_wo_lp.pdf")
            )
            shutil.copy(original, file_copy)

            RECORD.extract_pages(
                pages=last_pages,
                type="last_page",
                project_path=REVIEW_MANAGER,
                save_to_path=lp_path,
            )
            REVIEW_MANAGER.report_logger.info(
                f'removed last page for ({RECORD.data["ID"]})'
            )
        return RECORD.data


@zope.interface.implementer(PDFPreparationEndpoint)
class PDFMetadataValidationEndpoint:
    @classmethod
    def validates_based_on_metadata(cls, *, REVIEW_MANAGER, RECORD) -> dict:
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

    @classmethod
    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(cls, REVIEW_MANAGER, RECORD, PAD):
        from colrev_core.environment import LocalIndex, RecordNotInIndexException

        if RecordState.pdf_imported != RECORD.data["colrev_status"]:
            return RECORD.data

        LOCAL_INDEX = LocalIndex()

        try:
            retrieved_record = LOCAL_INDEX.retrieve(record=RECORD.data)

            pdf_path = REVIEW_MANAGER.path / Path(RECORD.data["file"])
            current_cpid = RECORD.get_colrev_pdf_id(path=pdf_path)

            if "colrev_pdf_id" in retrieved_record:
                if retrieved_record["colrev_pdf_id"] == str(current_cpid):
                    REVIEW_MANAGER.logger.debug(
                        "validated pdf metadata based on local_index "
                        f"({RECORD.data['ID']})"
                    )
                    return RECORD.data
                else:
                    print("colrev_pdf_ids not matching")
        except RecordNotInIndexException:
            pass

        validation_info = cls.validates_based_on_metadata(
            REVIEW_MANAGER=REVIEW_MANAGER, RECORD=RECORD
        )
        if not validation_info["validates"]:
            for msg in validation_info["msgs"]:
                REVIEW_MANAGER.report_logger.error(msg)

            hints = ",".join([hint for hint in validation_info["pdf_prep_hints"]])
            RECORD.add_data_provenance_hint(key="file", hint=hints)
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

    @classmethod
    def __longer_with_appendix(cls, *, REVIEW_MANAGER, RECORD, nr_pages_metadata):
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

    @classmethod
    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(cls, REVIEW_MANAGER, RECORD, PAD):
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
            pages=[0, 1], project_path=REVIEW_MANAGER.path
        ).replace(" ", ""):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD - 1, " ")
                + " Not the full version of the paper"
            )
            REVIEW_MANAGER.report_logger.error(msg)
            RECORD.add_data_provenance_hint(key="file", hint="not_full_version")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            return RECORD.data

        pages_metadata = RECORD.data.get("pages", "NA")

        roman_pages_matched = re.match(cls.roman_pages_pattern, pages_metadata)
        if roman_pages_matched:
            start_page, end_page = roman_pages_matched.group().split("--")
            pages_metadata = f"{__romanToInt(s=start_page)}--{__romanToInt(s=end_page)}"
        roman_page_matched = re.match(cls.roman_page_pattern, pages_metadata)
        if roman_page_matched:
            page = roman_page_matched.group()
            pages_metadata = f"{__romanToInt(s=page)}"

        if "NA" == pages_metadata or not re.match(r"^\d+--\d+|\d+$", pages_metadata):
            msg = (
                f'{RECORD.data["ID"]}'.ljust(PAD - 1, " ")
                + "Could not validate completeness: no pages in metadata"
            )
            RECORD.add_data_provenance_hint(key="file", hint="no_pages_in_metadata")
            RECORD.data.update(colrev_status=RecordState.pdf_needs_manual_preparation)
            return RECORD.data

        nr_pages_metadata = __get_nr_pages_in_metadata(pages_metadata=pages_metadata)

        RECORD.get_pages_in_pdf(project_path=REVIEW_MANAGER.path)
        if nr_pages_metadata != RECORD.data["pages_in_file"]:
            if nr_pages_metadata == int(RECORD.data["pages_in_file"]) - 1:

                RECORD.add_data_provenance_hint(key="file", hint="more_pages_in_pdf")

            elif cls.__longer_with_appendix(
                REVIEW_MANAGER=REVIEW_MANAGER,
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

                RECORD.add_data_provenance_hint(
                    key="file", hint="nr_pages_not_matching"
                )
                RECORD.data.update(
                    colrev_status=RecordState.pdf_needs_manual_preparation
                )

        return RECORD.data


class PDF_Preparation(Process):
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

        self.pdf_prep_endpoints: typing.Dict[str, typing.Dict[str, typing.Any]] = {
            "pdf_check_ocr": {
                "endpoint": PDFCheckOCREndpoint,
            },
            "remove_coverpage": {
                "endpoint": PDFCoverPageEndpoint,
            },
            "remove_last_page": {
                "endpoint": PDFLastPageEndpoint,
            },
            "validate_pdf_metadata": {
                "endpoint": PDFMetadataValidationEndpoint,
            },
            "validate_completeness": {
                "endpoint": PDFCompletenessValidationEndpoint,
            },
        }

        list_custom_scripts = [
            s["endpoint"]
            for s in REVIEW_MANAGER.settings.pdf_prep.scripts
            if s["endpoint"] not in self.pdf_prep_endpoints
            and Path(s["endpoint"] + ".py").is_file()
        ]
        sys.path.append(".")  # to import custom scripts from the project dir
        for plugin_script in list_custom_scripts:
            custom_pdf_prep_script = importlib.import_module(
                plugin_script, "."
            ).CustomPDFPrepratation
            verifyObject(PDFPreparationEndpoint, custom_pdf_prep_script())
            self.pdf_prep_endpoints[plugin_script] = {
                "endpoint": custom_pdf_prep_script
            }

        # TODO : test the module pdf_get_scripts
        list_module_scripts = [
            s["endpoint"]
            for s in REVIEW_MANAGER.settings.pdf_prep.scripts
            if s["endpoint"] not in self.pdf_prep_endpoints
            and not Path(s["endpoint"] + ".py").is_file()
        ]
        for plugin_script in list_module_scripts:
            try:
                custom_pdf_prep_script = importlib.import_module(
                    plugin_script
                ).CustomPDFPrepratation
                verifyObject(PDFPreparationEndpoint, custom_pdf_prep_script())
                self.pdf_prep_endpoints[plugin_script] = {
                    "endpoint": custom_pdf_prep_script
                }
            except ModuleNotFoundError:
                pass
                # raise MissingDependencyError
                print(
                    "Dependency data_script " + f"{plugin_script} not found. "
                    "Please install it\n  pip install "
                    f"{plugin_script}"
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

            if PDF_PREP_SCRIPT["endpoint"] not in list(self.pdf_prep_endpoints.keys()):
                if self.verbose:
                    print(f"Error: endpoint not available: {PDF_PREP_SCRIPT}")
                continue

            try:
                endpoint = self.pdf_prep_endpoints[PDF_PREP_SCRIPT["endpoint"]]
                self.REVIEW_MANAGER.logger.debug(f"{endpoint}(...) called")

                self.REVIEW_MANAGER.report_logger.info(
                    f'{endpoint}({RECORD.data["ID"]}) called'
                )

                ENDPOINT = endpoint["endpoint"]()
                RECORD.data = ENDPOINT.prep_pdf(self.REVIEW_MANAGER, RECORD, PAD)
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
                    f'Error for {RECORD.data["ID"]} ' f"(in {endpoint} : {err})"
                )
                pass
                RECORD.data["colrev_status"] = RecordState.pdf_needs_manual_preparation

            except Exception as e:
                print(e)
                RECORD.data["colrev_status"] = RecordState.pdf_needs_manual_preparation
            failed = (
                RecordState.pdf_needs_manual_preparation == RECORD.data["colrev_status"]
            )
            msg = f'{endpoint}({RECORD.data["ID"]}):'.ljust(PAD, " ") + " "
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

            RECORD = Record(record)
            RECORD.data.update(colrev_status=RecordState.pdf_imported)
            RECORD.reset_pdf_provenance_hints()
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
        self.REVIEW_MANAGER.create_commit(msg="Update colrev_pdf_ids")
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

        pdf_prep_data_batch = self.__get_data()

        pdf_prep_batch = self.__batch(items=pdf_prep_data_batch["items"])

        if self.REVIEW_MANAGER.DEBUG_MODE:
            for item in pdf_prep_batch:
                record = item["record"]
                print(record["ID"])
                record = self.prepare_pdf(item)
                self.REVIEW_MANAGER.pp.pprint(record)
                self.REVIEW_MANAGER.REVIEW_DATASET.save_record_list_by_ID(
                    record_list=[record]
                )
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
