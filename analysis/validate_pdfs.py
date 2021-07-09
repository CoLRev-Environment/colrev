#! /usr/bin/env python
import io
import os
import re

import config
import entry_hash_function
import utils
from langdetect import detect_langs
from pdfminer.converter import TextConverter
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFSyntaxError

EMAIL = config.paths['EMAIL']
PDF_DIRECTORY = entry_hash_function.paths['PDF_DIRECTORY']


def extract_text_by_page(pdf_path):
    with open(pdf_path, 'rb') as fh:
        text_list = []
        for page in PDFPage.get_pages(
            fh,
            pagenos=[0, 1, 2],
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


def extract_text(pdf_path):
    text_list = []
    for page in extract_text_by_page(pdf_path):
        text_list += page
    return ''.join(text_list)


def probability_english(text):

    langs = detect_langs(text)
    probability_english = 0.0
    for lang in langs:
        if lang.lang == 'en':
            probability_english = lang.prob
    return probability_english


def validate_pdf_metadata(bib_database):

    for entry in bib_database.entries:
        if 'file' not in entry:
            continue

        pdf = entry['file'].replace(':', '').replace('.pdfPDF', '.pdf')

        if not os.path.exists(pdf):
            return

        try:

            text = extract_text_by_page(pdf)

            if probability_english(text) < 0.98:
                print(
                    ' - validation error: possible OCR problems: ',
                    entry['file'],
                )
                continue

            text = text.replace(' ', '').replace('\n', '').lower()
            text = re.sub('[^a-zA-Z ]+', '', text)

            title_words = re.sub('[^a-zA-Z ]+', '', entry['title'])\
                            .lower().split()
            match_count = 0
            for title_word in title_words:
                if title_word in text:
                    match_count += 1

            if match_count/len(title_words) < 0.9:
                print(
                    ' - validation error (title not found in first pages): ',
                    entry['file'],
                )

            match_count = 0
            for author_name in entry['author'].split(' and '):
                author_name = author_name.split(',')[0]\
                    .lower()\
                    .replace(' ', '')
                if (re.sub('[^a-zA-Z ]+', '', author_name) in text):
                    match_count += 1

            if match_count/len(entry['author'].split(' and ')) < 0.8:
                print(
                    ' - validation error (author not found in first pages): ',
                    entry['file'],
                )

        except PDFSyntaxError:
            print(
                ' - PDF reader error: check whether ',
                entry['file'] + 'is really a pdf',
            )
            pass
        except PDFTextExtractionNotAllowed:
            print(
                ' - PDF reader error: not allowed to extract (protection) ',
                entry['file'],
            )
            pass

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Validate PDFs')

    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False,
    )
    bib_database = validate_pdf_metadata(bib_database)

    print(
        'TODO: if no OCR detected, ',
        'create a backup and send to ocrmypdf container',
    )
