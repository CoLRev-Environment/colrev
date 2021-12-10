#! /usr/bin/env python
import io
import logging
import multiprocessing as mp
import os
import pprint
import re
import subprocess

import git
import langdetect
from bibtexparser.bibdatabase import BibDatabase
from langdetect import detect_langs
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


BATCH_SIZE, PDF_DIRECTORY, CPUS, REPO_DIR = -1, "NA", -1, "NA"

IPAD, EPAD = 0, 0
current_batch_counter = mp.Value("i", 0)

report_logger = logging.getLogger("review_template_report")
logger = logging.getLogger("review_template")


def extract_text_by_page(record: dict, pages: list = None) -> str:

    text_list = []
    pdf_path = record["file"].replace(":", "").replace(".pdfPDF", ".pdf")
    with open(pdf_path, "rb") as fh:
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

    pdf_path = record["file"].replace(":", "").replace(".pdfPDF", ".pdf")
    file = open(pdf_path, "rb")
    parser = PDFParser(file)
    document = PDFDocument(parser)

    pages_in_file = resolve1(document.catalog["Pages"])["Count"]
    record["pages_in_file"] = pages_in_file

    try:
        text = extract_text_by_page(record, [0, 1, 2])
        record["text_from_pdf"] = text

    except PDFSyntaxError:
        msg = (
            f'{record["file"]}'.ljust(EPAD, " ")
            + "PDF reader error: check whether is a pdf"
        )
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)
        pass
    except PDFTextExtractionNotAllowed:
        msg = f'{record["file"]}'.ljust(EPAD, " ") + "PDF reader error: protection"
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
    pdf = record["file"]
    ocred_filename = pdf[:-4] + "_ocr.pdf"

    options = f"--jobs {CPUS}"
    # if rotate:
    #     options = options + '--rotate-pages '
    # if deskew:
    #     options = options + '--deskew '
    command = (
        'docker run --rm --user "$(id -u):$(id -g)" -v "'
        + os.path.join(os.getcwd(), "pdfs")
        + ':/home/docker" jbarlow83/ocrmypdf --force-ocr '
        + options
        + ' -l eng+deu "'
        + os.path.join("/home/docker", os.path.basename(pdf))
        + '"  "'
        + os.path.join("/home/docker", os.path.basename(ocred_filename))
        + '"'
    )
    subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

    record["pdf_processed"] = "OCRMYPDF"

    record["file"] = ocred_filename
    record = get_text_from_pdf(record)

    return record


def pdf_check_ocr(record: dict) -> dict:

    if RecordState.pdf_imported != record["status"]:
        return record

    record = get_text_from_pdf(record)

    if 0 == probability_english(record["text_from_pdf"]):
        report_logger.info(f'apply_ocr({record["ID"]})')
        record = apply_ocr(record)

    if probability_english(record["text_from_pdf"]) < 0.9:
        msg = (
            f'{record["ID"]}'.ljust(EPAD, " ")
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
        msg = f'{record["file"]}'.ljust(EPAD, " ") + "Title not found in first pages"
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)

    match_count = 0
    for author_name in record.get("author", "").split(" and "):
        author_name = author_name.split(",")[0].lower().replace(" ", "")
        if re.sub("[^a-zA-Z ]+", "", author_name) in text:
            match_count += 1

    if match_count / len(record.get("author", "").split(" and ")) < 0.8:
        msg = f'{record["file"]}'.ljust(EPAD, " ") + "author not found in first pages"
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
            f'{record["ID"]}'.ljust(EPAD - 1, " ")
            + " Not the full version of the paper"
        )
        report_logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)
        return record

    pages_metadata = record.get("pages", "NA")
    if "NA" == pages_metadata or not re.match(r"^\d*--\d*$", pages_metadata):
        msg = (
            f'{record["ID"]}'.ljust(EPAD - 1, " ")
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
                f'{record["ID"]}'.ljust(EPAD - 3, " ")
                + "File has one more page "
                + f'({record["pages_in_file"]}) compared to '
                + f"metadata ({nr_pages_metadata} pages)"
            )
        else:
            msg = (
                f'{record["ID"]}'.ljust(EPAD, " ")
                + f'Nr of pages in file ({record["pages_in_file"]}) '
                + "not identical with record "
                + f"({nr_pages_metadata} pages)"
            )
            report_logger.error(msg)
            record.update(status=RecordState.pdf_needs_manual_preparation)
    return record


prep_scripts = {
    "pdf_check_ocr": pdf_check_ocr,
    "validate_pdf_metadata": validate_pdf_metadata,
    "validate_completeness": validate_completeness,
}


