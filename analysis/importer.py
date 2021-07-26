#! /usr/bin/env python
import itertools
import logging
import os

import bibtexparser
import cleanse_records
import entry_hash_function
import git
import reformat_bibliography
import utils
from bibtexparser.customization import convert_to_unicode

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

total_nr_entries_added = 0
total_nr_duplicates_hash_ids = 0
details_commit = []

MAIN_REFERENCES = entry_hash_function.paths['MAIN_REFERENCES']
MAIN_REFERENCES_CLEANSED = MAIN_REFERENCES.replace('.bib', '_cleansed.bib')

JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS = \
    utils.retrieve_crowd_resources()


fields_to_keep = [
    'ID', 'hash_id', 'ENTRYTYPE',
    'author', 'year', 'title',
    'journal', 'booktitle', 'series',
    'volume', 'number', 'pages', 'doi',
    'abstract',
    'editor', 'book-group-author',
    'book-author', 'keywords', 'file',
    'source_file_path', 'status'
]
fields_to_drop = [
    'type', 'url', 'organization',
    'issn', 'isbn', 'note', 'issue',
    'unique-id', 'month', 'researcherid-numbers',
    'orcid-numbers', 'eissn', 'article-number',
    'publisher', 'author_keywords', 'source',
    'affiliation', 'document_type', 'art_number',
    'address', 'language', 'doc-delivery-number',
    'da', 'usage-count-last-180-days', 'usage-count-since-2013',
    'doc-delivery-number', 'research-areas',
    'web-of-science-categories', 'number-of-cited-references',
    'times-cited', 'journal-iso', 'oa', 'keywords-plus',
    'funding-text', 'funding-acknowledgement', 'day'
]


def drop_fields(entry):
    for val in list(entry):
        if(val not in fields_to_keep):
            # drop all fields not in fields_to_keep
            entry.pop(val)
            # warn if fields are dropped that are not in fields_to_drop
            if val not in fields_to_drop:
                print('  dropped ' + val + ' field')
    return entry


def load():

    # Not sure we need to track the "imported" status here...
    # entries will not be added to bib_database
    # if their hash_id is already there
    bib_database = utils.load_references_bib(
        modification_check=True, initialize=True,
    )
    processed_hash_ids = [entry['hash_id'].split(',') for
                          entry in bib_database.entries]
    processed_hash_ids = list(itertools.chain(*processed_hash_ids))

    citation_key_list = [entry['ID'] for entry in bib_database.entries]

    # always include the current bib (including the statuus of entries)
    search_records = bib_database.entries
    # Note: only add search_results if their hash_id is not already
    # in bib_database.entries
    bib_files = utils.get_bib_files()
    for bib_file in bib_files:
        with open(bib_file) as bibtex_file:
            individual_bib_database = bibtexparser.bparser.BibTexParser(
                customization=convert_to_unicode, common_strings=True,
            ).parse_file(bibtex_file, partial=True)
            for entry in individual_bib_database.entries:
                entry['source_file_path'] = os.path.basename(bib_file)
                # IMPORTANT NOTE: any modifications completed before this step
                # need to be considered when backward-tracing!
                # Tradeoff: preprocessing can help to reduce the number of
                # representations (hash_ids) for each record
                # but it also introduces complexity (backward tacing)
                entry['hash_id'] = entry_hash_function.create_hash(entry)
                if entry['hash_id'] not in processed_hash_ids:
                    # create IDs here to prevent conflicts
                    # when entries are added to the MAIN_REFERENCES
                    # (in parallel)
                    entry['ID'] = \
                        utils.generate_citation_key_blacklist(
                            entry, citation_key_list,
                            entry_in_bib_db=False,
                            raise_error=False)
                    citation_key_list.append(entry['ID'])
                    entry['status'] = 'not_imported'
                    search_records.append(entry)

    # Note: if we process papers in order (often alphabetically),
    # the merging may be more likely to produce conflicts (in parallel mode)
    # search_records = random.sample(search_records, len(search_records))
    # IMPORTANT: this is deprecated! we should know exactly in which
    # (deterministic) order the records were started

    return search_records


def preprocess(entry):

    entry = cleanse_records.homogenize_entry(entry)

    # Note: the cleanse_records.py will homogenize more cases because
    # it runs speculative_changes(entry) before
    entry = cleanse_records.apply_local_rules(entry)
    entry = cleanse_records.apply_crowd_rules(entry)

    entry = drop_fields(entry)

    entry['status'] = 'not_cleansed'

    return entry


def import_entries(search_records, bib_database):
    source_file_paths = [entry['source_file_path'] for entry in search_records]
    bib_file_info = [[source_file_path, 0, 0]
                     for source_file_path in set(source_file_paths)]
    existing_hash_ids = utils.get_hash_ids(bib_database)

    for entry in search_records:
        if entry['hash_id'] not in existing_hash_ids:
            additional_count = 1
            existing_hash_ids.append(entry['hash_id'])
        else:
            additional_count = 0

        for i in range(len(bib_file_info)):
            if bib_file_info[i][0] == entry['source_file_path']:
                bib_file_info[i][1] += 1
                bib_file_info[i][2] += additional_count
        del entry['source_file_path']
        if 1 == additional_count:
            bib_database.entries.append(entry)

    for entry in bib_database.entries:
        # We set the citation_key here (even though it may be updated
        # after cleansing/updating author/year fields)
        # to prevent duplicate IDs in MAIN_REFERENCES,
        # to achieve a better sort order in MAIN_REFERENCES,
        # and to achieve a cleaner git history
        entry['ID'] = utils.generate_citation_key(entry,
                                                  bib_database,
                                                  entry_in_bib_db=True)

    details_commit = [source_file_path +
                      ' (' + str(overall) + ' overall, ' +
                      str(added) + ' additional records)'
                      for [source_file_path, overall, added] in bib_file_info]

    return bib_database, details_commit


def save(bib_database):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    return


def create_commit(r, details_commit):
    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:
        # to avoid failing pre-commit hooks
        reformat_bibliography.reformat_bib()

        # print('Creating commit ...')

        r.index.add([MAIN_REFERENCES])
        r.index.add(utils.get_bib_files())
        # print('Import search results \n - ' + '\n - '.join(details_commit))
        r.index.commit(
            'Import search results \n - ' + '\n - '.join(details_commit),
            author=git.Actor(
                'script:importer.py', ''),
        )
    else:
        print('No new records added to MAIN_REFERENCES')
    return

# TODO: define preferences (start by processing e.g., WoS, then GS) or
# use heuristics to start with the highest quality entries first.
