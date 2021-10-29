#! /usr/bin/env python
import io
import logging
import multiprocessing as mp
import os
import re

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

from review_template import init
from review_template import process
from review_template import repo_setup
from review_template import utils

BATCH_SIZE = repo_setup.config['BATCH_SIZE']

current_batch_counter = mp.Value('i', 0)


def extract_text_by_page(entry, pages=None):

    text_list = []
    pdf_path = entry['file'].replace(':', '').replace('.pdfPDF', '.pdf')
    with open(pdf_path, 'rb') as fh:
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
    return ''.join(text_list)


def get_text_from_pdf(entry):

    pdf_path = entry['file'].replace(':', '').replace('.pdfPDF', '.pdf')
    file = open(pdf_path, 'rb')
    parser = PDFParser(file)
    document = PDFDocument(parser)

    pages_in_file = resolve1(document.catalog['Pages'])['Count']
    entry['pages_in_file'] = pages_in_file

    try:
        pages = [0, 1, 2]
        text = extract_text_by_page(entry, pages)

        entry['text_from_pdf'] = text
    except PDFSyntaxError:
        logging.error('PDF reader error: check whether '
                      f'{entry["file"]} is a pdf')
        entry.update(pdf_status='needs_manual_preparation')
        pass
    except PDFTextExtractionNotAllowed:
        logging.error(f'PDF reader error: protection {entry["file"]}')
        entry.update(pdf_status='needs_manual_preparation')
        pass

    return entry


def probability_english(text):
    langs = detect_langs(text)
    probability_english = 0.0
    for lang in langs:
        if lang.lang == 'en':
            probability_english = lang.prob
    return probability_english


def pdf_check_ocr(entry):

    if 'imported' != entry.get('pdf_status', 'NA'):
        return entry

    if probability_english(entry['text_from_pdf']) < 0.9:
        logging.error(
            'Validation error (OCR or language problems):'
            f' {entry["ID"]}')
        entry.update(pdf_status='needs_manual_preparation')

    return entry


def validate_pdf_metadata(entry):

    if 'imported' != entry.get('pdf_status', 'NA'):
        return entry

    text = entry['text_from_pdf']
    text = text.replace(' ', '').replace('\n', '').lower()
    text = re.sub('[^a-zA-Z ]+', '', text)

    title_words = re.sub('[^a-zA-Z ]+', '', entry['title'])\
                    .lower().split()
    match_count = 0
    for title_word in title_words:
        if title_word in text:
            match_count += 1

    if match_count/len(title_words) < 0.9:
        logging.error(f'Title not found in first pages: {entry["ID"]}')
        entry.update(pdf_status='needs_manual_preparation')

    match_count = 0
    for author_name in entry['author'].split(' and '):
        author_name = \
            author_name.split(',')[0].lower().replace(' ', '')
        if (re.sub('[^a-zA-Z ]+', '', author_name) in text):
            match_count += 1

    if match_count/len(entry['author'].split(' and ')) < 0.8:
        logging.error(f'author not found in first pages: {entry["ID"]}')
        entry.update(pdf_status='needs_manual_preparation')

    return entry


def validate_completeness(entry):
    if 'imported' != entry.get('pdf_status', 'NA'):
        return entry

    full_version_purchase_notice = \
        'morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas'
    if full_version_purchase_notice in \
            extract_text_by_page(entry).replace(' ', ''):
        logging.error(f'{entry["ID"]} not the full version of the paper')
        entry.update(pdf_status='needs_manual_preparation')
        return entry

    pages_metadata = entry.get('pages', 'NA')
    if 'NA' == pages_metadata or not re.match(r'^\d*--\d*$', pages_metadata):
        logging.error(f'{entry["ID"]} could not validate completeness '
                      f'- no pages in metadata')
        entry.update(pdf_status='needs_manual_preparation')
        return entry

    nr_pages_metadata = int(pages_metadata.split('--')[1]) - \
        int(pages_metadata.split('--')[0]) + 1

    if nr_pages_metadata != entry['pages_in_file']:
        logging.error(f'{entry["ID"]} Nr of pages in file '
                      f'({entry["pages_in_file"]}) not '
                      f'identical with record ({nr_pages_metadata} pages)')
        entry.update(pdf_status='needs_manual_preparation')
    return entry


