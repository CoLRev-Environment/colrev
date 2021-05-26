#! /usr/bin/env python
import utils
from bibtexparser.bibdatabase import BibDatabase

nr_entries_added = 0
nr_current_entries = 0


def merge_duplicates(bib_database):

    deduplicated_bib_database = BibDatabase()
    for current_entry in bib_database.entries:
        if 0 == len(deduplicated_bib_database.entries):
            deduplicated_bib_database.entries.append(current_entry)
            continue
        # NOTE: append non-duplicated entries to deduplicated_bib_database
#        for entry in bib_database.entries:
#            if current_entry == entry:
#                continue
#            if current_entry['hash_id'] == entry['hash_id']:
        deduplicated_bib_database.entries.append(current_entry)

    return deduplicated_bib_database


if __name__ == '__main__':

    print('')
    print('')

    print('Merge duplicates')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    nr_current_entries = len(bib_database.entries)

    print(str(nr_current_entries) + ' records in references.bib')
    bib_database = merge_duplicates(bib_database)

    utils.save_bib_file(bib_database, 'data/references.bib')

    duplicates_removed = nr_current_entries - len(bib_database.entries)
    print('Duplicates removed: ' + str(duplicates_removed))
    print('')
