#! /usr/bin/env python
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from dacite import from_dict
from lingua.builder import LanguageDetectorBuilder
from PyPDF2 import PdfFileReader

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.process
import colrev.record


if TYPE_CHECKING:
    import colrev.ops.pdf_prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.process.PDFPrepEndpoint)
class PDFCheckOCREndpoint:
    """Prepare PDFs by checking and applying OCR (if necessary) based on OCRmyPDF"""

    settings_class = colrev.process.DefaultSettings

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    # TODO : test whether this is too slow:
    language_detector = (
        LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
    )

    def __text_is_english(self, *, text: str) -> bool:
        # Format: ENGLISH
        confidence_values = self.language_detector.compute_language_confidence_values(
            text=text
        )
        for lang, conf in confidence_values:
            if "ENGLISH" == lang.name:
                if conf > 0.85:
                    return True
            # else:
            #     print(text)
            #     print(conf)
        return False

    def __apply_ocr(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record_dict: dict,
        pad: int,  # pylint: disable=unused-argument
    ) -> None:

        pdf_path = review_manager.path / Path(record_dict["file"])
        ocred_filename = Path(str(pdf_path).replace(".pdf", "_ocr.pdf"))

        orig_path = (
            pdf_path.parents[0] if pdf_path.is_file() else review_manager.pdf_directory
        )

        # TODO : use variable self.cpus
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

        record = colrev.record.Record(data=record_dict)
        record.add_data_provenance_note(key="file", note="pdf_processed with OCRMYPDF")
        record.data["file"] = str(ocred_filename.relative_to(review_manager.path))
        record.set_text_from_pdf(project_path=review_manager.path)

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,
    ) -> dict:
        if colrev.record.RecordState.pdf_imported != record.data["colrev_status"]:
            return record.data

        # TODO : allow for other languages in this and the following if statement
        if not self.__text_is_english(text=record.data["text_from_pdf"]):
            pdf_prep_operation.review_manager.report_logger.info(
                f'apply_ocr({record.data["ID"]})'
            )
            self.__apply_ocr(
                review_manager=pdf_prep_operation.review_manager,
                record_dict=record.data,
                pad=pad,
            )

        if not self.__text_is_english(text=record.data["text_from_pdf"]):
            msg = (
                f'{record.data["ID"]}'.ljust(pad, " ")
                + "Validation error (OCR problems)"
            )
            pdf_prep_operation.review_manager.report_logger.error(msg)

        if not self.__text_is_english(text=record.data["text_from_pdf"]):
            msg = (
                f'{record.data["ID"]}'.ljust(pad, " ")
                + "Validation error (Language not English)"
            )
            pdf_prep_operation.review_manager.report_logger.error(msg)
            record.add_data_provenance_note(key="file", note="pdf_language_not_english")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )
        return record.data


