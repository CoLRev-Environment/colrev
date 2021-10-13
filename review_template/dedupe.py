#! /usr/bin/env python
import csv
import itertools
import os
import re

import git
import pandas as pd
from fuzzywuzzy import fuzz

from review_template import repo_setup
from review_template import utils

nr_entries_added = 0
nr_current_entries = 0


MERGING_NON_DUP_THRESHOLD = repo_setup.config['MERGING_NON_DUP_THRESHOLD']
MERGING_DUP_THRESHOLD = repo_setup.config['MERGING_DUP_THRESHOLD']
MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

pd.options.mode.chained_assignment = None  # default='warn'


def format_authors_string(authors):
    authors = str(authors).lower()
    authors_string = ''
    authors = utils.remove_accents(authors)

    # abbreviate first names
    # "Webster, Jane" -> "Webster, J"
    # also remove all special characters and do not include separators (and)
    for author in authors.split(' and '):
        if ',' in author:
            last_names = [word[0] for word in author.split(',')[1].split(' ')
                          if len(word) > 0]
            authors_string = authors_string + \
                author.split(',')[0] + ' ' + ' '.join(last_names) + ' '
        else:
            authors_string = authors_string + author + ' '
    authors_string = re.sub(r'[^A-Za-z0-9, ]+', '', authors_string.rstrip())
    return authors_string


def get_entry_similarity(entry_a, entry_b):
    if 'author' not in entry_a:
        entry_a['author'] = ''
    if 'year' not in entry_a:
        entry_a['year'] = ''
    if 'journal' not in entry_a:
        entry_a['journal'] = ''
    if 'volume' not in entry_a:
        entry_a['volume'] = ''
    if 'number' not in entry_a:
        entry_a['number'] = ''
    if 'pages' not in entry_a:
        entry_a['pages'] = ''
    if 'booktitle' not in entry_a:
        entry_a['booktitle'] = ''
    if 'author' not in entry_b:
        entry_b['author'] = ''
    if 'year' not in entry_b:
        entry_b['year'] = ''
    if 'journal' not in entry_b:
        entry_b['journal'] = ''
    if 'volume' not in entry_b:
        entry_b['volume'] = ''
    if 'number' not in entry_b:
        entry_b['number'] = ''
    if 'pages' not in entry_b:
        entry_b['pages'] = ''
    if 'booktitle' not in entry_b:
        entry_b['booktitle'] = ''

    if 'container_title' not in entry_a:
        entry_a['container_title'] = entry_a.get('journal', '') + \
            entry_a.get('booktitle', '') + \
            entry_a.get('series', '')

    if 'container_title' not in entry_b:
        entry_b['container_title'] = entry_b.get('journal', '') + \
            entry_b.get('booktitle', '') + \
            entry_b.get('series', '')

    df_a = pd.DataFrame.from_dict([entry_a])
    df_b = pd.DataFrame.from_dict([entry_b])

    return get_similarity(df_a.iloc[0], df_b.iloc[0])


