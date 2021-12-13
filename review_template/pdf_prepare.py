#! /usr/bin/env python
import io
import logging
import os
import pprint
import re
import subprocess
from pathlib import Path

import imagehash
import langdetect
from bibtexparser.bibdatabase import BibDatabase
from langdetect import detect_langs
from pdf2image import convert_from_bytes
from pdfminer.converter import TextConverter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfparser import PDFSyntaxError
from tqdm.contrib.concurrent import process_map

from review_template.review_manager import RecordState

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

PDF_HANDLING = "NA"
DEBUG_MODE = False
PDF_DIRECTORY = Path("pdfs")
CPUS, REPO_DIR = -1, "NA"

PAD = 0

report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")


def extract_text_by_page(record: dict, pages: list = None) -> str:

    text_list: list = []
    with open(record["file"], "rb") as fh:
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
    return "".join(text_list)


def get_text_from_pdf(record: dict) -> dict:

    with open(record["file"], "rb") as file:
        parser = PDFParser(file)
        document = PDFDocument(parser)

        pages_in_file = resolve1(document.catalog["Pages"])["Count"]
    record["pages_in_file"] = pages_in_file

    try:
        text = extract_text_by_page(record, [0, 1, 2])
        record["text_from_pdf"] = text

    except PDFSyntaxError:
        msg = (
            f'{record["file"]}'.ljust(PAD, " ")
            + "PDF reader error: check whether is a pdf"
        )
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)
        pass
    except PDFTextExtractionNotAllowed:
        msg = f'{record["file"]}'.ljust(PAD, " ") + "PDF reader error: protection"
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.md_needs_manual_preparation)
        pass

    return record


def probability_english(text: str) -> float:
    try:
        langs = detect_langs(text)
        probability_english = 0.0
        for lang in langs:
            if lang.lang == "en":
                probability_english = lang.prob
    except langdetect.lang_detect_exception.LangDetectException:
        probability_english = 0
        pass
    return probability_english


def apply_ocr(record: dict) -> dict:
    pdf = Path(record["file"])
    ocred_filename = Path(record["file"].replace(".pdf", "_ocr.pdf"))

    options = f"--jobs {CPUS}"
    # if rotate:
    #     options = options + '--rotate-pages '
    # if deskew:
    #     options = options + '--deskew '
    docker_home_path = Path("/home/docker")
    command = (
        'docker run --rm --user "$(id -u):$(id -g)" -v "'
        + str(PDF_DIRECTORY)
        + ':/home/docker" jbarlow83/ocrmypdf --force-ocr '
        + options
        + ' -l eng+deu "'
        + str(docker_home_path / pdf.name)
        + '"  "'
        + str(docker_home_path / ocred_filename.name)
        + '"'
    )
    subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

    record["pdf_processed"] = "OCRMYPDF"

    record["file"] = str(ocred_filename)
    record = get_text_from_pdf(record)

    return record


def pdf_check_ocr(record: dict) -> dict:

    if str(RecordState.pdf_imported) != str(record["status"]):
        return record

    record = get_text_from_pdf(record)

    if 0 == probability_english(record["text_from_pdf"]):
        report_logger.info(f'apply_ocr({record["ID"]})')
        record = apply_ocr(record)

    if probability_english(record["text_from_pdf"]) < 0.9:
        msg = (
            f'{record["ID"]}'.ljust(PAD, " ")
            + "Validation error (OCR or language problems)"
        )
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)

    return record


def validate_pdf_metadata(record: dict) -> dict:

    if RecordState.pdf_imported != record["status"]:
        return record

    if "text_from_pdf" not in record:
        record = get_text_from_pdf(record)

    text = record["text_from_pdf"]
    text = text.replace(" ", "").replace("\n", "").lower()
    text = re.sub("[^a-zA-Z ]+", "", text)

    title_words = re.sub("[^a-zA-Z ]+", "", record["title"]).lower().split()

    match_count = 0
    for title_word in title_words:
        if title_word in text:
            match_count += 1

    if match_count / len(title_words) < 0.9:
        msg = f'{record["file"]}'.ljust(PAD, " ") + "Title not found in first pages"
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)

    match_count = 0
    for author_name in record.get("author", "").split(" and "):
        author_name = author_name.split(",")[0].lower().replace(" ", "")
        if re.sub("[^a-zA-Z ]+", "", author_name) in text:
            match_count += 1

    if match_count / len(record.get("author", "").split(" and ")) < 0.8:
        msg = f'{record["file"]}'.ljust(PAD, " ") + "author not found in first pages"
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)

    return record


