#! /usr/bin/env python
import csv
import os
import pprint
from collections import OrderedDict

import git
import pandas as pd

from review_template import repo_setup
from review_template import utils

SCREEN = repo_setup.paths['SCREEN']


def generate_screen_csv(exclusion_criteria):
    data = []

    screen = pd.DataFrame(
        data, columns=[
            'citation_key',
            'inclusion_1',
            'inclusion_2',
        ] + exclusion_criteria + ['comment'],
    )

    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(SCREEN, index=False, quoting=csv.QUOTE_ALL, na_rep='NA')

    return screen


def update_screen(bib_database):

    screen = pd.read_csv(SCREEN, dtype=str)
    screened_records = screen['citation_key'].tolist()
    to_add = [entry['ID'] for entry in bib_database.entries
              if 'processed' == entry['status'] and
              entry['ID'] not in screened_records]
    for paper_to_screen in to_add:
        add_entry = pd.DataFrame({
            'citation_key': [paper_to_screen],
            'inclusion_1': ['TODO'],
            'inclusion_2': ['TODO'],
        })
        add_entry = add_entry.reindex(
            columns=screen.columns, fill_value='TODO',
        )
        add_entry['comment'] = '-'

        screen = pd.concat([screen, add_entry], axis=0, ignore_index=True)
    # To reformat/sort the screen:
    screen.sort_values(by=['citation_key'], inplace=True)
    screen.to_csv(SCREEN, index=False, quoting=csv.QUOTE_ALL, na_rep='NA')

    return


def pre_screen_commit(repo):

    repo.index.add([SCREEN, repo_setup.paths['MAIN_REFERENCES']])

    hook_skipping = 'false'
    if not repo_setup.config['DEBUG_MODE']:
        hook_skipping = 'true'

    repo.index.commit(
        'Pre-screening (manual)' + utils.get_version_flag() +
        utils.get_commit_report(),
        author=git.Actor(repo_setup.config['GIT_ACTOR'],
                         repo_setup.config['EMAIL']),
        committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                            repo_setup.config['EMAIL']),
        skip_hooks=hook_skipping
    )

    return


desired_order_list = ['ENTRYTYPE', 'ID', 'year', 'author',
                      'title', 'journal', 'booktitle',
                      'volume', 'issue', 'doi',
                      'link', 'url', 'fulltext']


def customsort(dict1, key_order):
    items = [dict1[k] if k in dict1.keys() else '' for k in key_order]
    sorted_dict = OrderedDict()
    for i in range(len(key_order)):
        sorted_dict[key_order[i]] = items[i]
    return sorted_dict


def prescreen():

    repo = git.Repo('')
    utils.require_clean_repo(repo)

    print('\n\nRun prescreen')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    if not os.path.exists(SCREEN):
        print('Create screen sheet')
        # Note: Users can include exclusion criteria afterwards
        screen = generate_screen_csv(['ec_exclusion_criterion1'])
    else:
        utils.git_modification_check(SCREEN)

    update_screen(bib_database)
    screen = pd.read_csv(SCREEN, dtype=str)

    # Note: this seems to be necessary to ensure that
    # pandas saves quotes around the last column
    screen.comment = screen.comment.fillna('-')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    print('To stop screening, press ctrl-c')
    try:
        for i, row in screen.iterrows():
            if 'TODO' == row['inclusion_1']:
                os.system('cls' if os.name == 'nt' else 'clear')
                entry = [x for x in bib_database.entries
                         if x['ID'] == row['citation_key']][0]
                if 'processed' != entry.get('status', 'NA'):
                    print(f'Skipping {entry["ID"]} - not yet processed')
                    input('Enter to continue')
                    continue

                inclusion_decision = 'TODO'

                while inclusion_decision not in ['y', 'n']:
                    reventry = customsort(entry, desired_order_list)
                    pp.pprint(reventry)

                    print()
                    inclusion_decision = input('include (y) or exclude (n)?')
                inclusion_decision = inclusion_decision\
                    .replace('y', 'yes')\
                    .replace('n', 'no')
                screen.at[i, 'inclusion_1'] = inclusion_decision
                if 'no' == inclusion_decision:
                    screen.at[i, 'inclusion_2'] = 'NA'
                    for column in screen.columns:
                        if 'ec_' in column:
                            screen.at[i, column] = 'NA'
                if 'yes' == inclusion_decision:
                    entry.update(pdf_status='needs_retrieval')

                screen.sort_values(by=['citation_key'], inplace=True)
                screen.to_csv(
                    SCREEN, index=False,
                    quoting=csv.QUOTE_ALL, na_rep='NA',
                )
                utils.save_bib_file(
                    bib_database, repo_setup.paths['MAIN_REFERENCES'])

    except KeyboardInterrupt:
        print('\n\nstopping screen 1\n')
        pass

    # If records remain for pre-screening, ask whether to create a commit
    if 0 < screen[screen['inclusion_1'] == 'TODO'].shape[0]:
        if 'y' == input('Create commit (y/n)?'):
            pre_screen_commit(repo)
    else:
        pre_screen_commit(repo)

    return


