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


def get_excl_criteria(ec_string):
    criteria = []
    for exclusion_criterion in ec_string.split(';'):
        exclusion_criterion = exclusion_criterion.split('=')[0]
        criteria.append(exclusion_criterion)
    return criteria


def prescreen(include_all):

    repo = git.Repo('')
    utils.require_clean_repo(repo)
    bib_db = utils.load_main_refs()
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)

    process.check_delay(bib_db, min_status_requirement='md_processed')

    if include_all:
        for entry in bib_db.entries:
            if 'retrieved' != entry.get('rev_status', 'NA'):
                continue
            if 'processed' != entry.get('md_status', 'NA'):
                continue

            logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                         'Included in prescreen (automatically)')
            entry.update(rev_status='prescreen_included')
            entry.update(pdf_status='needs_retrieval')
        utils.save_bib_file(
            bib_db, repo_setup.paths['MAIN_REFERENCES'])
        repo.index.add([repo_setup.paths['MAIN_REFERENCES']])
        # Ask whether to create a commit/if records remain for pre-screening
        if 'y' == input('Create commit (y/n)?'):
            utils.create_commit(repo, 'Pre-screening (manual)',
                                manual_author=False)

    else:

        print('\n\nRun prescreen')

        pp = pprint.PrettyPrinter(indent=4, width=140)

        print('To stop screening, press ctrl-c')
        try:
            for entry in bib_db.entries:
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
                    logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                                 'Excluded in prescreen')
                if 'yes' == inclusion_decision:
                    logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                                 'Included in prescreen')
                    entry.update(rev_status='prescreen_included')
                    entry.update(pdf_status='needs_retrieval')

                utils.save_bib_file(
                    bib_db, repo_setup.paths['MAIN_REFERENCES'])

        except KeyboardInterrupt:
            print('\n\nstopping screen 1\n')
            pass
        os.system('cls' if os.name == 'nt' else 'clear')

        repo.index.add([repo_setup.paths['MAIN_REFERENCES']])
        # Ask whether to create a commit/if records remain for pre-screening
        if 'y' == input('Create commit (y/n)?'):
            utils.create_commit(repo, 'Pre-screening (manual)',
                                manual_author=True)

    status.review_instructions()

    return


def screen():

    repo = git.Repo('')
    utils.require_clean_repo(repo)
    bib_db = utils.load_main_refs()

    process.check_delay(bib_db,
                        min_status_requirement='prescreened_and_pdf_prepared')

    print('\n\nRun screen')

    print('To stop screening, press ctrl-c')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    ec_string = [x.get('excl_criteria') for x in bib_db.entries
                 if 'excl_criteria' in x]

    if ec_string:
        excl_criteria = get_excl_criteria(ec_string[0])
    else:
        excl_criteria = input('Provide exclusion criteria (comma separated)')
        excl_criteria = excl_criteria.split(',')

    excl_criteria_available = (0 < len(excl_criteria))
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)
    try:
        for entry in bib_db.entries:
            if 'prepared' != entry.get('pdf_status', 'NA') or \
                    'prescreen_included' != entry.get('rev_status', 'NA'):
                continue
            os.system('cls' if os.name == 'nt' else 'clear')

            reventry = customsort(entry, desired_order_list)
            pp.pprint(reventry)

            if excl_criteria_available:
                decisions = []
                for exclusion_criterion in excl_criteria:
                    decision = 'TODO'

                    while decision not in ['y', 'n']:
                        # if [''] == excl_criteria:
                        #     decision = \
                        #       nput(f'Include {exclusion_criterion} (y/n)?')
                        #     decision = \
                        #         decision.replace('y', 'no')\
                        #                 .replace('n', 'yes')
                        # else:
                        decision = \
                            input(f'Violates {exclusion_criterion} (y/n)?')
                    decision = \
                        decision.replace('y', 'yes')\
                                .replace('n', 'no')
                    decisions.append([exclusion_criterion, decision])
                if all([decision == 'no' for ec, decision in decisions]):
                    logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                                 'Included')
                    entry.update(rev_status='included')
                else:
                    logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                                 'Excluded')
                    entry.update(rev_status='excluded')

                ec_field = ''
                for exclusion_criterion, decision in decisions:
                    if ec_field != '':
                        ec_field = f'{ec_field};'
                    ec_field = f'{ec_field}{exclusion_criterion}={decision}'
                entry['excl_criteria'] = ec_field.replace(' ', '')
            else:
                decision = 'TODO'
                while decision not in ['y', 'n']:
                    decision = input('Include (y/n)?')
                if decision == 'y':
                    logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                                 'Included')
                    entry.update(rev_status='included')
                if decision == 'n':
                    logging.info(f' {entry["ID"]}'.ljust(PAD, ' ') +
                                 'Excluded')
                    entry.update(rev_status='excluded')

            utils.save_bib_file(
                bib_db, repo_setup.paths['MAIN_REFERENCES'])

    except IndexError:
        MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
        print(f'Index error/ID not found in {MAIN_REFERENCES}: {entry["ID"]}')
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
    prescreen(include_all=False)
    screen()