def get_similarity(df_a, df_b):

    author_similarity = fuzz.partial_ratio(df_a['author'], df_b['author'])/100

    title_similarity = fuzz.ratio(df_a['title'], df_b['title'])/100

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = fuzz.partial_ratio(df_a['year'], df_b['year'])/100

    outlet_similarity = \
        fuzz.ratio(df_a['container_title'], df_b['container_title'])/100

    if (str(df_a['journal']) != 'nan'):
        # Note: for journals papers, we expect more details
        if df_a['volume'] == df_b['volume']:
            volume_similarity = 1
        else:
            volume_similarity = 0
        if df_a['number'] == df_b['number']:
            number_similarity = 1
        else:
            number_similarity = 0
        # sometimes, only the first page is provided.
        if str(df_a['pages']) == 'nan' or str(df_b['pages']) == 'nan':
            pages_similarity = 1
        else:
            if df_a['pages'] == df_b['pages']:
                pages_similarity = 1
            else:
                if df_a['pages'].split('-')[0] == df_b['pages'].split('-')[0]:
                    pages_similarity = 1
                else:
                    pages_similarity = 0

        # Put more weithe on other fields if the title is very common
        # ie., non-distinctive
        # The list is based on a large export of distinct papers, tabulated
        # according to titles and sorted by frequency
        if [df_a['title'], df_b['title']] in \
            [['editorial', 'editorial'],
             ['editorial introduction', 'editorial introduction'],
             ['editorial notes', 'editorial notes'],
             ["editor's comments", "editor's comments"],
             ['book reviews', 'book reviews'],
             ['editorial note', 'editorial note'],
             ]:
            weights = [0.175, 0, 0.175, 0.175, 0.175, 0.175, 0.125]
        else:
            weights = [0.25, 0.3, 0.13, 0.2, 0.05, 0.05, 0.02]

        similarities = [author_similarity,
                        title_similarity,
                        year_similarity,
                        outlet_similarity,
                        volume_similarity,
                        number_similarity,
                        pages_similarity]

    else:

        weights = [0.15, 0.75, 0.05, 0.05]
        similarities = [author_similarity,
                        title_similarity,
                        year_similarity,
                        outlet_similarity]

    weighted_average = sum(similarities[g] * weights[g]
                           for g in range(len(similarities)))

    return round(weighted_average, 4)


def prep_references(references):
    if 'volume' not in references:
        references['volume'] = 'nan'
    if 'number' not in references:
        references['number'] = 'nan'
    if 'pages' not in references:
        references['pages'] = 'nan'
    if 'year' not in references:
        references['year'] = 'nan'
    else:
        references['year'] = references['year'].astype(str)
    if 'author' not in references:
        references['author'] = 'nan'
    else:
        references['author'] = \
            references['author'].apply(lambda x: format_authors_string(x))
    if 'title' not in references:
        references['title'] = 'nan'
    else:
        references['title'] = references['title']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()
    if 'journal' not in references:
        references['journal'] = ''
    else:
        references['journal'] = references['journal']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()
    if 'booktitle' not in references:
        references['booktitle'] = ''
    else:
        references['booktitle'] = references['booktitle']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()
    if 'series' not in references:
        references['series'] = ''
    else:
        references['series'] = references['series']\
            .str.replace(r'[^A-Za-z0-9, ]+', '', regex=True)\
            .str.lower()

    references['container_title'] = references['journal'].fillna('') + \
        references['booktitle'].fillna('') + \
        references['series'].fillna('')

    references.drop(references.columns.difference(['ID',
                                                   'author',
                                                   'title',
                                                   'year',
                                                   'journal',
                                                   'container_title',
                                                   'volume',
                                                   'number',
                                                   'pages']), 1, inplace=True)

    return references


def calculate_similarities_entry(references):
    # Note: per definition, similarities are needed relative to the first row.
    references = prep_references(references)
    # references.to_csv('preped_references.csv')
    references['similarity'] = 0
    sim_col = references.columns.get_loc('similarity')
    for base_entry_i in range(1, references.shape[0]):
        references.iloc[base_entry_i, sim_col] = \
            get_similarity(references.iloc[base_entry_i], references.iloc[0])
    # Note: return all other entries (not the comparison entry/first row)
    # and restrict it to the ID and similarity
    ck_col = references.columns.get_loc('ID')
    sim_col = references.columns.get_loc('similarity')
    return references.iloc[1:, [ck_col, sim_col]]


def get_prev_queue(queue_order, entry_link):
    # Note: Because we only introduce individual (non-merged entries),
    # there should be no semicolons in entry_link!
    prev_entries = []
    for idx, el in enumerate(queue_order):
        if entry_link == el:
            prev_entries = queue_order[:idx]
            break
    return prev_entries