def screen_commit(repo):

    repo = git.Repo('')
    repo.index.add([SCREEN])

    hook_skipping = 'false'
    if not repo_setup.config['DEBUG_MODE']:
        hook_skipping = 'true'

    repo.index.commit(
        'Screening (manual)' + utils.get_version_flag() +
        utils.get_commit_report(),
        author=git.Actor(repo_setup.config['GIT_ACTOR'],
                         repo_setup.config['EMAIL']),
        committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                            repo_setup.config['EMAIL']),
        skip_hooks=hook_skipping
    )

    return


def screen():

    repo = git.Repo('')
    utils.require_clean_repo(repo)

    print('\n\nRun screen')

    assert os.path.exists(SCREEN)
    utils.git_modification_check(SCREEN)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    screen = pd.read_csv(SCREEN, dtype=str)

    print('To stop screening, press ctrl-c')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    exclusion_criteria_available = 0 < len(
        [col for col in screen.columns if col.startswith('ec_')],
    )

    try:
        for i, row in screen.iterrows():
            try:
                if 'TODO' == row['inclusion_2']:
                    os.system('cls' if os.name == 'nt' else 'clear')
                    entry = [x for x in bib_database.entries
                             if x['ID'] == row['citation_key']][0]

                    if 'prepared' != entry.get('pdf_status', 'NA'):
                        print('  - Warning: pdf_status must be "prepared"'
                              ' before screen')
                        continue

                    reventry = customsort(entry, desired_order_list)
                    pp.pprint(reventry)

                    if exclusion_criteria_available:
                        for column in [
                            col for col in screen.columns
                            if col.startswith('ec_')
                        ]:
                            decision = 'TODO'

                            while decision not in ['y', 'n']:
                                decision = \
                                    input('Violates ' + column + ' (y/n)?')
                            decision = \
                                decision.replace('y', 'yes')\
                                        .replace('n', 'no')
                            screen.at[i, column] = decision

                        if all([
                            screen.at[i, col] == 'no' for col in screen.columns
                            if col.startswith('ec_')
                        ]):
                            screen.at[i, 'inclusion_2'] = 'yes'
                            print('Inclusion recorded')
                        else:
                            screen.at[i, 'inclusion_2'] = 'no'
                            print('Exclusion recorded')
                    else:
                        decision = 'TODO'
                        while decision not in ['y', 'n']:
                            decision = input('Include (y/n)?')
                        decision = decision.replace('y', 'yes')\
                                           .replace('n', 'no')
                        screen.at[i, 'inclusion_2'] = 'yes'

                    screen.sort_values(by=['citation_key'], inplace=True)
                    screen.to_csv(
                        SCREEN, index=False,
                        quoting=csv.QUOTE_ALL, na_rep='NA',
                    )
            except IndexError:
                MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
                print('Index error/citation_key not found in ' +
                      f'{MAIN_REFERENCES}: {row["citation_key"]}')
                pass
    except KeyboardInterrupt:
        print('\n\nstopping screen 1\n')
        pass

    # If records remain for screening, ask whether to create a commit
    if 0 < screen[screen['inclusion_2'] == 'TODO'].shape[0]:
        if 'y' == input('Create commit (y/n)?'):
            screen_commit(repo)
    else:
        screen_commit(repo)

    return


if __name__ == '__main__':
    prescreen()
    screen()
