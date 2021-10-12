#! /usr/bin/env python
import csv
import difflib
import os

import ansiwrap
import git
import pandas as pd
from dictdiffer import diff

from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

removed_tuples = []


def get_combined_entry_link_list(entry_a, entry_b):

    els_entry_a = entry_a['entry_link'].split(';')
    els_entry_b = entry_b['entry_link'].split(';')

    combined_el_list = set(els_entry_a
                           + els_entry_b)

    return ';'.join(combined_el_list)


class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_diff(change, prefix_len):
    d = difflib.Differ()

    if change[0] == 'change':
        if change[1] not in ['ID', 'status']:
            letters = list(d.compare(change[2][0], change[2][1]))
            for i in range(len(letters)):
                if letters[i].startswith('  '):
                    letters[i] = letters[i][-1]
                elif letters[i].startswith('+ '):
                    letters[i] = f'{colors.RED}' + \
                        letters[i][-1] + f'{colors.END}'
                elif letters[i].startswith('- '):
                    letters[i] = f'{colors.GREEN}' + \
                        letters[i][-1] + f'{colors.END}'
            prefix = change[1] + ': '
            print(ansiwrap.fill(''.join(letters),
                                initial_indent=prefix.ljust(prefix_len),
                                subsequent_indent=' '*prefix_len))
    elif change[0] == 'add':
        prefix = change[1] + ': '
        print(ansiwrap.fill(f'{colors.RED}{change[2]}{colors.END}',
                            initial_indent=prefix.ljust(prefix_len),
                            subsequent_indent=' '*prefix_len))
    elif change[0] == 'remove':
        prefix = change[1] + ': '
        print(ansiwrap.fill(f'{colors.GREEN}{change[2]}{colors.END}',
                            initial_indent=prefix.ljust(prefix_len),
                            subsequent_indent=' '*prefix_len))
    return


def merge_manual_dialogue(bib_database, main_ID, duplicate_ID, stat):
    global quit_pressed
    global removed_tuples
    # Note: all changes must be made to the main_entry (i.e., if we display
    # the main_entry on the left side and if the user selects "1", this
    # means "no changes to the main entry".)
    # We effectively have to consider only cases in which the user
    # wants to merge fields from the duplicate entry into the main entry

    main_entry = [x for x in bib_database.entries if main_ID == x['ID']][0]
    duplicate_entry = \
        [x for x in bib_database.entries if duplicate_ID == x['ID']][0]

    # Escape sequence to clear terminal output for each new comparison
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"Merge {colors.GREEN}{main_entry['ID']}{colors.END} < " +
          f"{colors.RED}{duplicate_entry['ID']}{colors.END}?\n")

    keys = set(list(main_entry) + list(duplicate_entry))

    differences = list(diff(main_entry, duplicate_entry))

    if len([x[2] for x in differences if 'add' == x[0]]) > 0:
        added_fields = [y[0] for y in [x[2] for x in differences
                                       if 'add' == x[0]][0]]
    else:
        added_fields = []
    if len([x[2] for x in differences if 'remove' == x[0]]) > 0:
        removed_fields = [y[0] for y in [x[2] for x in differences
                                         if 'remove' == x[0]][0]]
    else:
        removed_fields = []
    prefix_len = len(max(keys, key=len) + ': ')
    for key in ['author', 'title',
                'journal', 'booktitle',
                'year', 'volume',
                'number', 'pages',
                'doi', 'ENTRYTYPE']:
        if key in added_fields:
            change = [y for y in [x[2] for x in differences
                                  if 'add' == x[0]][0] if key == y[0]]
            print_diff(('add', *change[0]), prefix_len)
        elif key in removed_fields:
            change = [y for y in [x[2] for x in differences
                                  if 'remove' == x[0]][0] if key == y[0]]
            print_diff(('remove', *change[0]), prefix_len)
        elif key in [x[1] for x in differences]:
            change = [x for x in differences if x[1] == key]
            print_diff(change[0], prefix_len)
        elif key in keys:
            prefix = key + ': '
            print(ansiwrap.fill(main_entry[key],
                                initial_indent=prefix.ljust(prefix_len),
                                subsequent_indent=' '*prefix_len))

    response_string = '(' + stat + ') Merge entries [y,n,d,q,?]? '
    response = input('\n' + response_string)
    while response not in ['y', 'n', 'd', 'q']:
        print(f'y - merge the {colors.RED}red entry{colors.END} into the ' +
              f'{colors.GREEN}green entry{colors.END}')
        print('n - keep both entries (not duplicates)')
        print('d - detailed merge: decide for each field (to be implemented)')
        print('q - stop processing duplicate entries')
        print('? - print help')
        response = input(response_string)

    if 'y' == response:
        # Note: update status and remove the other entry
        combined_el_list = get_combined_entry_link_list(
            main_entry, duplicate_entry)
        # Delete the other entry (entry_a_ID or entry_b_ID)
        main_entry.update(entry_link=combined_el_list)

        main_entry.update(status='processed')
        bib_database.entries = [x for x in bib_database.entries
                                if x['ID'] != duplicate_entry['ID']]
        removed_tuples.append([main_ID, duplicate_ID])

    if 'n' == response:
        # do not merge entries/modify the bib_database
        removed_tuples.append([main_ID, duplicate_ID])
    # 'd' == response: TODO
        # Modification examples:
        # main_entry.update(title='TEST')
        # main_entry.update(title=duplicate_entry['title])

    if 'q' == response:
        quit_pressed = True

    return bib_database