def validate_completeness(record: dict) -> dict:

    if RecordState.pdf_imported != record["status"]:
        return record

    full_version_purchase_notice = (
        "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
    )
    if full_version_purchase_notice in extract_text_by_page(record).replace(" ", ""):
        msg = (
            f'{record["ID"]}'.ljust(PAD - 1, " ") + " Not the full version of the paper"
        )
        report_logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)
        return record

    pages_metadata = record.get("pages", "NA")
    if "NA" == pages_metadata or not re.match(r"^\d*--\d*$", pages_metadata):
        msg = (
            f'{record["ID"]}'.ljust(PAD - 1, " ")
            + "Could not validate completeness: no pages in metadata"
        )
        report_logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)
        return record

    nr_pages_metadata = (
        int(pages_metadata.split("--")[1]) - int(pages_metadata.split("--")[0]) + 1
    )

    if nr_pages_metadata != record["pages_in_file"]:
        if nr_pages_metadata == int(record["pages_in_file"]) - 1:
            report_logger.warning(
                f'{record["ID"]}'.ljust(PAD - 3, " ")
                + "File has one more page "
                + f'({record["pages_in_file"]}) compared to '
                + f"metadata ({nr_pages_metadata} pages)"
            )
        else:
            msg = (
                f'{record["ID"]}'.ljust(PAD, " ")
                + f'Nr of pages in file ({record["pages_in_file"]}) '
                + "not identical with record "
                + f"({nr_pages_metadata} pages)"
            )
            report_logger.error(msg)
            record.update(status=RecordState.pdf_needs_manual_preparation)
    return record


def cleanup_pdf_processing_fields(record: dict) -> BibDatabase:

    if "text_from_pdf" in record:
        del record["text_from_pdf"]
    if "pages_in_file" in record:
        del record["pages_in_file"]

    return record


prep_scripts = {
    "pdf_check_ocr": pdf_check_ocr,
    "validate_pdf_metadata": validate_pdf_metadata,
    "validate_completeness": validate_completeness,
}


def prepare_pdf(item: dict) -> dict:

    record = item["record"]
    if str(RecordState.pdf_imported) != str(record["status"]) or "file" not in record:
        return record

    if not Path(record["file"]).is_file():
        msg = f'{record["ID"]}'.ljust(PAD, " ") + "Linked file/pdf does not exist"
        report_logger.error(msg)
        logger.error(msg)
        return record

    # TODO
    # Remove cover pages and decorations
    # Remove protection
    # from process-paper.py
    # if pdf_tools.has_copyright_stamp(filepath):
    # pdf_tools.remove_copyright_stamp(filepath)
    # Watermark
    # experimental because many stamps are not embedded as searchable text
    # pdf_tools.remove_watermark(filepath)
    # pdf_tools.remove_coverpage(filepath)
    # pdf_tools.remove_last_page_info(filepath)

    # Note: if there are problems status is set to pdf_needs_manual_preparation
    # if it remains 'imported', all preparation checks have passed
    report_logger.info(f'prepare({record["ID"]})')  # / {record["file"]}
    for prep_script in prep_scripts:
        record = prep_scripts[prep_script](record)

        failed = str(RecordState.pdf_needs_manual_preparation) == str(record["status"])
        msg = f'{prep_script}({record["ID"]}):'.ljust(PAD, " ") + " "
        msg += "fail" if failed else "pass"
        report_logger.info(msg)
        if failed:
            break

    # Each prep_scripts can create a new file
    # (previous/temporary pdfs are deleted when the process is successful)

    if str(RecordState.pdf_imported) == str(record["status"]):
        # Remove temporary PDFs when processing has succeeded
        target_fname = REPO_DIR / Path(f'{record["ID"]}.pdf')
        linked_file = REPO_DIR / record["file"]
        record.update(
            pdf_hash=imagehash.average_hash(
                convert_from_bytes(open(linked_file, "rb").read())[0], hash_size=16
            )
        )
        if "file" in record:
            # TODO : we may have to consider different subdirectories?
            if target_fname.name != Path(record["file"]).name:
                if "GIT" == PDF_HANDLING:
                    if target_fname.is_file():
                        os.remove(target_fname)
                else:
                    # Create a copy of the original PDF if users cannot
                    # restore it from git
                    linked_file.rename(str(linked_file).replace(".pdf", "_backup.pdf"))
                linked_file.rename(target_fname)
                record["file"] = target_fname
            record.update(status=RecordState.pdf_prepared)
    else:
        if not DEBUG_MODE:
            # Delete temporary PDFs for which processing has failed:
            orig_filepath = PDF_DIRECTORY / Path(f'{record["ID"]}.pdf')
            if orig_filepath.is_file():
                for fpath in PDF_DIRECTORY.glob("*.pdf"):
                    if record["ID"] in str(fpath) and fpath != orig_filepath:
                        os.remove(fpath)

    record = cleanup_pdf_processing_fields(record)

    return record


