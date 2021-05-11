#! /usr/bin/env python
# -*- coding: utf-8 -*-

import csv
import os
from bibtexparser.bibdatabase import BibDatabase
import pandas as pd
import requests
import json

import utils

YOUR_EMAIL = "gerit.wagner@hec.ca"

PDF_DIRECTORY = 'data/pdfs/'

pdfs_retrieved = 0
existing_pdfs_linked = 0
missing_pdfs = 0
total_to_retrieve = 0
pdfs_available = 0

def unpaywall(doi, retry=0, pdfonly=True):

    r = requests.get("https://api.unpaywall.org/v2/{}".format(doi), params={"email":YOUR_EMAIL})

    if r.status_code == 404:
#        print("Invalid/unknown DOI {}".format(doi))
        return None

    if r.status_code == 500:
#        print("Unpaywall API failed. Try: {}/3".format(retry+1))

        if retry < 3:
            return unpaywall(doi, retry+1)
        else:
#            print("Retried 3 times and failed. Giving up")
            return None

    best_loc = None
    try:
        best_loc = r.json()['best_oa_location']
    except json.decoder.JSONDecodeError:
#        print("Response was not json")
#        print(r.text)
        return None
    except KeyError:
#        print("best_oa_location not set")
#        print(r.text)
        return None
    except:
#        print("Something weird happened")
#        print(r.text)
        return None


    if not r.json()['is_oa'] or best_loc is None:
#        print("No OA paper found for {}".format(doi))
        return None

    if(best_loc['url_for_pdf'] is None and pdfonly is True):
#        print("No PDF found..")
#        print(best_loc)
        return None
    else:
        return best_loc['url']

    return best_loc['url_for_pdf']


def acquire_pdfs(bib_database, screen):
    global total_to_retrieve
    global pdfs_retrieved
    global existing_pdfs_linked
    global missing_pdfs
    global pdfs_available

#    global total_to_retrieve
    
    papers_to_acquire = screen.loc[screen.inclusion_2.notnull(), 'citation_key'].tolist()
    
    total_to_retrieve = len(papers_to_acquire)
    
    missing_entries = BibDatabase()

    for entry in bib_database.entries:
        if entry['ID'] in papers_to_acquire:
            pdf_filepath = os.path.join(PDF_DIRECTORY, entry['ID'] + '.pdf')
            
            if os.path.exists(pdf_filepath):
                pdfs_available += 1
                if not 'file' in entry:
                    entry['file'] = ':' + pdf_filepath + ':PDF'
                    existing_pdfs_linked += 1
                continue
            if 'doi' in entry:
                url = unpaywall(entry['doi'])
                if not url is None:
                    if not 'Invalid/unknown DOI' in url:
                        response = requests.get(url)
                        with open(pdf_filepath, 'wb') as f:
                            f.write(response.content)
                        print('Retrieved pdf via unpaywall api: ' + pdf_filepath)
                        entry['file'] = ':' + pdf_filepath + ':PDF'
                        pdfs_retrieved += 1

            if not os.path.exists(pdf_filepath):
                missing_entries.entries.append(entry)

    if len(missing_entries.entries) > 0:
        missing_entries_df = pd.DataFrame.from_records(missing_entries.entries)
        missing_entries_df = missing_entries_df.loc[:,missing_entries_df.columns.isin(['ID', 'author', 'title', 'journal', 'booktitle', 'year', 'volume', 'number', 'pages'])]
        missing_entries_df = missing_entries_df.rename(columns = {'ID': 'citation_key'})
        missing_entries_df.to_csv('data/missing_pdf_files.csv', index=False, quoting=csv.QUOTE_ALL)
        
        missing_pdfs = len(missing_entries.entries)

    return bib_database

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Acquire PDFs')
    
    bib_database = utils.load_references_bib(modification_check = True, initialize = False)

    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)
    screen = pd.read_csv(screen_file, dtype=str)

    bib_database = acquire_pdfs(bib_database, screen_file)
    
    print(' - ' + str(total_to_retrieve) + ' pdfs required')
    print(' - ' + str(pdfs_available) + ' pdfs available')
    if existing_pdfs_linked > 0:
        print(' - ' + str(existing_pdfs_linked) + ' existing pdfs linked in bib file')
    print(' - ' + str(pdfs_retrieved) + ' pdfs retrieved')
    if missing_pdfs > 0:
        print(' - ' + str(missing_pdfs) + ' pdfs missing (see data/missing_pdf_files.csv)')
   
    

    utils.save_bib_file(bib_database, 'data/references.bib')
