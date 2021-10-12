#! /usr/bin/env python
import configparser
import os
import pprint

import git

from review_template import entry_hash_function
from review_template import importer
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']

entry_type_mapping = {'a': 'article', 'p': 'inproceedings',
                      'b': 'book', 'ib': 'inbook', 'pt': 'phdthesis',
                      'mt': 'masterthesis',
                      'o': 'other', 'unp': 'unpublished'}


citation_key_list = []


def create_commit(r, bib_database):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:

        r.index.add([MAIN_REFERENCES])

        hook_skipping = 'false'
        if not config.getboolean('general', 'DEBUG_MODE'):
            hook_skipping = 'true'
        r.index.commit(
            'Complete records for import',
            author=git.Actor(
                'manual (using man_comp.py)', ''),
            skip_hooks=hook_skipping
        )

    return


def man_complete_entry(entry):
    global citation_key_list

    if 'needs_manual_completion' != entry['status']:
        return entry

    pp = pprint.PrettyPrinter(indent=4, width=140)
    # Escape sequence to clear terminal output for each new comparison
    os.system('cls' if os.name == 'nt' else 'clear')
    pp.pprint(entry)
    if 'title' in entry:
        print('https://scholar.google.de/scholar?hl=de&as_sdt=0%2C5&q=' +
              entry['title'].replace(' ', '+'))
    if 'n' == input('ENTRYTYPE=' + entry['ENTRYTYPE'] + ' correct?'):
        choice = input('Correct type: ' +
                       'a (article), p (inproceedings), ' +
                       'b (book), ib (inbook), ' +
                       'pt (phdthesis), mt (masterthesis), '
                       'unp (unpublished), o (other), ')
        assert choice in entry_type_mapping.keys()
        correct_entry_type = [value for (key, value)
                              in entry_type_mapping.items()
                              if key == choice]
        entry['ENTRYTYPE'] = correct_entry_type[0]

    reqs = importer.entry_field_requirements[entry['ENTRYTYPE']]
    for field in reqs:
        if field not in entry:
            value = input('Please provide the ' + field + ' (or NA)')
            entry[field] = value

    # ELSE: title, author, year, any-container-title

    if importer.is_sufficiently_complete(entry):
        # Note: NA is used to indicate that there is no value for the field
        # (but it is not needed), e.g., some journals have no issue numbers
        for key in list(entry):
            if 'NA' == entry[key]:
                del entry[key]

        entry = importer.drop_fields(entry)
        entry.update(ID=utils.generate_citation_key_blacklist(
            entry, citation_key_list,
            entry_in_bib_db=True,
            raise_error=False))
        citation_key_list.append(entry['ID'])
        entry.update(status='imported')

    return entry


def main():
    global citation_key_list

    r = git.Repo('')
    utils.require_clean_repo(r)

    print('Loading records for manual completion...')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    citation_key_list = [entry['ID'] for entry in bib_database.entries]

    for entry in bib_database.entries:
        entry = man_complete_entry(entry)
        utils.save_bib_file(bib_database)

    create_commit(r, bib_database)

    return


if __name__ == '__main__':
    main()
