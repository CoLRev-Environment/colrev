#! /usr/bin/env python
import logging
import os

import bibtexparser
import cleanse_records
import entry_hash_function
import git
import utils
from bibtexparser.customization import convert_to_unicode

logging.getLogger('bibtexparser').setLevel(logging.CRITICAL)

total_nr_entries_added = 0
total_nr_duplicates_hash_ids = 0
details_commit = []

MAIN_REFERENCES = entry_hash_function.paths['MAIN_REFERENCES']

fields_to_keep = [
    'ID', 'hash_id', 'ENTRYTYPE',
    'author', 'year', 'title',
    'journal', 'booktitle', 'series',
    'volume', 'number', 'pages', 'doi',
    'abstract',
    'editor', 'book-group-author',
    'book-author', 'keywords', 'file'
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


def gather(bibfilename, bib_database):
    global total_nr_entries_added
    global total_nr_duplicates_hash_ids
    global details_commit
    nr_entries_added = 0
    nr_duplicates_hash_ids = 0

    with open(bibfilename) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        print('')
        print(
            'Loading ' + os.path.basename(bib_file).ljust(52) + '(' +
            str(len(individual_bib_database.entries)).rjust(5) + ' records)',
        )

        for entry in individual_bib_database.entries:
            # IMPORTANT NOTE: any modifications completed before this step
            # need to be considered when backward-tracing!
            # Tradeoff: preprocessing can help to reduce the number of
            # representations (hash_ids) for each record
            # but it also introduces complexity (e.g., in the backward tacing)
            entry['hash_id'] = entry_hash_function.create_hash(entry)

            entry = cleanse_records.homogenize_entry(entry)

            # Note: the cleanse_records.py will homogenize more cases because
            # it runs speculative_changes(entry) before
            entry = cleanse_records.apply_local_rules(entry)
            entry = cleanse_records.apply_crowd_rules(entry)

            entry = drop_fields(entry)

        # pre-calculate for efficiency
        existing_hash_ids = utils.get_hash_ids(bib_database)

        for entry in individual_bib_database.entries:

            if 0 == len(bib_database.entries):
                bib_database.entries.append(entry)
                existing_hash_ids.append(entry['hash_id'])
                total_nr_entries_added += 1
                nr_entries_added += 1
                continue

            # don't append the entry if the hash_id is already in bib_database
            if not entry['hash_id'] in existing_hash_ids:

                # We set the citation_key here (even though it may be updated
                # after cleansing/updating author/year fields) to achieve a
                # better sort order in MAIN_REFERENCES
                # (and a cleaner git history)
                entry['ID'] = utils.generate_citation_key(entry, bib_database)

                entry['status'] = 'not_cleansed'

                bib_database.entries.append(entry)
                existing_hash_ids.append(entry['hash_id'])
                total_nr_entries_added += 1
                nr_entries_added += 1

            else:
                total_nr_duplicates_hash_ids += 1
                nr_duplicates_hash_ids += 1

    print(
        ' - ' + str(nr_entries_added).rjust(5) + ' entries added, ' +
        str(nr_duplicates_hash_ids).rjust(5) +
        ' entries with identical hash_ids',
    )

    if nr_entries_added > 0:
        details_commit.append(
            os.path.basename(bib_file) +
            ' (' +
            str(nr_entries_added) +
            ' additional records)'
        )

    return bib_database


if __name__ == '__main__':

    print('')
    print('')

    print('Combine search results')
    print('')

    assert utils.hash_function_up_to_date()

    r = git.Repo()

    # This should be sufficient (checking r.is_dirty() is not necessary)
    bib_database = utils.load_references_bib(
        modification_check=True, initialize=True,
    )

    JOURNAL_ABBREVIATIONS, JOURNAL_VARIATIONS, CONFERENCE_ABBREVIATIONS = \
        utils.retrieve_crowd_resources()

    nr_current_entries = len(bib_database.entries)

    if 0 == nr_current_entries:
        print(
            str('Created ' + MAIN_REFERENCES).ljust(60),
            '(',
            '0'.rjust(5),
            ' records).',
        )
    else:
        print(
            str('Opening existing  ' + 'Created ' + MAIN_REFERENCES).ljust(60),
            '(',
            str(nr_current_entries).rjust(5),
            ' records)',
        )
    print('')

    print('------------------------------------------------------------------')
    # TODO: define preferences (start by processing e.g., WoS, then GS) or
    # use heuristics to start with the highest quality entries first.

    for bib_file in utils.get_bib_files():
        bib_database = gather(bib_file, bib_database)

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    print('')
    print('------------------------------------------------------------------')
    print(
        'Overall: ',
        str(total_nr_entries_added).rjust(5),
        ' records added, ',
        str(len(bib_database.entries)).rjust(5),
        ' records in ' + MAIN_REFERENCES,
    )
    print('')

    print('Creating commit ...')

    r.index.add([MAIN_REFERENCES])
    print('Import search results \n - ' + '\n - '.join(details_commit))
    r.index.commit(
        'Import search results \n - ' + '\n - '.join(details_commit),
        author=git.Actor('script:combine_individual_search_results.py', ''),
    )
