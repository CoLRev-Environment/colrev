#! /usr/bin/env python
import io
import logging
import multiprocessing as mp
import os
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

from review_template import process
from review_template import repo_setup
from review_template import utils

BATCH_SIZE = repo_setup.config["BATCH_SIZE"]
PDF_DIRECTORY = repo_setup.paths["PDF_DIRECTORY"]
CPUS = repo_setup.config["CPUS"]

IPAD, EPAD = 0, 0
current_batch_counter = mp.Value("i", 0)


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
        logging.error(
            f'{record["file"]}'.ljust(EPAD, " ")
            + "PDF reader error: check whether is a pdf"
        )
        record.update(pdf_status="needs_manual_preparation")
        pass
    except PDFTextExtractionNotAllowed:
        logging.error(
            f'{record["file"]}'.ljust(EPAD, " ") + "PDF reader error: protection"
        )
        record.update(pdf_status="needs_manual_preparation")
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

    if "imported" != record.get("pdf_status", "NA"):
        return record

    record = get_text_from_pdf(record)

    if 0 == probability_english(record["text_from_pdf"]):
        logging.info(f'apply_ocr({record["ID"]})')
        record = apply_ocr(record)

    if probability_english(record["text_from_pdf"]) < 0.9:
        logging.error(
            f'{record["ID"]}'.ljust(EPAD, " ")
            + "Validation error (OCR or language problems)"
        )
        record.update(pdf_status="needs_manual_preparation")

    return record


def validate_pdf_metadata(record: dict) -> dict:

    if "imported" != record.get("pdf_status", "NA"):
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
        logging.error(
            f'{record["file"]}'.ljust(EPAD, " ") + "Title not found in first pages"
        )
        record.update(pdf_status="needs_manual_preparation")

    match_count = 0
    for author_name in record["author"].split(" and "):
        author_name = author_name.split(",")[0].lower().replace(" ", "")
        if re.sub("[^a-zA-Z ]+", "", author_name) in text:
            match_count += 1

    if match_count / len(record["author"].split(" and ")) < 0.8:
        logging.error(
            f'{record["file"]}'.ljust(EPAD, " ") + "author not found in first pages"
        )
        record.update(pdf_status="needs_manual_preparation")

    return record


def validate_completeness(record: dict) -> dict:

    if "imported" != record.get("pdf_status", "NA"):
        return record

    full_version_purchase_notice = (
        "morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas"
    )
    if full_version_purchase_notice in extract_text_by_page(record).replace(" ", ""):
        logging.error(
            f'{record["ID"]}'.ljust(EPAD - 1, " ")
            + " Not the full version of the paper"
        )
        record.update(pdf_status="needs_manual_preparation")
        return record

    pages_metadata = record.get("pages", "NA")
    if "NA" == pages_metadata or not re.match(r"^\d*--\d*$", pages_metadata):
        logging.error(
            f'{record["ID"]}'.ljust(EPAD - 1, " ")
            + "Could not validate completeness: no pages in metadata"
        )
        record.update(pdf_status="needs_manual_preparation")
        return record

    nr_pages_metadata = (
        int(pages_metadata.split("--")[1]) - int(pages_metadata.split("--")[0]) + 1
    )

    if nr_pages_metadata != record["pages_in_file"]:
        if nr_pages_metadata == int(record["pages_in_file"]) - 1:
            logging.warning(
                f'{record["ID"]}'.ljust(EPAD - 3, " ")
                + "File has one more page "
                + f'({record["pages_in_file"]}) compared to '
                + f"metadata ({nr_pages_metadata} pages)"
            )
        else:
            logging.error(
                f'{record["ID"]}'.ljust(EPAD, " ")
                + f'Nr of pages in file ({record["pages_in_file"]}) '
                + "not identical with record "
                + f"({nr_pages_metadata} pages)"
            )
            record.update(pdf_status="needs_manual_preparation")
    return record


prep_scripts = {
    "pdf_check_ocr": pdf_check_ocr,
    "validate_pdf_metadata": validate_pdf_metadata,
    "validate_completeness": validate_completeness,
}


