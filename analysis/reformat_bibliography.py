#! /usr/bin/env python
# -*- coding: utf-8 -*-


import utils

if __name__ == "__main__":
    
    print('')
    print('')    
    
    print('Reformat bibliography')
    
    bib_database = utils.load_references_bib(modification_check = True, initialize = False)
    
    utils.save_bib_file(bib_database, 'data/references.bib')
