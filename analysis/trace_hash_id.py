#! /usr/bin/env python
import logging

import bibtexparser
import entry_hash_function
import utils
from bibtexparser.customization import convert_to_unicode

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)


def trace_hash(bibfilename, hash_id_needed):
    global nr_found

    with open(bibfilename) as bibtex_file:
        bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        for entry in bib_database.entries:
            # If there are transformations before the hash is created,
            # they need to be executed before the following.
            if entry_hash_function.create_hash(entry) == hash_id_needed:
                print(
                    '\n\n Found hash ',
                    hash_id_needed,
                    '\n in ',
                    bibfilename,
                    '\n\n',
                )
                print(entry)
                nr_found += 1
    return


if __name__ == '__main__':

    print('')
    print('')

    print('Trace hash_id')

    assert utils.hash_function_up_to_date()

    hash_id_needed = input('provide hash_id')
    assert len(hash_id_needed) == 64

    nr_found = 0

    for bib_file in utils.get_bib_files():
        trace_hash(bib_file, hash_id_needed)

    if nr_found == 0:
        print('Did not find hash_id')
