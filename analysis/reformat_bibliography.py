#! /usr/bin/env python
import entry_hash_function
import utils

MAIN_REFERENCES = entry_hash_function.paths['MAIN_REFERENCES']

if __name__ == '__main__':

    print('')
    print('')

    print('Reformat bibliography')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    utils.save_bib_file(bib_database, MAIN_REFERENCES)