def prepare_pdf(record: dict) -> dict:

    if "imported" != record.get("pdf_status", "NA") or "file" not in record:
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    pdf = record["file"].replace(":", "").replace(".pdfPDF", ".pdf")
    if not os.path.exists(pdf):
        logging.error(
            f'{record["ID"]}'.ljust(EPAD, " ") + "Linked file/pdf does not exist"
        )
        return record

    if "pdf_versioned_tag" not in record:
        logging.error(f'{record["ID"]} - PDF not versioned/skip preparation')
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

    # Note: if there are problems pdf_status is set to needs_manual_preparation
    # if it remains 'imported', all preparation checks have passed
    logging.info(f'prepare({record["ID"]})')  # / {record["file"]}
    for prep_script in prep_scripts:
        record = prep_scripts[prep_script](record)

        failed = "needs_manual_preparation" == record.get("pdf_status")
        msg = f'{prep_script}({record["ID"]}):'.ljust(IPAD, " ") + " "
        msg += "fail" if failed else "pass"
        logging.info(msg)
        if failed:
            break

    if "imported" == record.get("pdf_status", "NA"):
        # Remove temporary PDFs when processing has succeeded
        fname = f'{PDF_DIRECTORY}{record["ID"]}.pdf'
        if fname != record.get("file", "NA"):
            if "GIT" == repo_setup.config["PDF_HANDLING"]:
                os.remove(fname)
            else:
                # Create a copy of the original PDF if users cannot
                # restore it from git
                os.rename(fname, fname.replace(".pdf", "_backup.pdf"))
            os.rename(record["file"], fname)
            record["file"] = fname
        record.update(pdf_status="prepared")
    else:
        if not repo_setup.config["DEBUG_MODE"]:
            # Delete temporary PDFs for which processing has failed:
            orig_filepath = f'{PDF_DIRECTORY}{record["ID"]}.pdf'
            if os.path.exists(orig_filepath):
                for fpath in os.listdir(PDF_DIRECTORY):
                    print(fpath)
                    if record["ID"] in fpath and fpath not in orig_filepath:
                        os.remove(fpath)

    return record


def mark_committed_pdfs(bib_db: BibDatabase, repo: git.Repo) -> BibDatabase:

    revlist = (commit.tree for commit in repo.iter_commits())
    last_tree = list(revlist)[0]
    files_in_prev_commit = [el.path for el in list(last_tree.traverse())]
    for record in bib_db.entries:
        if f'{PDF_DIRECTORY}{record["ID"]}.pdf' in files_in_prev_commit:
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


def main(bib_db: BibDatabase, repo: git.Repo) -> BibDatabase:

    saved_args = locals()

    process.check_delay(bib_db, min_status_requirement="pdf_imported")
    global IPAD
    global EPAD
    IPAD = min((max(len(x["ID"]) for x in bib_db.entries) + 2), 35) + 25
    EPAD = IPAD + 1

    # TODO: temporary fix: remove all lines containint PDFType1Font from log.
    # https://github.com/pdfminer/pdfminer.six/issues/282

    utils.reset_log()
    logging.info("Prepare PDFs")

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logging.info("Continuing batch preparation started earlier")

        bib_db = mark_committed_pdfs(bib_db, repo)

        pool = mp.Pool(repo_setup.config["CPUS"])
        bib_db.entries = pool.map(prepare_pdf, bib_db.entries)
        pool.close()
        pool.join()

        bib_db = cleanup_pdf_processing_fields(bib_db)

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            logging.info(
                "Completed pdf preparation batch "
                f"(entries {batch_start} to {batch_end})"
            )

            MAIN_REFERENCES = repo_setup.paths["MAIN_REFERENCES"]
            utils.save_bib_file(bib_db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            need_man_preps = [
                r["ID"]
                for r in bib_db.entries
                if "needs_manual_preparation" == r.get("pdf_status", "NA")
            ]
            if "GIT" == repo_setup.config["PDF_HANDLING"]:
                dirname = repo_setup.paths["PDF_DIRECTORY"]
                if os.path.exists(dirname):
                    for filepath in os.listdir(dirname):
                        if any(ID in filepath for ID in need_man_preps):
                            logging.info("skipping " + filepath)
                            continue

                        if filepath.endswith(".pdf"):
                            repo.index.add([os.path.join(dirname, filepath)])

            if not repo.is_dirty():
                break

            utils.reorder_log([x["ID"] for x in bib_db.entries])
            in_process = utils.create_commit(repo, "⚙️ Prepare PDFs", saved_args)
            if not in_process:
                logging.info("No PDFs prepared")

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info("No additional pdfs to prepare")
            break

    return bib_db
