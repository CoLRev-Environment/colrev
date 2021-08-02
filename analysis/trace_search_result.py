#! /usr/bin/env python
import bibtexparser
import entry_hash_function
import utils
import yaml

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

if __name__ == '__main__':

    print('')
    print('')

    print('Trace an entry')

    entry_string = input('Enter BibTeX entry (replacing \n newlines)')

#    entry_string = '@book{RN507, author = {Abdalla Mikhaeil, Christine ' + \
#        'and Baskerville, Richard},  title = {An Identity Driven ' + \
#        'Escalation of Commitment to Negative Spillovers},   series = ' + \
#        '{ICIS 2017 Proceedings}, year = {2017},type = {Book}}'
#    entry_string = entry_string.replace('\n', '')

    entry_database = bibtexparser.loads(entry_string)

    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False)

    nr_found = 0

    for entry in entry_database.entries:
        hash_id = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)

        print(hash_id)

        found = False
        for entry in bib_database.entries:
            if entry['hash_id'] == hash_id:
                print('citation_key: ' +
                      entry['ID'] + ' for hash_id ' + entry['hash_id'])
                print()
                # if cleansed (hash_id in data/search/bib_details):
                # add note: quality cleansed entry:
                print(entry)
                found = True
        if not found:
            print('Did not find entry')
