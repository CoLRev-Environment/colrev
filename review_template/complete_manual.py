#! /usr/bin/env python
import csv
import itertools
import pprint

import git
import yaml

from review_template import entry_hash_function
from review_template import importer
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']
with open('private_config.yaml') as private_config_yaml:
    private_config = yaml.load(private_config_yaml, Loader=yaml.FullLoader)

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']

DEBUG_MODE = (1 == private_config['params']['DEBUG_MODE'])

entry_type_mapping = {'a': 'article', 'i': 'inproceedings', 'b': 'book'}


def main():
    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    # TBD: load completion_edits to avoid inserting redundant data?

    existing_hash_ids = [entry['hash_id'].split(',') for
                         entry in bib_database.entries
                         if not 'needs_manual_completion' == entry['status']]
    existing_hash_ids = list(itertools.chain(*existing_hash_ids))

    citation_key_list = [entry['ID'] for entry in bib_database.entries]

    completion_edits = []
    pp = pprint.PrettyPrinter(indent=4)
    for entry in [x for x in bib_database.entries
                  if 'needs_manual_completion' == x['status']]:
        # Escape sequence to clear terminal output for each new comparison
        print(chr(27) + '[2J')
        pp.pprint(entry)
        if 'n' == input('ENTRYTYPE=' + entry['ENTRYTYPE'] + ' correct?'):
            correct_entry_type = input('Correct type: ' +
                                       'a (article), i (inproceedings), ' +
                                       'b (book), o (other)')
            assert correct_entry_type in ['a', 'i', 'b', 'o']
            correct_entry_type = [value for (key, value)
                                  in entry_type_mapping.items()
                                  if key == correct_entry_type]
            completion_edits.append([entry['source_file_path'],
                                     entry['source_id'],
                                     'ENTRYTYPE',
                                     correct_entry_type[0]])
            entry['ENTRYTYPE'] = correct_entry_type[0]

        if 'article' == entry['ENTRYTYPE']:
            for field in ['title', 'author', 'year', 'journal', 'volume']:
                if field not in entry:
                    value = input('Please provide the ' + field + ' (or NA)')
                    completion_edits.append([entry['source_file_path'],
                                             entry['source_id'],
                                             field,
                                             value])
                    entry[field] = value
            if 'issue' not in entry and 'number' not in entry:
                value = input('Please provide the issue (or NA)')
                completion_edits.append([entry['source_file_path'],
                                         entry['source_id'],
                                         field,
                                         value])
                entry['issue'] = value

        if 'inproceedings' == entry['ENTRYTYPE']:
            for field in ['title', 'author', 'booktitle', 'year']:
                if field not in entry:
                    value = input('Please provide the ' + field + ' (or NA)')
                    completion_edits.append([entry['source_file_path'],
                                             entry['source_id'],
                                             field,
                                             value])
                    entry[field] = value

        if 'book' == entry['ENTRYTYPE']:
            for field in ['title', 'author', 'year']:
                if field not in entry:
                    value = input('Please provide the ' + field + ' (or NA)')
                    completion_edits.append([entry['source_file_path'],
                                             entry['source_id'],
                                             field,
                                             value])
                    entry[field] = value

        # ELSE: title, author, year, any-container-title

        if importer.is_sufficiently_complete(entry):
            # Note: NA is used to indicate that there is no value for the field
            # (but it is not needed), e.g., some journals have no issue numbers
            for key in entry.keys():
                if 'NA' == entry[key]:
                    del entry[key]

            entry = importer.drop_fields(entry)
            entry.update(status='imported')
            hid = entry_hash_function.create_hash[HASH_ID_FUNCTION](entry)
            entry.update(hash_id=hid)
            del entry['source_file_path']
            del entry['source_id']
            if hid in existing_hash_ids:
                entry = None
            else:
                entry.update(ID=utils.generate_citation_key_blacklist(
                    entry, citation_key_list,
                    entry_in_bib_db=True,
                    raise_error=False))
                citation_key_list.append(entry['ID'])

    with open('search/completion_edits.csv', 'a') as wr_obj:
        writer = csv.writer(wr_obj, quotechar='"', quoting=csv.QUOTE_ALL)
        for completion_edit in completion_edits:
            writer.writerow(completion_edit)

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    r = git.Repo('')
    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:

        r.index.add([MAIN_REFERENCES, 'search/completion_edits.csv'])

        hook_skipping = 'false'
        if not DEBUG_MODE:
            hook_skipping = 'true'
        r.index.commit(
            'Complete records for import',
            author=git.Actor(
                'manual (using complete_manual.py)', ''),
            skip_hooks=hook_skipping
        )

    print('Completed task. To continue, use \n\n   make main')


if __name__ == '__main__':
    main()