def add_to_git(REVIEW_MANAGER, retrieval_batch) -> None:
    git_repo = REVIEW_MANAGER.get_repo()
    if "GIT" == REVIEW_MANAGER.config["PDF_HANDLING"]:
        if REVIEW_MANAGER.paths["PDF_DIRECTORY"].is_dir():
            for record in retrieval_batch:
                if "file" in record:
                    if Path(record["file"]).is_file():
                        git_repo.index.add([record["file"]])

    return


def get_data(REVIEW_MANAGER) -> dict:
    from review_template.review_manager import RecordState

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [x for x in record_state_list if str(RecordState.pdf_imported) == x[1]]
    )

    PAD = min((max(len(x[0]) for x in record_state_list) + 2), 35)
    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": str(RecordState.pdf_imported)},
    )

    prep_data = {
        "nr_tasks": nr_tasks,
        "PAD": PAD,
        "items": items,
    }
    logger.debug(pp.pformat(prep_data))
    return prep_data


def batch(items: dict, REVIEW_MANAGER):
    n = REVIEW_MANAGER.config["BATCH_SIZE"]
    batch = []
    for item in items:
        batch.append(
            {
                "record": item,
                "REVIEW_MANAGER": REVIEW_MANAGER,
            }
        )
        if len(batch) == n:
            yield batch
            batch = []
    yield batch


def main(REVIEW_MANAGER) -> None:

    saved_args = locals()

    # TODO: temporary fix: remove all lines containint PDFType1Font from log.
    # https://github.com/pdfminer/pdfminer.six/issues/282

    logger.info("Prepare PDFs")

    global PDF_HANDLING
    PDF_HANDLING = REVIEW_MANAGER.config["PDF_HANDLING"]

    global DEBUG_MODE
    DEBUG_MODE = REVIEW_MANAGER.config["DEBUG_MODE"]

    global PDF_DIRECTORY
    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]

    global REPO_DIR
    REPO_DIR = REVIEW_MANAGER.paths["REPO_DIR"]

    global CPUS
    CPUS = REVIEW_MANAGER.config["CPUS"]

    if "GIT" != PDF_HANDLING:
        print("PDFs not versioned - exit.")
        return

    pdf_prep_data = get_data(REVIEW_MANAGER)

    global PAD
    PAD = pdf_prep_data["PAD"]

    i = 1
    for pdf_prep_batch in batch(pdf_prep_data["items"], REVIEW_MANAGER):

        print(f"Batch {i}")
        i += 1

        pdf_prep_batch = process_map(prepare_pdf, pdf_prep_batch, max_workers=CPUS)

        REVIEW_MANAGER.save_record_list_by_ID(pdf_prep_batch)

        # Multiprocessing mixes logs of different records.
        # For better readability:
        REVIEW_MANAGER.reorder_log([x["ID"] for x in pdf_prep_batch])

        add_to_git(REVIEW_MANAGER, pdf_prep_batch)

        REVIEW_MANAGER.create_commit("Prepare PDFs", saved_args=saved_args)

    if i == 1:
        logger.info("No additional pdfs to prepare")

    return