def append_merges(entry):

    if 'prepared' != entry['status']:
        return

    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False,
    )

    # add all processed entries to the queue order before first (re)run
    if not os.path.exists('queue_order.csv'):
        with open('queue_order.csv', 'a') as fd:
            for x in bib_database.entries:
                if 'processed' == x.get('status', 'NA'):
                    fd.write(x['entry_link'] + '\n')

    # the order matters for the incremental merging (make sure that each
    # additional record is compared to/merged with all prior records in
    # the queue)
    with open('queue_order.csv', 'a') as fd:
        fd.write(entry['entry_link'] + '\n')
    queue_order = pd.read_csv('queue_order.csv', header=None)
    queue_order = queue_order[queue_order.columns[0]].tolist()
    required_prior_entry_links = \
        get_prev_queue(queue_order, entry['entry_link'])

    entry_links_in_prepared_file = []
    # note: no need to wait for completion of preparation
    entry_links_in_prepared_file = [entry['entry_link'].split(';')
                                    for entry in bib_database.entries
                                    if 'entry_link' in entry]
    entry_links_in_prepared_file = \
        list(itertools.chain(*entry_links_in_prepared_file))

    # if the entry is the first one added to the bib_database
    # (in a preceding processing step), it can be propagated
    if len(required_prior_entry_links) < 2:
        # entry.update(status = 'processed')
        if not os.path.exists('non_duplicates.csv'):
            with open('non_duplicates.csv', 'a') as fd:
                fd.write('"ID"\n')
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return

    merge_ignore_status = ['needs_manual_preparation',
                           'needs_manual_completion',
                           'needs_manual_merging']

    prior_entries = [x for x in bib_database.entries
                     if x.get('status', 'NA') not in merge_ignore_status]

    prior_entries = [x for x in prior_entries
                     if any(entry_link in x['entry_link'].split(',')
                            for entry_link in required_prior_entry_links)]

    if len(prior_entries) < 1:
        # Note: the first entry is a non_duplicate (by definition)
        if not os.path.exists('non_duplicates.csv'):
            with open('non_duplicates.csv', 'a') as fd:
                fd.write('"ID"\n')
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return

    # df to get_similarities for each other entry
    references = pd.DataFrame.from_dict([entry] + prior_entries)

    # drop the same ID entry
    # Note: the entry is simply added as the first row.
    # references = references[~(references['ID'] == entry['ID'])]
    # dropping them before calculating similarities prevents errors
    # caused by unavailable fields!
    # Note: ignore entries that need manual preparation in the merging
    # (until they have been prepared!)
    references = references[~references['status'].str
                            .contains('|'.join(merge_ignore_status), na=False)]

    # means that all prior entries are tagged as needs_manual_preparation
    if references.shape[0] == 0:
        # entry.update(status = 'processed')
        if not os.path.exists('non_duplicates.csv'):
            with open('non_duplicates.csv', 'a') as fd:
                fd.write('"ID"\n')
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
        return
    references = calculate_similarities_entry(references)

    max_similarity = references.similarity.max()
    citation_key = references.loc[references['similarity'].idxmax()]['ID']
    if max_similarity <= MERGING_NON_DUP_THRESHOLD:
        # Note: if no other entry has a similarity exceeding the threshold,
        # it is considered a non-duplicate (in relation to all other entries)
        if not os.path.exists('non_duplicates.csv'):
            with open('non_duplicates.csv', 'a') as fd:
                fd.write('"ID"\n')
        with open('non_duplicates.csv', 'a') as fd:
            fd.write('"' + entry['ID'] + '"\n')
    if max_similarity > MERGING_NON_DUP_THRESHOLD and \
            max_similarity < MERGING_DUP_THRESHOLD:
        # The needs_manual_merging status is only set
        # for one element of the tuple!
        if not os.path.exists('potential_duplicate_tuples.csv'):
            with open('potential_duplicate_tuples.csv', 'a') as fd:
                fd.write('"ID1","ID2","max_similarity"\n')
        with open('potential_duplicate_tuples.csv', 'a') as fd:
            # to ensure a consistent order
            entry_a, entry_b = sorted([citation_key, entry['ID']])
            line = '"' + entry_a + '","' + entry_b + '","' + \
                str(max_similarity) + '"\n'
            fd.write(line)
    if max_similarity >= MERGING_DUP_THRESHOLD:
        # note: the following status will not be saved in the bib file but
        # in the duplicate_tuples.csv (which will be applied to the bib file
        # in the end)
        if not os.path.exists('duplicate_tuples.csv'):
            with open('duplicate_tuples.csv', 'a') as fd:
                fd.write('"ID1","ID2"\n')
        with open('duplicate_tuples.csv', 'a') as fd:
            fd.write('"' + citation_key + '","' + entry['ID'] + '"\n')

    return


