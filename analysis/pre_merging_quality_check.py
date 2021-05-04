#! /usr/bin/env python
# -*- coding: utf-8 -*-

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

import os

def pre_merging_quality_check(bibfilename):
    
    with open(bibfilename, 'r') as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(common_strings=True).parse_file(bibtex_file, partial=True)
        for entry in bib_database.entries:

            if not ('author' in entry) :
                print('Record ' + entry.get('ID', 'no ID') + ' missing author')
#                entry['keywords'] = 'quality_improvement_needed'
            if not ('title' in entry):
                print('Record ' + entry.get('ID', 'no ID') + ' missing title ')
#                entry['keywords'] = 'quality_improvement_needed'
            if not ('year' in entry) :
                print('Record ' + entry.get('ID', 'no ID') + ' missing year')

#    writer = BibTexWriter()
#    writer.contents = ['comments', 'entries']
#    writer.indent = '    '
#    writer.display_order = ['author', 'booktitle', 'journal', 'title', 'year', 'number', 'pages', 'volume', 'doi', 'hash_id']
#    writer.order_entries_by = ('ID', 'author', 'year')
#    bibtex_str = bibtexparser.dumps(bib_database, writer)
#    
#    with open(bibfilename, 'w') as out:
#        out.write(bibtex_str + '\n')
        
    return

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Pre-merging quality check')
    
    bib_database = 'data/references.bib'
    assert os.path.exists(bib_database)

    pre_merging_quality_check(bib_database)