def merge_manual(bib_database, entry_a_ID, entry_b_ID, stat):
    global removed_tuples

    if not all(eid in [x['ID'] for x in bib_database.entries]
               for eid in [entry_a_ID, entry_b_ID]):
        # Note: entry IDs may no longer be in entries
        # due to prior merging operations
        return bib_database

    a_propagated = utils.propagated_citation_key(entry_a_ID)
    b_propagated = utils.propagated_citation_key(entry_b_ID)

    if not a_propagated and not b_propagated:

        # Use the entry['ID'] without appended letters if possible
        # Set a_propagated=True if entry_a_ID should be kept
        if entry_a_ID[-1:].isnumeric() and \
                not entry_b_ID[-1:].isnumeric():
            a_propagated = True
        else:
            b_propagated = True
            # This arbitrarily uses entry_b_ID
            # if none of the IDs has a letter appended.

    if a_propagated and b_propagated:
        print('WARNING: both citation_keys propagated:' +
              f' {entry_a_ID}, {entry_b_ID}')
        return bib_database

    if a_propagated:
        main_ID = \
            [x['ID'] for x in bib_database.entries if entry_a_ID == x['ID']][0]
        duplicate_ID = \
            [x['ID'] for x in bib_database.entries if entry_b_ID == x['ID']][0]
    else:
        main_ID = \
            [x['ID'] for x in bib_database.entries if entry_b_ID == x['ID']][0]
        duplicate_ID = \
            [x['ID'] for x in bib_database.entries if entry_a_ID == x['ID']][0]

    bib_database = \
        merge_manual_dialogue(bib_database, main_ID, duplicate_ID, stat)

    return bib_database


def manual_merge_commit(r):

    r.git.add(update=True)
    # deletion of 'potential_duplicate_tuples.csv' may added to git staging

    hook_skipping = 'false'
    if not repo_setup.config['DEBUG_MODE']:
        hook_skipping = 'true'

    flag, flag_details = utils.get_version_flags()

    r.index.commit(
        'Process duplicates manually' + flag + flag_details +
        '\n - Using man_dedupe.py' +
        '\n - ' + utils.get_package_details(),
        author=git.Actor(repo_setup.config['GIT_ACTOR'],
                         repo_setup.config['EMAIL']),
        committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                            repo_setup.config['EMAIL']),
        skip_hooks=hook_skipping
    )

    return


def main():
    global removed_tuples

    r = git.Repo('')
    utils.require_clean_repo(r)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    potential_duplicate = pd.read_csv('potential_duplicate_tuples.csv')

    first_entry_col = potential_duplicate.columns.get_loc('ID1')
    second_entry_col = potential_duplicate.columns.get_loc('ID2')

    quit_pressed = False
    # Note: the potential_duplicate is ordered according to the last
    # column (similarity)
    stat = ''
    for i in range(0, potential_duplicate.shape[0]):
        entry_a_ID = potential_duplicate.iloc[i, first_entry_col]
        entry_b_ID = potential_duplicate.iloc[i, second_entry_col]

        stat = str(i+1) + '/' + str(potential_duplicate.shape[0])
        bib_database = merge_manual(bib_database, entry_a_ID, entry_b_ID, stat)
        if quit_pressed:
            break

    for entry_a_ID, entry_b_ID in removed_tuples:
        potential_duplicate.drop(potential_duplicate[
            (potential_duplicate['ID1'] == entry_a_ID) &
            (potential_duplicate['ID2'] == entry_b_ID)].index, inplace=True)
        potential_duplicate.drop(potential_duplicate[
            (potential_duplicate['ID1'] == entry_b_ID) &
            (potential_duplicate['ID2'] == entry_a_ID)].index, inplace=True)

    not_completely_processed = potential_duplicate['ID1'].tolist() + \
        potential_duplicate['ID2'].tolist()

    for entry in bib_database.entries:
        if entry['ID'] not in not_completely_processed and \
                'needs_manual_merging' == entry['status']:
            entry['status'] = 'processed'

    if potential_duplicate.shape[0] == 0:
        os.remove('potential_duplicate_tuples.csv')
    else:
        potential_duplicate.to_csv('potential_duplicate_tuples.csv',
                                   index=False,
                                   quoting=csv.QUOTE_ALL)

    utils.save_bib_file(bib_database, MAIN_REFERENCES)

    # If there are remaining duplicates, ask whether to create a commit
    if not stat.split('/')[0] == stat.split('/')[1]:
        if 'y' == input('Create commit (y/n)?'):
            manual_merge_commit()
    else:
        manual_merge_commit()


if __name__ == '__main__':
    main()