def apply_merges(bib_database):

    # The merging also needs to consider whether citation_keys are propagated
    # Completeness of comparisons should be ensured by the
    # append_merges procedure (which ensures that all prior entries
    # in global queue_order are considered before completing
    # the comparison/adding entries ot the csvs)

    try:
        os.remove('queue_order.csv')
    except FileNotFoundError:
        pass

    merge_details = ''
    # Always merge clear duplicates: row[0] <- row[1]
    if os.path.exists('duplicate_tuples.csv'):
        with open('duplicate_tuples.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                el_to_merge = []
                for entry in bib_database.entries:
                    if entry['ID'] == row[1]:
                        print(f'drop {entry["ID"]}')
                        el_to_merge = entry['entry_link'].split(';')
                        # Drop the duplicated entry
                        bib_database.entries = \
                            [i for i in bib_database.entries
                             if not (i['ID'] == entry['ID'])]
                        break
                for entry in bib_database.entries:
                    if entry['ID'] == row[0]:
                        els = el_to_merge + entry['entry_link'].split(';')
                        els = list(set(els))
                        entry.update(entry_link=str(';'.join(els)))
                        if 'prepared' == entry['status']:
                            entry.update(status='processed')
                        merge_details += row[0] + ' < ' + row[1] + '\n'
                        break

    # Set clear non-duplicates to completely processed (remove the status tag)
    if os.path.exists('non_duplicates.csv'):
        with open('non_duplicates.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                for entry in bib_database.entries:
                    if entry['ID'] == row[0]:
                        if 'prepared' == entry['status']:
                            entry.update(status='processed')
        os.remove('non_duplicates.csv')

    # note: potential_duplicate_tuples need to be processed manually but we
    # tag the second entry (row[1]) as "needs_manual_merging"
    if os.path.exists('potential_duplicate_tuples.csv'):
        with open('potential_duplicate_tuples.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                for entry in bib_database.entries:
                    if (entry['ID'] == row[1]) or (entry['ID'] == row[2]):
                        entry.update(status='needs_manual_merging')
        potential_duplicates = \
            pd.read_csv('potential_duplicate_tuples.csv', dtype=str)
        potential_duplicates.sort_values(by=['max_similarity', 'ID1', 'ID2'],
                                         ascending=False, inplace=True)
        potential_duplicates.to_csv(
            'potential_duplicate_tuples.csv', index=False,
            quoting=csv.QUOTE_ALL, na_rep='NA',
        )

    return bib_database


def create_commit(r, bib_database):

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    merge_details = ''
    if os.path.exists('duplicate_tuples.csv'):
        with open('duplicate_tuples.csv') as read_obj:
            csv_reader = csv.reader(read_obj)
            for row in csv_reader:
                if row[0] != 'ID1':
                    merge_details += row[0] + ' < ' + row[1] + '\n'
        os.remove('duplicate_tuples.csv')

    if merge_details != '':
        merge_details = '\n\nDuplicates removed:\n' + merge_details

    if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)] or \
            MAIN_REFERENCES in r.untracked_files:

        # to avoid failing pre-commit hooks
        bib_database = utils.load_references_bib(
            modification_check=False, initialize=False,
        )
        utils.save_bib_file(bib_database, MAIN_REFERENCES)

        if MAIN_REFERENCES in [item.a_path for item in r.index.diff(None)]:
            r.index.add([MAIN_REFERENCES])
            if os.path.exists('potential_duplicate_tuples.csv'):
                r.index.add(['potential_duplicate_tuples.csv'])

            flag, flag_details = utils.get_version_flags()

            r.index.commit(
                '⚙️ Process duplicates' + flag + flag_details +
                merge_details +
                '\n - ' + utils.get_package_details(),
                author=git.Actor('script:process_duplicates.py', ''),
                committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                                    repo_setup.config['EMAIL']),

            )
        return True
    else:
        print('- No duplicates merged')
        return False


if __name__ == '__main__':
    print('')
