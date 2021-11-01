#! /usr/bin/env python
import itertools
import multiprocessing as mp
import os
import pprint
from itertools import chain

import bibtexparser
import dictdiffer
import git
from bashplotlib.histogram import plot_hist
from bibtexparser.customization import convert_to_unicode

from review_template import dedupe
from review_template import repo_setup
from review_template import utils


def load_entries(bib_file):

    with open(bib_file) as bibtex_file:
        individual_bib_db = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)
        search_file = os.path.basename(bib_file)
        for entry in individual_bib_db.entries:
            entry['origin'] = search_file + '/' + entry['ID']

    return individual_bib_db.entries


def get_search_entries():

    pool = mp.Pool(repo_setup.config['CPUS'])
    entries = pool.map(load_entries, utils.get_bib_files())
    entries = list(chain(*entries))

    return entries


def validate_preparation_changes(bib_db, search_entries):

    print('Calculating preparation differences...')
    change_diff = []
    for entry in bib_db.entries:
        if 'changed_in_target_commit' not in entry:
            continue
        del entry['changed_in_target_commit']
        del entry['rev_status']
        del entry['md_status']
        del entry['pdf_status']
        # del entry['origin']
        for cur_entry_link in entry['origin'].split(';'):
            prior_entries = [x for x in search_entries
                             if cur_entry_link in x['origin'].split(',')]
            for prior_entry in prior_entries:
                similarity = dedupe.get_entry_similarity(entry, prior_entry)
                change_diff.append([entry['ID'], cur_entry_link, similarity])

    change_diff = [[e1, e2, 1-sim] for [e1, e2, sim] in change_diff if sim < 1]
    # sort according to similarity
    change_diff.sort(key=lambda x: x[2], reverse=True)

    if 0 == len(change_diff):
        print('No substantial differences found.')

    plot_hist([sim for [e1, e2, sim] in change_diff],
              bincount=100, xlab=True, showSummary=True)
    input('continue')

    pp = pprint.PrettyPrinter(indent=4)
    for eid, entry_link, difference in change_diff:
        # Escape sequence to clear terminal output for each new comparison
        os.system('cls' if os.name == 'nt' else 'clear')
        print('Entry with ID: ' + eid)

        print('Difference: ' + str(round(difference, 4)) + '\n\n')
        entry_1 = [x for x in search_entries if entry_link == x['origin']]
        pp.pprint(entry_1[0])
        entry_2 = [x for x in bib_db.entries if eid == x['ID']]
        pp.pprint(entry_2[0])

        print('\n\n')
        for diff in list(dictdiffer.diff(entry_1, entry_2)):
            # Note: may treat fields differently (e.g., status, ID, ...)
            pp.pprint(diff)

        if 'n' == input('continue (y/n)?'):
            break
        # input('TODO: correct? if not, replace current entry with old one')

    return


def validate_merging_changes(bib_db, search_entries):

    os.system('cls' if os.name == 'nt' else 'clear')
    print('Calculating differences between merged records...')
    change_diff = []
    merged_entries = False
    for entry in bib_db.entries:
        if 'changed_in_target_commit' not in entry:
            continue
        del entry['changed_in_target_commit']
        if ';' in entry['origin']:
            merged_entries = True
            els = entry['origin'].split(';')
            duplicate_el_pairs = list(itertools.combinations(els, 2))
            for el_1, el_2 in duplicate_el_pairs:
                entry_1 = [x for x in search_entries if el_1 == x['origin']]
                entry_2 = [x for x in search_entries if el_2 == x['origin']]

                similarity = \
                    dedupe.get_entry_similarity(entry_1[0], entry_2[0])
                change_diff.append([el_1, el_2, similarity])

    change_diff = [[e1, e2, 1-sim] for [e1, e2, sim] in change_diff if sim < 1]

    # sort according to similarity
    change_diff.sort(key=lambda x: x[2], reverse=True)

    if 0 == len(change_diff):
        if merged_entries:
            print('No substantial differences found.')
        else:
            print('No merged entries')

    pp = pprint.PrettyPrinter(indent=4)

    for el_1, el_2, difference in change_diff:
        # Escape sequence to clear terminal output for each new comparison
        os.system('cls' if os.name == 'nt' else 'clear')

        print('Differences between merged entries:' +
              f' {round(difference, 4)}\n\n')
        entry_1 = [x for x in search_entries if el_1 == x['origin']]
        pp.pprint(entry_1[0])
        entry_2 = [x for x in search_entries if el_2 == x['origin']]
        pp.pprint(entry_2[0])

        if 'n' == input('continue (y/n)?'):
            break
        # TODO: explain users how to change it/offer option to reverse!

    return


def load_bib_db(target_commit):

    if 'none' == target_commit:
        print('Loading data...')
        bib_db = utils.load_main_refs(mod_check=False)
        [x.update(changed_in_target_commit='True') for x in bib_db.entries]

    else:
        print('Loading data from history...')
        repo = git.Repo()

        MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

        revlist = (
            (commit.hexsha, (commit.tree / MAIN_REFERENCES).data_stream.read())
            for commit in repo.iter_commits(paths=MAIN_REFERENCES)
        )
        found = False
        for commit, filecontents in list(revlist):
            if found:  # load the MAIN_REFERENCES in the following commit
                prior_bib_db = bibtexparser.loads(filecontents)
                break
            if commit == target_commit:
                bib_db = bibtexparser.loads(filecontents)
                found = True

        # determine which entries have been changed (prepared or merged)
        # in the target_commit
        for entry in bib_db.entries:
            prior_entry = [x for x in prior_bib_db.entries
                           if x['ID'] == entry['ID']][0]
            # Note: the following is an exact comparison of all fields
            if entry != prior_entry:
                entry.update(changed_in_target_commit='True')

    return bib_db


def main(scope, target_commit):

    # TODO: extension: filter for changes of contributor (git author)

    bib_db = load_bib_db(target_commit)

    # Note: search entries are considered immutable
    # we therefore load the latest files
    search_entries = get_search_entries()

    if 'prepare' == scope or 'all' == scope:
        validate_preparation_changes(bib_db, search_entries)

    if 'merge' == scope or 'all' == scope:
        validate_merging_changes(bib_db, search_entries)

    return


if __name__ == '__main__':
    main()