def prepare_pdf(record: dict) -> dict:

    if RecordState.pdf_imported != record["status"] or "file" not in record:
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    if not os.path.exists(record["file"]):
        msg = f'{record["ID"]}'.ljust(EPAD, " ") + "Linked file/pdf does not exist"
        report_logger.error(msg)
        logger.error(msg)
        return record

    if "pdf_versioned_tag" not in record:
        report_logger.error(f'{record["ID"]} - PDF not versioned/skip preparation')
        logger.error(f'{record["ID"]} - PDF not versioned/skip preparation')
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

        failed = RecordState.pdf_needs_manual_preparation == record["status"]
        msg = f'{prep_script}({record["ID"]}):'.ljust(IPAD, " ") + " "
        msg += "fail" if failed else "pass"
        report_logger.info(msg)
        if failed:
            break

    if RecordState.pdf_imported == record["status"]:
        # Remove temporary PDFs when processing has succeeded
        fname = os.path.join(REPO_DIR, f'{record["ID"]}.pdf')
        # TODO : we may have to consider different subdirectories?
        if os.path.basename(fname) != os.path.basename(record.get("file", "NA")):
            if "GIT" == PDF_HANDLING:
                if os.path.exists(fname):
                    os.remove(fname)
            else:
                # Create a copy of the original PDF if users cannot
                # restore it from git
                os.rename(fname, fname.replace(".pdf", "_backup.pdf"))
            os.rename(os.path.join(REPO_DIR, record["file"]), fname)
            record["file"] = fname
        record.update(status=RecordState.pdf_prepared)
    else:
        if not DEBUG_MODE:
            # Delete temporary PDFs for which processing has failed:
            orig_filepath = f'{PDF_DIRECTORY}{record["ID"]}.pdf'
            if os.path.exists(orig_filepath):
                for fpath in os.listdir(PDF_DIRECTORY):
                    print(fpath)
                    if record["ID"] in fpath and fpath not in orig_filepath:
                        os.remove(fpath)

    return record


def mark_committed_pdfs(
    REVIEW_MANAGER, bib_db: BibDatabase, repo: git.Repo
) -> BibDatabase:

    revlist = (commit.tree for commit in repo.iter_commits())
    last_tree = list(revlist)[0]
    files_in_prev_commit = [el.path for el in list(last_tree.traverse())]
    for record in bib_db.entries:
        if record["file"] in files_in_prev_commit:
            record["pdf_versioned_tag"] = "yes"

    return bib_db


def cleanup_pdf_processing_fields(bib_db: BibDatabase) -> BibDatabase:

    for record in bib_db.entries:
        if "text_from_pdf" in record:
            del record["text_from_pdf"]
        if "pages_in_file" in record:
            del record["pages_in_file"]
        if "pdf_versioned_tag" in record:
            del record["pdf_versioned_tag"]

    return bib_db


def main(REVIEW_MANAGER) -> None:

    saved_args = locals()

    global PDF_HANDLING
    global DEBUG_MODE
    global BATCH_SIZE
    global PDF_DIRECTORY
    global REPO_DIR
    global CPUS

    logger.info("Prepare PDFs")
    PDF_HANDLING = REVIEW_MANAGER.config["PDF_HANDLING"]
    DEBUG_MODE = REVIEW_MANAGER.config["DEBUG_MODE"]
    BATCH_SIZE = REVIEW_MANAGER.config["BATCH_SIZE"]
    PDF_DIRECTORY = REVIEW_MANAGER.paths["PDF_DIRECTORY"]
    REPO_DIR = REVIEW_MANAGER.paths["REPO_DIR"]
    CPUS = REVIEW_MANAGER.config["CPUS"]
    bib_db = REVIEW_MANAGER.load_bib_db()

    global IPAD
    global EPAD
    IPAD = min((max(len(x["ID"]) for x in bib_db.entries) + 2), 35) + 25
    EPAD = IPAD + 1

    # TODO: temporary fix: remove all lines containint PDFType1Font from log.
    # https://github.com/pdfminer/pdfminer.six/issues/282

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logger.info("Continuing batch preparation started earlier")

        bib_db = mark_committed_pdfs(REVIEW_MANAGER, bib_db, REVIEW_MANAGER.get_repo())

        bib_db.entries = process_map(
            prepare_pdf, bib_db.entries, max_workers=REVIEW_MANAGER.config["CPUS"] * 5
        )

        bib_db = cleanup_pdf_processing_fields(bib_db)

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            msg = (
                "Completed pdf preparation batch "
                + f"(entries {batch_start} to {batch_end})"
            )
            report_logger.info(msg)
            logger.info(msg)

            REVIEW_MANAGER.save_bib_db(bib_db)
            git_repo = REVIEW_MANAGER.get_repo()
            git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])

            need_man_preps = [
                record["ID"]
                for record in bib_db.entries
                if RecordState.pdf_needs_manual_preparation == record["status"]
            ]
            if "GIT" == REVIEW_MANAGER.config["PDF_HANDLING"]:
                dirname = REVIEW_MANAGER.paths["PDF_DIRECTORY"]
                if os.path.exists(dirname):
                    for filepath in os.listdir(dirname):
                        if any(ID in filepath for ID in need_man_preps):
                            report_logger.info("skipping " + filepath)
                            logger.info("skipping " + filepath)
                            continue

                        if filepath.endswith(".pdf"):
                            git_repo.index.add(
                                [
                                    os.path.join(
                                        str(
                                            REVIEW_MANAGER.paths[
                                                "PDF_DIRECTORY_RELATIVE"
                                            ]
                                        ),
                                        filepath,
                                    )
                                ]
                            )

            if not git_repo.is_dirty():
                break

            REVIEW_MANAGER.reorder_log([x["ID"] for x in bib_db.entries])
            in_process = REVIEW_MANAGER.create_commit(
                "Prepare PDFs", saved_args=saved_args
            )
            if not in_process:
                logger.info("No PDFs prepared")

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logger.info("No additional pdfs to prepare")
            break

    return