@zope.interface.implementer(colrev.process.PDFPrepEndpoint)
class PDFCoverPageEndpoint:
    """Prepare PDFs by removing unnecessary cover pages (e.g. researchgate, publishers)"""

    settings_class = colrev.process.DefaultSettings

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:

        local_index = pdf_prep_operation.review_manager.get_local_index()
        cp_path = local_index.local_environment_path / Path(".coverpages")
        cp_path.mkdir(exist_ok=True)

        def __get_coverpages(*, pdf):
            # for corrupted PDFs pdftotext seems to be more robust than
            # pdf_reader.getPage(0).extractText()
            coverpages = []

            pdf_reader = PdfFileReader(pdf, strict=False)
            if pdf_reader.getNumPages() == 1:
                return coverpages

            pdf_hash_service = pdf_prep_operation.review_manager.get_pdf_hash_service()

            first_page_average_hash_16 = pdf_hash_service.get_pdf_hash(
                pdf_path=Path(pdf),
                page_nr=1,
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
                check=True,
            )
            page0 = (
                res.stdout.decode("utf-8").replace(" ", "").replace("\n", "").lower()
            )

            res = subprocess.run(
                ["/usr/bin/pdftotext", pdf, "-f", "2", "-l", "2", "-enc", "UTF-8", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
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
            ):
                coverpages.append(0)
            if (
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
            if ("pleasescrolldownforarticle" in page0) or (
                "viewrelatedarticles" in page0
            ):
                if "abstract" not in page0 and "keywords" not in page0:
                    coverpages.append(0)
                    if (
                        "terms-and-conditions" in page1
                        and "abstract" not in page1
                        and "keywords" not in page1
                    ):
                        coverpages.append(1)

            return list(set(coverpages))

        coverpages = __get_coverpages(pdf=record.data["file"])
        if not coverpages:
            return record.data
        if coverpages:
            original = pdf_prep_operation.review_manager.path / Path(
                record.data["file"]
            )
            file_copy = pdf_prep_operation.review_manager.path / Path(
                record.data["file"].replace(".pdf", "_wo_cp.pdf")
            )
            shutil.copy(original, file_copy)
            record.extract_pages(
                pages=coverpages,
                project_path=pdf_prep_operation.review_manager.path,
                save_to_path=cp_path,
            )
            pdf_prep_operation.review_manager.report_logger.info(
                f'removed cover page for ({record.data["ID"]})'
            )
        return record.data


@zope.interface.implementer(colrev.process.PDFPrepEndpoint)
class PDFLastPageEndpoint:
    """Prepare PDFs by removing unnecessary last pages (e.g. copyright notices, cited-by infos)"""

    settings_class = colrev.process.DefaultSettings

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:

        local_index = pdf_prep_operation.review_manager.get_local_index()
        lp_path = local_index.local_environment_path / Path(".lastpages")
        lp_path.mkdir(exist_ok=True)

        def __get_last_pages(*, pdf):
            # for corrupted PDFs pdftotext seems to be more robust than
            # pdf_reader.getPage(0).extractText()

            last_pages = []
            pdf_reader = PdfFileReader(pdf, strict=False)
            last_page_nr = pdf_reader.getNumPages()

            pdf_hash_service = pdf_prep_operation.review_manager.get_pdf_hash_service()

            last_page_average_hash_16 = pdf_hash_service.get_pdf_hash(
                pdf_path=Path(pdf),
                page_nr=last_page_nr,
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
                check=True,
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

        last_pages = __get_last_pages(pdf=record.data["file"])
        if not last_pages:
            return record.data
        if last_pages:
            original = pdf_prep_operation.review_manager.path / Path(
                record.data["file"]
            )
            file_copy = pdf_prep_operation.review_manager.path / Path(
                record.data["file"].replace(".pdf", "_wo_lp.pdf")
            )
            shutil.copy(original, file_copy)

            record.extract_pages(
                pages=last_pages,
                project_path=pdf_prep_operation.review_manager.path,
                save_to_path=lp_path,
            )
            pdf_prep_operation.review_manager.report_logger.info(
                f'removed last page for ({record.data["ID"]})'
            )
        return record.data


@zope.interface.implementer(colrev.process.PDFPrepEndpoint)
class PDFMetadataValidationEndpoint:
    """Prepare PDFs by validating it against its associated metadata"""

    settings_class = colrev.process.DefaultSettings

    def __init__(
        self,
        *,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def validates_based_on_metadata(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.Record,
    ) -> dict:

        validation_info = {"msgs": [], "pdf_prep_hints": [], "validates": True}

        if "text_from_pdf" not in record.data:
            record.set_text_from_pdf(project_path=review_manager.path)

        text = record.data["text_from_pdf"]
        text = text.replace(" ", "").replace("\n", "").lower()
        text = colrev.env.utils.remove_accents(input_str=text)
        text = re.sub("[^a-zA-Z ]+", "", text)

        title_words = re.sub("[^a-zA-Z ]+", "", record.data["title"]).lower().split()

        match_count = 0
        for title_word in title_words:
            if title_word in text:
                match_count += 1

        if "title" not in record.data or len(title_words) == 0:
            validation_info["msgs"].append(  # type: ignore
                f"{record.data['ID']}: title not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info
        if "author" not in record.data:
            validation_info["msgs"].append(  # type: ignore
                f"{record.data['ID']}: author not in record"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "author_not_in_record"
            )
            validation_info["validates"] = False
            return validation_info

        if match_count / len(title_words) < 0.9:
            validation_info["msgs"].append(  # type: ignore
                f"{record.data['ID']}: title not found in first pages"
            )
            validation_info["pdf_prep_hints"].append(  # type: ignore
                "title_not_in_first_pages"
            )
            validation_info["validates"] = False

        text = text.replace("ue", "u").replace("ae", "a").replace("oe", "o")

        # Editorials often have no author in the PDF (or on the last page)
        if "editorial" not in title_words:

            match_count = 0
            for author_name in record.data.get("author", "").split(" and "):
                author_name = author_name.split(",")[0].lower().replace(" ", "")
                author_name = colrev.env.utils.remove_accents(input_str=author_name)
                author_name = (
                    author_name.replace("ue", "u").replace("ae", "a").replace("oe", "o")
                )
                author_name = re.sub("[^a-zA-Z ]+", "", author_name)
                if author_name in text:
                    match_count += 1

            if match_count / len(record.data.get("author", "").split(" and ")) < 0.8:

                validation_info["msgs"].append(  # type: ignore
                    f"{record.data['file']}: author not found in first pages"
                )
                validation_info["pdf_prep_hints"].append(  # type: ignore
                    "author_not_in_first_pages"
                )
                validation_info["validates"] = False

        return validation_info

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad=40,  # pylint: disable=unused-argument
    ) -> dict:

        if colrev.record.RecordState.pdf_imported != record.data["colrev_status"]:
            return record.data

        local_index = pdf_prep_operation.review_manager.get_local_index()

        try:
            retrieved_record = local_index.retrieve(record_dict=record.data)

            pdf_path = pdf_prep_operation.review_manager.path / Path(
                record.data["file"]
            )
            current_cpid = record.get_colrev_pdf_id(
                review_manager=pdf_prep_operation.review_manager, pdf_path=pdf_path
            )

            if "colrev_pdf_id" in retrieved_record:
                if retrieved_record["colrev_pdf_id"] == str(current_cpid):
                    pdf_prep_operation.review_manager.logger.debug(
                        "validated pdf metadata based on local_index "
                        f"({record.data['ID']})"
                    )
                    return record.data
                print("colrev_pdf_ids not matching")
        except colrev_exceptions.RecordNotInIndexException:
            pass

        validation_info = self.validates_based_on_metadata(
            review_manager=pdf_prep_operation.review_manager, record=record
        )
        if not validation_info["validates"]:
            for msg in validation_info["msgs"]:
                pdf_prep_operation.review_manager.report_logger.error(msg)

            notes = ",".join(validation_info["pdf_prep_hints"])
            record.add_data_provenance_note(key="file", note=notes)
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )

        return record.data


@zope.interface.implementer(colrev.process.PDFPrepEndpoint)
class PDFCompletenessValidationEndpoint:
    """Prepare PDFs by validating its completeness (based on the number of pages)"""

    settings_class = colrev.process.DefaultSettings

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
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def __longer_with_appendix(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
        record: colrev.record.Record,
        nr_pages_metadata: int,
    ) -> bool:
        if 10 < nr_pages_metadata < record.data["pages_in_file"]:
            text = record.extract_text_by_page(
                pages=[
                    record.data["pages_in_file"] - 3,
                    record.data["pages_in_file"] - 2,
                    record.data["pages_in_file"] - 1,
                ],
                project_path=review_manager.path,
            )
            if "appendi" in text.lower():
                return True
        return False

    @timeout_decorator.timeout(60, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,
    ) -> dict:
        if colrev.record.RecordState.pdf_imported != record.data["colrev_status"]:
            return record.data

        def __roman_to_int(*, s):
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

        def __get_nr_pages_in_metadata(*, pages_metadata) -> int:
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
        if full_version_purchase_notice in record.extract_text_by_page(
            pages=[0, 1], project_path=pdf_prep_operation.review_manager.path
        ).replace(" ", ""):
            msg = (
                f'{record.data["ID"]}'.ljust(pad - 1, " ")
                + " Not the full version of the paper"
            )
            pdf_prep_operation.review_manager.report_logger.error(msg)
            record.add_data_provenance_note(key="file", note="not_full_version")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )
            return record.data

        pages_metadata = record.data.get("pages", "NA")

        roman_pages_matched = re.match(self.roman_pages_pattern, pages_metadata)
        if roman_pages_matched:
            start_page, end_page = roman_pages_matched.group().split("--")
            pages_metadata = (
                f"{__roman_to_int(s=start_page)}--{__roman_to_int(s=end_page)}"
            )
        roman_page_matched = re.match(self.roman_page_pattern, pages_metadata)
        if roman_page_matched:
            page = roman_page_matched.group()
            pages_metadata = f"{__roman_to_int(s=page)}"

        if "NA" == pages_metadata or not re.match(r"^\d+--\d+|\d+$", pages_metadata):
            msg = (
                f'{record.data["ID"]}'.ljust(pad - 1, " ")
                + "Could not validate completeness: no pages in metadata"
            )
            record.add_data_provenance_note(key="file", note="no_pages_in_metadata")
            record.data.update(
                colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
            )
            return record.data

        nr_pages_metadata = __get_nr_pages_in_metadata(pages_metadata=pages_metadata)

        record.set_pages_in_pdf(project_path=pdf_prep_operation.review_manager.path)
        if nr_pages_metadata != record.data["pages_in_file"]:
            if nr_pages_metadata == int(record.data["pages_in_file"]) - 1:

                record.add_data_provenance_note(key="file", note="more_pages_in_pdf")

            elif self.__longer_with_appendix(
                review_manager=pdf_prep_operation.review_manager,
                record=record,
                nr_pages_metadata=nr_pages_metadata,
            ):
                pass
            else:

                msg = (
                    f'{record.data["ID"]}'.ljust(pad, " ")
                    + f'Nr of pages in file ({record.data["pages_in_file"]}) '
                    + "not identical with record "
                    + f"({nr_pages_metadata} pages)"
                )

                record.add_data_provenance_note(
                    key="file", note="nr_pages_not_matching"
                )
                record.data.update(
                    colrev_status=colrev.record.RecordState.pdf_needs_manual_preparation
                )

        return record.data


@zope.interface.implementer(colrev.process.PDFPrepEndpoint)
class TEIEndpoint:
    """Prepare PDFs by creating an annotated TEI document"""

    settings_class = colrev.process.DefaultSettings

    def __init__(
        self, *, pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep, settings: dict
    ) -> None:

        self.settings = from_dict(data_class=self.settings_class, data=settings)

        grobid_service = pdf_prep_operation.review_manager.get_grobid_service()
        grobid_service.start()
        Path(".tei").mkdir(exist_ok=True)

    @timeout_decorator.timeout(180, use_signals=False)
    def prep_pdf(
        self,
        pdf_prep_operation: colrev.ops.pdf_prep.PDFPrep,
        record: colrev.record.Record,
        pad: int,  # pylint: disable=unused-argument
    ) -> dict:

        pdf_prep_operation.review_manager.logger.info(
            f" creating tei: {record.data['ID']}"
        )
        if "file" in record.data:
            _ = pdf_prep_operation.review_manager.get_tei(
                pdf_path=Path(record.data["file"]),
                tei_path=record.get_tei_filename(),
            )

        return record.data


if __name__ == "__main__":
    pass
