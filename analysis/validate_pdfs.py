#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
import os
import re
from bibtexparser.customization import convert_to_unicode

from langdetect import detect_langs


import io
from pdfminer.converter import TextConverter
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage

from pdfminer.pdfparser import PDFSyntaxError
from pdfminer.pdfdocument import PDFTextExtractionNotAllowed


YOUR_EMAIL = "gerit.wagner@hec.ca"

PDF_DIRECTORY = 'data/pdfs/'

def extract_text_by_page(pdf_path):
    with open(pdf_path, 'rb') as fh:
        text_list = []
        for page in PDFPage.get_pages(fh,
                                      pagenos = [0,1,2],
                                      caching=True,
                                      check_extractable=True):
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
    for page in extract_text_by_page(pdf_path):
        print(page)
        print()

def probability_english(text):

    langs = detect_langs(text)
    probability_english = 0.0
    for lang in langs:
        if lang.lang == 'en':
            probability_english = lang.prob
    return probability_english

def validate_pdf_metadata(bibfilename):
    
    with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)

    for entry in bp.entries:
        if not 'file' in entry:
            continue
        
        pdf = entry['file'].replace(':','').replace('.pdfPDF','.pdf')

        if not os.path.exists(pdf):
            return
    
        try:

            text = extract_text_by_page(pdf)
            
            if probability_english(text) < 0.98:
                print(' - validation error: possible OCR problems: ' + entry['file'])
                continue
        
            text = text.replace(' ', '').replace('\n','').lower()
            text = re.sub('[^a-zA-Z ]+', '', text)
    
            title_words = re.sub('[^a-zA-Z ]+', '', entry['title']).lower().split()
            match_count = 0
            for title_word in title_words:
                if title_word in text:
                    match_count += 1
            
            if match_count/len(title_words) < 0.9:
                print(' - validation error (title not found in first pages): ' + entry['file'])
                
            match_count = 0
            for author_name in entry['author'].split(' and '):
                author_name = author_name.split(',')[0].lower().replace(' ', '')
                if (re.sub('[^a-zA-Z ]+', '', author_name) in text):
                    match_count += 1

            if match_count/len(entry['author'].split(' and ')) < 0.8:
                    print(' - validation error (author not found in first pages): ' + entry['file'])

        except PDFSyntaxError:
            print(' - PDF reader error: check whether ' + entry['file'] + 'is really a pdf')
            pass
        except PDFTextExtractionNotAllowed:
            print(' - PDF reader error: not allowed to extract (protection) ' + entry['file'])
            pass
            
    return


if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Validate PDFs')
    
    bibfilename = 'data/references.bib'
    assert os.path.exists(bibfilename)

    bib_database = validate_pdf_metadata(bibfilename)
