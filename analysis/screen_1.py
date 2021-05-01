#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.customization import convert_to_unicode

import os
import csv
import pandas as pd

def load_bib_file(bibfilename):
    
   with open(bibfilename) as bibtex_file:
        bp = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True).parse_file(bibtex_file, partial=True)
        
        data = []

        for entry in bp.get_entry_list():
            # print(entry)
            row = []
            citation_key = entry.get("ID", "no id")
            row.append(citation_key)
            author = entry.get("author", "no author")
            row.append(author)
            title = entry.get("title", "no title")
            row.append(title)
            year = entry.get("year", "no year")
            row.append(year)
            journal = entry.get("journal", "no journal")
            booktitle = entry.get("booktitle", "no booktitle")
            if journal == "no journal" and booktitle != "no booktitle":
                journal = booktitle
            row.append(journal)
            volume = entry.get("volume", "no volume")
            row.append(volume)
            issue = entry.get("number", "no issue")
            row.append(issue)
            pages = entry.get("pages", "no pages")
            row.append(pages)
            file_name = entry.get("file", "no file")
            row.append(file_name)
            doi = entry.get("doi", "no doi")
            row.append(doi)

            data.append(row)    

        
        data_df = pd.DataFrame(data, columns =["citation_key",
                        "author",
                        "title",
                        "year",
                        "journal",
                        "volume",
                        "issue",
                        "pages",
                        "file_name",
                        "doi"])

        return data_df


def run_screen_1(screen_filename, bibfilename):

    screen = pd.read_csv(screen_filename, dtype=str)
    
    #TODO: join references.bib
    
    print('To stop screening, press ctrl-c')

    references = load_bib_file(bibfilename)
    
    screen = pd.merge(screen, references, on='citation_key')

    try:
        for i, row in screen.iterrows():
            if 'TODO' == row['inclusion_1']:
                inclusion_decision = 'TODO'
                while inclusion_decision not in ['y','n']:
                    print()
                    print()
                    print(row['title'] + '  -  ' + row['author'] + '  ' + row['journal'] + '  ' + row['year'] + '  (' + row['volume'] + ':' + row['issue'] + ') *' + row['citation_key'] + '*')
                    print()
                    inclusion_decision = input('include (y) or exclude (n)?')
                inclusion_decision = inclusion_decision.replace('y', 'yes').replace('n', 'no')
                screen.at[i,'inclusion_1'] = inclusion_decision
        
                screen.sort_values(by=['citation_key'], inplace=True)
                screen.to_csv(screen_filename, index=False, quoting=csv.QUOTE_ALL)
    except KeyboardInterrupt:
        print()
        print()
        print('stopping screen 1')
        print()
        pass

    return


if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Run screen 1')
    
    bibfilename = 'data/references.bib'
    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)
    assert os.path.exists(bibfilename)
    
    run_screen_1(screen_file, bibfilename)

