#! /usr/bin/env python
import io
import logging
import os
import pprint
import re
import shutil
import subprocess
import typing
from pathlib import Path

import git
import imagehash
import langdetect
import timeout_decorator
from bibtexparser.bibdatabase import BibDatabase
from langdetect import detect_langs
from pdf2image import convert_from_path
from pdfminer.converter import TextConverter
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import resolve1
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfparser import PDFSyntaxError
from PyPDF2 import PdfFileReader
from PyPDF2 import PdfFileWriter
from tqdm.contrib.concurrent import process_map

from colrev_core.review_manager import RecordState

pp = pprint.PrettyPrinter(indent=4, width=140, compact=False)

PDF_HANDLING = "NA"
DEBUG_MODE = False
PDF_DIRECTORY = Path("pdfs")
CPUS, REPO_DIR = -1, "NA"

report_logger = logging.getLogger("colrev_core_report")
logger = logging.getLogger("colrev_core")

logging.getLogger("pdfminer").setLevel(logging.ERROR)


def reset_hashes(REVIEW_MANAGER) -> None:
    from colrev_core.review_manager import Process, ProcessType

    REVIEW_MANAGER.notify(Process(ProcessType.pdf_prep))
    bib_db = REVIEW_MANAGER.load_bib_db()
    for record in bib_db.entries:
        if "pdf_hash" in record:
            record.update(
                pdf_hash=imagehash.average_hash(
                    convert_from_path(record["file"], first_page=0, last_page=1)[0],
                    hash_size=32,
                )
            )
    REVIEW_MANAGER.save_bib_db(bib_db)
    git_repo = REVIEW_MANAGER.get_repo()
    git_repo.index.add([str(REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"])])
    REVIEW_MANAGER.create_commit("Update PDF hashes")
    return


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


def get_text_from_pdf(record: dict, PAD: int) -> dict:

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


def apply_ocr(record: dict, PAD: int) -> dict:
    pdf = Path(record["file"])
    ocred_filename = Path(record["file"].replace(".pdf", "_ocr.pdf"))

    if pdf.is_file():
        orig_path = pdf.parents[0]
    else:
        orig_path = PDF_DIRECTORY

    options = f"--jobs {CPUS}"
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
        + str(docker_home_path / pdf.name)
        + '"  "'
        + str(docker_home_path / ocred_filename.name)
        + '"'
    )
    subprocess.check_output([command], stderr=subprocess.STDOUT, shell=True)

    record["pdf_processed"] = "OCRMYPDF"

    record["file"] = str(ocred_filename)
    record = get_text_from_pdf(record, PAD)

    return record


@timeout_decorator.timeout(60, use_signals=False)
def pdf_check_ocr(record: dict, PAD: int) -> dict:

    if RecordState.pdf_imported != record["status"]:
        return record

    if not any(lang.prob > 0.9 for lang in detect_langs(record["text_from_pdf"])):
        report_logger.info(f'apply_ocr({record["ID"]})')
        record = apply_ocr(record, PAD)

    if not any(lang.prob > 0.9 for lang in detect_langs(record["text_from_pdf"])):
        msg = f'{record["ID"]}'.ljust(PAD, " ") + "Validation error (OCR problems)"
        report_logger.error(msg)
        logger.error(msg)

    if probability_english(record["text_from_pdf"]) < 0.9:
        msg = (
            f'{record["ID"]}'.ljust(PAD, " ")
            + "Validation error (Language not English)"
        )
        report_logger.error(msg)
        logger.error(msg)
        record.update(status=RecordState.pdf_needs_manual_preparation)

    return record


@timeout_decorator.timeout(60, use_signals=False)
def validate_pdf_metadata(record: dict, PAD: int) -> dict:

    if RecordState.pdf_imported != record["status"]:
        return record

    if "text_from_pdf" not in record:
        record = get_text_from_pdf(record, PAD)

    text = record["text_from_pdf"]
    text = text.replace(" ", "").replace("\n", "").lower()
    text = re.sub("[^a-zA-Z ]+", "", text)

    title_words = re.sub("[^a-zA-Z ]+", "", record["title"]).lower().split()

    match_count = 0
    for title_word in title_words:
        if title_word in text:
            match_count += 1

    if match_count / len(title_words) < 0.9:
        msg = f'{record["file"]}'.ljust(PAD, " ") + ": title not found in first pages"
        report_logger.error(msg)
        logger.error(msg)
        record["pdf_prep_hints"] = (
            record.get("pdf_prep_hints", "") + "; title_not_in_first_pages"
        )
        record.update(status=RecordState.pdf_needs_manual_preparation)

    match_count = 0
    for author_name in record.get("author", "").split(" and "):
        author_name = author_name.split(",")[0].lower().replace(" ", "")
        if re.sub("[^a-zA-Z ]+", "", author_name) in text:
            match_count += 1

    if match_count / len(record.get("author", "").split(" and ")) < 0.8:
        msg = f'{record["file"]}'.ljust(PAD, " ") + ": author not found in first pages"
        report_logger.error(msg)
        record["pdf_prep_hints"] = (
            record.get("pdf_prep_hints", "") + "; author_not_in_first_pages"
        )
        record.update(status=RecordState.pdf_needs_manual_preparation)

    return record


@timeout_decorator.timeout(60, use_signals=False)
def validate_completeness(record: dict, PAD: int) -> dict:

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
        record["pdf_prep_hints"] = (
            record.get("pdf_prep_hints", "") + "; not_full_version"
        )
        record.update(status=RecordState.pdf_needs_manual_preparation)
        return record

    pages_metadata = record.get("pages", "NA")
    if "NA" == pages_metadata or not re.match(r"^\d*--\d*$", pages_metadata):
        msg = (
            f'{record["ID"]}'.ljust(PAD - 1, " ")
            + "Could not validate completeness: no pages in metadata"
        )
        # report_logger.error(msg)
        record["pdf_prep_hints"] = (
            record.get("pdf_prep_hints", "") + "; no_pages_in_metadata"
        )
        record.update(status=RecordState.pdf_needs_manual_preparation)
        return record

    nr_pages_metadata = (
        int(pages_metadata.split("--")[1]) - int(pages_metadata.split("--")[0]) + 1
    )

    if nr_pages_metadata != record["pages_in_file"]:
        if nr_pages_metadata == int(record["pages_in_file"]) - 1:
            # report_logger.warning(
            #     f'{record["ID"]}'.ljust(PAD - 3, " ")
            #     + "File has one more page "
            #     + f'({record["pages_in_file"]}) compared to '
            #     + f"metadata ({nr_pages_metadata} pages)"
            # )
            record["pdf_prep_hints"] = (
                record.get("pdf_prep_hints", "") + "; more_pages_in_pdf"
            )
        else:
            msg = (
                f'{record["ID"]}'.ljust(PAD, " ")
                + f'Nr of pages in file ({record["pages_in_file"]}) '
                + "not identical with record "
                + f"({nr_pages_metadata} pages)"
            )
            # report_logger.error(msg)
            record["pdf_prep_hints"] = (
                record.get("pdf_prep_hints", "") + "; nr_pages_not_matching"
            )
            record.update(status=RecordState.pdf_needs_manual_preparation)
    return record


def get_coverpages(pdf):
    # for corrupted PDFs pdftotext seems to be more robust than
    # pdfReader.getPage(0).extractText()
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
    pdfReader = PdfFileReader(pdf, strict=False)
    if pdfReader.getNumPages() == 1:
        return [-1]

    # input(page0)

    coverpages = []

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
        or "formoreinformationregardingjstor,pleasecontactsupport@jstor.org" in page0
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

    # CAIS First Page
    if (
        "communicationsoftheassociationforinformationsystems" in page0
        and "abstract" not in page0
        and "keywords" not in page0
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


def extract_pages(record, pages):
    pdf = record["file"]
    pdfReader = PdfFileReader(pdf, strict=False)
    writer = PdfFileWriter()
    for i in range(0, pdfReader.getNumPages()):
        if i in pages:
            continue
        writer.addPage(pdfReader.getPage(i))
    with open(pdf, "wb") as outfile:
        writer.write(outfile)
    return


@timeout_decorator.timeout(60, use_signals=False)
def remove_coverpage(record, PAD):
    coverpages = get_coverpages(record["file"])
    if [-1] == coverpages:
        return record
    if coverpages:
        prior = record["file"]
        record["file"] = record["file"].replace(".pdf", "_wo_cp.pdf")
        shutil.copy(prior, record["file"])
        extract_pages(record, coverpages)
        report_logger.info(f'removed cover page for ({record["ID"]})')
    return record


def cleanup_pdf_processing_fields(record: dict) -> BibDatabase:

    if "text_from_pdf" in record:
        del record["text_from_pdf"]
    if "pages_in_file" in record:
        del record["pages_in_file"]
    if "pdf_prep_hints" in record:
        record["pdf_prep_hints"] = record["pdf_prep_hints"][2:]

    return record


def file_is_git_versioned(git_repo: git.Repo, filePath: Path) -> bool:
    pathdir = os.path.dirname(str(filePath))
    rsub = git_repo.head.commit.tree
    for path_element in pathdir.split(os.path.sep):
        try:
            rsub = rsub[path_element]
        except KeyError:
            return False
    return filePath in rsub


def prepare_pdf(item: dict) -> dict:
    record = item["record"]

    if RecordState.pdf_imported != record["status"] or "file" not in record:
        return record

    PAD = len(record["ID"]) + 35

    if not Path(record["file"]).is_file():
        msg = f'{record["ID"]}'.ljust(PAD, " ") + "Linked file/pdf does not exist"
        report_logger.error(msg)
        logger.error(msg)
        return record

    prep_scripts: typing.List[typing.Dict[str, typing.Any]] = [
        {"script": get_text_from_pdf, "params": [record, PAD]},
        {"script": pdf_check_ocr, "params": [record, PAD]},
        {"script": remove_coverpage, "params": [record, PAD]},
        {"script": validate_pdf_metadata, "params": [record, PAD]},
        {"script": validate_completeness, "params": [record, PAD]},
    ]

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
        try:
            prepped_record = prep_script["script"](*prep_script["params"])
            # Note : the record should not be changed
            # if the prep_script throws an exception
            record = prepped_record
        except (
            subprocess.CalledProcessError,
            timeout_decorator.timeout_decorator.TimeoutError,
        ) as err:
            logger.error(
                f'Error for {record["ID"]} '
                f'(in {prep_script["script"].__name__} : {err})'
            )
            pass
            record["status"] = RecordState.pdf_needs_manual_preparation
            if "text_from_pdf" in record:
                del record["text_from_pdf"]
            if "pages_in_file" in record:
                del record["pages_in_file"]
            return record

        failed = RecordState.pdf_needs_manual_preparation == record["status"]
        msg = f'{prep_script["script"].__name__}({record["ID"]}):'.ljust(PAD, " ") + " "
        msg += "fail" if failed else "pass"
        report_logger.info(msg)
        if failed:
            break

    # Each prep_scripts can create a new file
    # previous/temporary pdfs are deleted when the process is successful

    if RecordState.pdf_imported == record["status"]:
        record.update(status=RecordState.pdf_prepared)
        record.update(
            pdf_hash=imagehash.average_hash(
                convert_from_path(record["file"], first_page=0, last_page=1)[0],
                hash_size=32,
            )
        )

    # Backup:
    # Create a copy of the original PDF if users cannot
    # restore it from git
    # linked_file.rename(str(linked_file).replace(".pdf", "_backup.pdf"))

    if item["file_git_versioned"]:
        # Remove temporary PDFs when processing has succeeded
        target_fname = REPO_DIR / Path(f'{record["ID"]}.pdf')
        linked_file = REPO_DIR / record["file"]

        # TODO : we may have to consider different subdirectories?
        if target_fname.name != Path(record["file"]).name:
            if target_fname.is_file():
                os.remove(target_fname)
            linked_file.rename(target_fname)
            record["file"] = target_fname

        if not DEBUG_MODE:
            # Delete temporary PDFs for which processing has failed:
            if target_fname.is_file():
                for fpath in PDF_DIRECTORY.glob("*.pdf"):
                    if record["ID"] in str(fpath) and fpath != target_fname:
                        os.remove(fpath)

        git_repo = item["REVIEW_MANAGER"].get_repo()
        git_repo.index.add([record["file"]])

    record = cleanup_pdf_processing_fields(record)

    return record


def get_data(REVIEW_MANAGER) -> dict:
    from colrev_core.review_manager import RecordState

    record_state_list = REVIEW_MANAGER.get_record_state_list()
    nr_tasks = len(
        [x for x in record_state_list if str(RecordState.pdf_imported) == x[1]]
    )

    items = REVIEW_MANAGER.read_next_record(
        conditions={"status": RecordState.pdf_imported},
    )

    prep_data = {
        "nr_tasks": nr_tasks,
        "items": items,
    }
    logger.debug(pp.pformat(prep_data))
    return prep_data


def batch(items: dict, REVIEW_MANAGER):
    n = REVIEW_MANAGER.config["BATCH_SIZE"]
    batch = []
    for item in items:

        # (Quick) fix if there are multiple files linked:
        if ";" in item.get("file", ""):
            item["file"] = item["file"].split(";")[0]
        batch.append(
            {
                "record": item,
                "REVIEW_MANAGER": REVIEW_MANAGER,
                "file_git_versioned": file_is_git_versioned(
                    REVIEW_MANAGER.get_repo(), item["file"]
                ),
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

    # if "GIT" != PDF_HANDLING:
    #     print("PDFs not versioned - exit.")
    #     return

    pdf_prep_data = get_data(REVIEW_MANAGER)

    i = 1
    for pdf_prep_batch in batch(pdf_prep_data["items"], REVIEW_MANAGER):

        print(f"Batch {i}")
        i += 1

        # Note : for debugging:
        # for item in pdf_prep_batch:
        #     record = item['record']
        #     print(record['ID'])
        #     record = prepare_pdf(item)
        #     REVIEW_MANAGER.save_record_list_by_ID([record])

        pdf_prep_batch = process_map(prepare_pdf, pdf_prep_batch, max_workers=CPUS)

        REVIEW_MANAGER.save_record_list_by_ID(pdf_prep_batch)

        # Multiprocessing mixes logs of different records.
        # For better readability:
        REVIEW_MANAGER.reorder_log([x["ID"] for x in pdf_prep_batch])

        REVIEW_MANAGER.create_commit("Prepare PDFs", saved_args=saved_args)

    if i == 1:
        logger.info("No additional pdfs to prepare")

    return


if __name__ == "__main__":
    pass
