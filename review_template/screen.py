#! /usr/bin/env python
import logging
import os
import pprint
from collections import OrderedDict

import git

from review_template import process
from review_template import repo_setup
from review_template import status
from review_template import utils


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
    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )
    process.check_delay(bib_database, min_status_requirement='md_processed')

    print('\n\nRun prescreen')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    print('To stop screening, press ctrl-c')
    try:
        for entry in bib_database.entries:
            os.system('cls' if os.name == 'nt' else 'clear')
            # Skip records that have already been screened
            if 'retrieved' != entry.get('rev_status', 'NA'):
                continue
            if 'processed' != entry.get('md_status', 'NA'):
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
            if 'no' == inclusion_decision:
                entry.update(rev_status='prescreen_excluded')
                logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                             'Excluded in prescreen')
            if 'yes' == inclusion_decision:
                logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                             'Included in prescreen')
                entry.update(rev_status='prescreen_included')
                entry.update(pdf_status='needs_retrieval')

            utils.save_bib_file(
                bib_database, repo_setup.paths['MAIN_REFERENCES'])

    except KeyboardInterrupt:
        print('\n\nstopping screen 1\n')
        pass
    os.system('cls' if os.name == 'nt' else 'clear')

    repo.index.add([repo_setup.paths['MAIN_REFERENCES']])
    # Ask whether to create a commit/if records remain for pre-screening
    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Pre-screening (manual)', manual_author=True)

    status.review_instructions()

    return


def screen():

    repo = git.Repo('')
    utils.require_clean_repo(repo)
    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )
    process.check_delay(bib_database,
                        min_status_requirement='prescreened_and_pdf_prepared')

    print('\n\nRun screen')

    print('To stop screening, press ctrl-c')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    # exclusion_criteria = load_exclusion_criteria()
    # col.startswith('ec_')

    exclusion_criteria = input('Provide exclusion criteria (comma separated)')
    exclusion_criteria = exclusion_criteria.split(',')
    exclusion_criteria = ['ec_' + x for x in exclusion_criteria]

    exclusion_criteria_available = 0 < len(exclusion_criteria)

    try:
        for entry in bib_database.entries:
            if 'prepared' != entry.get('pdf_status', 'NA') or \
                    'prescreen_included' != entry.get('rev_status', 'NA'):
                continue
            os.system('cls' if os.name == 'nt' else 'clear')

            reventry = customsort(entry, desired_order_list)
            pp.pprint(reventry)

            if exclusion_criteria_available:
                for exclusion_criterion in exclusion_criteria:
                    decision = 'TODO'

                    while decision not in ['y', 'n']:
                        decision = \
                            input(f'Violates {exclusion_criterion} (y/n)?')
                    decision = \
                        decision.replace('y', 'yes')\
                                .replace('n', 'no')
                    entry[exclusion_criterion] = decision
                if all([
                    entry.get(exclusion_criterion) == 'no'
                    for exclusion_criterion in exclusion_criteria
                ]):
                    logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                                 'Included')
                    entry.update(rev_status='included')
                else:
                    logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                                 'Excluded')
                    entry.update(rev_status='excluded')
            else:
                decision = 'TODO'
                while decision not in ['y', 'n']:
                    decision = input('Include (y/n)?')
                if decision == 'y':
                    logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                                 'Included')
                    entry.update(rev_status='included')
                if decision == 'n':
                    logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                                 'Excluded')
                    entry.update(rev_status='excluded')

            utils.save_bib_file(
                bib_database, repo_setup.paths['MAIN_REFERENCES'])

    except IndexError:
        MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
        print('Index error/citation_key not found in ' +
              f'{MAIN_REFERENCES}: {entry["ID"]}')
        pass
    except KeyboardInterrupt:
        print('\n\nStopping screen 1\n')
        pass

    repo.index.add([repo_setup.paths['MAIN_REFERENCES']])
    # Ask whether to create a commit/if records remain for screening
    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Screening (manual)', manual_author=True)

    return


if __name__ == '__main__':
    prescreen()
    screen()
