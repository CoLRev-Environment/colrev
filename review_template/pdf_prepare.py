#! /usr/bin/env python
import io
import logging
import multiprocessing as mp
import os
import re

import click
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
IPAD, EPAD = 0, 0
current_batch_counter = mp.Value('i', 0)


def extract_text_by_page(record, pages=None):

    text_list = []
    pdf_path = record['file'].replace(':', '').replace('.pdfPDF', '.pdf')
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


def get_text_from_pdf(record):

    pdf_path = record['file'].replace(':', '').replace('.pdfPDF', '.pdf')
    file = open(pdf_path, 'rb')
    parser = PDFParser(file)
    document = PDFDocument(parser)

    pages_in_file = resolve1(document.catalog['Pages'])['Count']
    record['pages_in_file'] = pages_in_file

    try:
        pages = [0, 1, 2]
        text = extract_text_by_page(record, pages)

        record['text_from_pdf'] = text
    except PDFSyntaxError:
        logging.error(f'{record["file"]}'.ljust(EPAD, ' ') +
                      'PDF reader error: check whether is a pdf')
        record.update(pdf_status='needs_manual_preparation')
        pass
    except PDFTextExtractionNotAllowed:
        logging.error(f'{record["file"]}'.ljust(EPAD, ' ') +
                      'PDF reader error: protection')
        record.update(pdf_status='needs_manual_preparation')
        pass

    return record


def probability_english(text):
    langs = detect_langs(text)
    probability_english = 0.0
    for lang in langs:
        if lang.lang == 'en':
            probability_english = lang.prob
    return probability_english


def pdf_check_ocr(record):

    if 'imported' != record.get('pdf_status', 'NA'):
        return record

    if probability_english(record['text_from_pdf']) < 0.9:
        logging.error(f'{record["file"]}'.ljust(EPAD, ' ') +
                      'Validation error (OCR or language problems)')
        record.update(pdf_status='needs_manual_preparation')

    return record


def validate_pdf_metadata(record):

    if 'imported' != record.get('pdf_status', 'NA'):
        return record

    if 'text_from_pdf' not in record:
        record = get_text_from_pdf(record)

    text = record['text_from_pdf']
    text = text.replace(' ', '').replace('\n', '').lower()
    text = re.sub('[^a-zA-Z ]+', '', text)

    title_words = re.sub('[^a-zA-Z ]+', '', record['title'])\
                    .lower().split()
    match_count = 0
    for title_word in title_words:
        if title_word in text:
            match_count += 1

    if match_count/len(title_words) < 0.9:
        logging.error(f'{record["file"]}'.ljust(EPAD, ' ') +
                      'Title not found in first pages')
        record.update(pdf_status='needs_manual_preparation')

    match_count = 0
    for author_name in record['author'].split(' and '):
        author_name = \
            author_name.split(',')[0].lower().replace(' ', '')
        if (re.sub('[^a-zA-Z ]+', '', author_name) in text):
            match_count += 1

    if match_count/len(record['author'].split(' and ')) < 0.8:
        logging.error(f'{record["file"]}'.ljust(EPAD, ' ') +
                      'author not found in first pages')
        record.update(pdf_status='needs_manual_preparation')

    return record


def validate_completeness(record):
    if 'imported' != record.get('pdf_status', 'NA'):
        return record

    full_version_purchase_notice = \
        'morepagesareavailableinthefullversionofthisdocument,whichmaybepurchas'
    if full_version_purchase_notice in \
            extract_text_by_page(record).replace(' ', ''):
        logging.error(f'{record["ID"]}'.ljust(EPAD, ' ') +
                      ' not the full version of the paper')
        record.update(pdf_status='needs_manual_preparation')
        return record

    pages_metadata = record.get('pages', 'NA')
    if 'NA' == pages_metadata or not re.match(r'^\d*--\d*$', pages_metadata):
        logging.error(f'{record["ID"]}'.ljust(EPAD, ' ') +
                      'could not validate completeness: no pages in metadata')
        record.update(pdf_status='needs_manual_preparation')
        return record

    nr_pages_metadata = int(pages_metadata.split('--')[1]) - \
        int(pages_metadata.split('--')[0]) + 1

    if nr_pages_metadata != record['pages_in_file']:
        logging.error(f'{record["ID"]}'.ljust(EPAD, ' ') +
                      f'Nr of pages in file ({record["pages_in_file"]}) not '
                      f'identical with record ({nr_pages_metadata} pages)')
        record.update(pdf_status='needs_manual_preparation')
    return record


def prepare_pdf(record):

    if 'imported' != record.get('pdf_status', 'NA') or \
            'file' not in record:
        return record

    with current_batch_counter.get_lock():
        if current_batch_counter.value >= BATCH_SIZE:
            return record
        else:
            current_batch_counter.value += 1

    pdf = record['file'].replace(':', '').replace('.pdfPDF', '.pdf')
    if not os.path.exists(pdf):
        logging.error(f'{record["ID"]}'.ljust(EPAD, ' ') +
                      'Linked file/pdf does not exist')
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

    record = get_text_from_pdf(record)
    if 'needs_manual_preparation' == record.get('pdf_status'):
        if 'text_from_pdf' in record:
            del record['text_from_pdf']
            del record['pages_in_file']
        return record

    prep_scripts = {'pdf_check_ocr': pdf_check_ocr,
                    'validate_pdf_metadata': validate_pdf_metadata,
                    'validate_completeness': validate_completeness,
                    }

    # Note: if there are problems pdf_status is set to needs_manual_preparation
    logging.debug(f'Prepare pdf for {record["ID"]}')
    for prep_script in prep_scripts:
        logging.debug(f'{prep_script}({record["ID"]}) called')
        record = prep_scripts[prep_script](record)
        if 'needs_manual_preparation' == record.get('pdf_status'):
            break

    if 'text_from_pdf' in record:
        del record['text_from_pdf']
        del record['pages_in_file']

    if 'imported' == record.get('pdf_status'):
        logging.info(f' {record["ID"]}'.ljust(IPAD, ' ') + 'Prepared pdf')

        record.update(pdf_status='prepared')

    return record


def main(bib_db, repo):

    process.check_delay(bib_db, min_status_requirement='pdf_imported')
    global IPAD
    global EPAD
    IPAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)
    EPAD = IPAD-1

    print('TODO: if no OCR detected, create a copy & ocrmypdf')

    utils.reset_log()
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
        bib_db.entries = pool.map(prepare_pdf, bib_db.entries)
        pool.close()
        pool.join()

        with current_batch_counter.get_lock():
            batch_end = current_batch_counter.value + batch_start - 1

        if batch_end > 0:
            logging.info('Completed pdf preparation batch '
                         f'(entries {batch_start} to {batch_end})')

            MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
            utils.save_bib_file(bib_db, MAIN_REFERENCES)
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

    return bib_db


@click.command()
def cli():
    # TODO: temporary fix: remove all lines containint PDFType1Font from log.
    # https://github.com/pdfminer/pdfminer.six/issues/282

    bib_db = utils.load_main_refs()
    repo = init.get_repo()
    main(bib_db, repo)

    return 0


if __name__ == '__main__':
    bib_db = utils.load_main_refs()
    repo = init.get_repo()
    main(bib_db, repo)