def prepare_pdf(entry):

    if 'imported' != entry.get('pdf_status', 'NA') or \
            'file' not in entry:
        return entry

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return entry
        else:
            current_batch_counter.value += 1

    pdf = entry['file'].replace(':', '').replace('.pdfPDF', '.pdf')
    if not os.path.exists(pdf):
        logging.error(f'Linked file/pdf does not exist for {entry["ID"]}')
        return entry

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

    entry = get_text_from_pdf(entry)
    if 'needs_manual_preparation' == entry.get('pdf_status'):
        if 'text_from_pdf' in entry:
            del entry['text_from_pdf']
            del entry['pages_in_file']
        return entry

    # OCR
    entry = pdf_check_ocr(entry)
    if 'needs_manual_preparation' == entry.get('pdf_status'):
        if 'text_from_pdf' in entry:
            del entry['text_from_pdf']
            del entry['pages_in_file']
        return entry

    # Match with meta-data
    entry = validate_pdf_metadata(entry)
    if 'needs_manual_preparation' == entry.get('pdf_status'):
        if 'text_from_pdf' in entry:
            del entry['text_from_pdf']
            del entry['pages_in_file']
        return entry

    # Completeness (nr pages/no cover-pages)
    entry = validate_completeness(entry)
    if 'needs_manual_preparation' == entry.get('pdf_status'):
        if 'text_from_pdf' in entry:
            del entry['text_from_pdf']
            del entry['pages_in_file']
        return entry

    if 'text_from_pdf' in entry:
        del entry['text_from_pdf']
        del entry['pages_in_file']
    entry.update(pdf_status='prepared')

    return entry


def prepare_pdfs(db, repo):

    process.check_delay(db, min_status_requirement='pdf_imported')

    print('TODO: if no OCR detected, create a copy & ocrmypdf')

    with open('report.log', 'r+') as f:
        f.truncate(0)
    logging.info('Prepare PDFs')

    in_process = True
    batch_start, batch_end = 1, 0
    while in_process:
        with current_batch_counter.get_lock():
            batch_start += current_batch_counter.value
            current_batch_counter.value = 0  # start new batch
        if batch_start > 1:
            logging.info('Continuing batch preparation started earlier')

        pool = mp.Pool(repo_setup.config['CPUS'])
        db.entries = pool.map(prepare_pdf, db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            logging.info('Completed pdf preparation batch '
                         f'(entries {batch_start} to {batch_end})')

            MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
            utils.save_bib_file(db, MAIN_REFERENCES)
            repo.index.add([MAIN_REFERENCES])

            if 'GIT' == repo_setup.config['PDF_HANDLING']:
                dirname = repo_setup.paths['PDF_DIRECTORY']
                if os.path.exists(dirname):
                    for filepath in os.listdir(dirname):
                        if filepath.endswith('.pdf'):
                            repo.index.add([os.path.join(dirname, filepath)])

            in_process = utils.create_commit(repo, '⚙️ Prepare PDFs')
            if not in_process:
                logging.info('No PDFs prepared')

        if batch_end < BATCH_SIZE or batch_end == 0:
            if batch_end == 0:
                logging.info('No additional pdfs to prepare')
            break

    print()

    return db


def main():
    # TODO: temporary fix: remove all lines containint PDFType1Font from log.
    # https://github.com/pdfminer/pdfminer.six/issues/282

    db = utils.load_references_bib(True, initialize=True)
    repo = init.get_repo()
    prepare_pdfs(db, repo)
    return


if __name__ == '__main__':
    main()
