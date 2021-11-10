#! /usr/bin/env python
import logging
import os
import pprint
from collections import OrderedDict

import git

from review_template import process
from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

desired_order_list = ['ENTRYTYPE', 'ID', 'year', 'author',
                      'title', 'journal', 'booktitle',
                      'volume', 'number', 'doi',
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
        if exclusion_criterion != 'NA':
            criteria.append(exclusion_criterion)
    return criteria


def screen():
    saved_args = locals()
    bib_db = utils.load_main_refs()
    repo = git.Repo('')
    utils.require_clean_repo(repo, ignore_pattern=MAIN_REFERENCES)

    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)
    i = 1
    stat_len = len([x for x in bib_db.entries
                    if 'prescreen_included' == x.get('rev_status', 'NA')])

    try:
        req = 'prescreened_and_pdf_prepared'
        process.check_delay(bib_db, min_status_requirement=req)
    except process.DelayRequirement:
        if stat_len > 0:
            logging.info('Prior processing steps not completed'
                         ' (DELAY_AUTOMATED_PROCESSING)')
        else:
            logging.info('No records to screen')
        return
        pass

    logging.info('Run screen')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    ec_string = [x.get('excl_criteria') for x in bib_db.entries
                 if 'excl_criteria' in x]

    if ec_string:
        excl_criteria = get_excl_criteria(ec_string[0])
    else:
        excl_criteria = \
            input('Provide exclusion criteria (comma separated or NA)')
        excl_criteria = excl_criteria.split(',')
        if '' in excl_criteria:
            excl_criteria = excl_criteria.remove('')
    if 'NA' in excl_criteria:
        excl_criteria = excl_criteria.remove('NA')

    if excl_criteria:
        excl_criteria_available = True
    else:
        excl_criteria_available = False
        excl_criteria = ['NA']

    try:
        for record in bib_db.entries:
            if 'prepared' != record.get('pdf_status', 'NA') or \
                    'prescreen_included' != record.get('rev_status', 'NA'):
                continue

            os.system('cls' if os.name == 'nt' else 'clear')
            print(f'{i}/{stat_len}')
            i += 1
            revrecord = customsort(record, desired_order_list)
            pp.pprint(revrecord)

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
                    logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                                 'Included')
                    record.update(rev_status='included')
                else:
                    logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                                 'Excluded')
                    record.update(rev_status='excluded')

                ec_field = ''
                for exclusion_criterion, decision in decisions:
                    if ec_field != '':
                        ec_field = f'{ec_field};'
                    ec_field = f'{ec_field}{exclusion_criterion}={decision}'
                record['excl_criteria'] = ec_field.replace(' ', '')
            else:
                decision = 'TODO'
                while decision not in ['y', 'n']:
                    decision = input('Include (y/n)?')
                if decision == 'y':
                    logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                                 'Included')
                    record.update(rev_status='included')
                if decision == 'n':
                    logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                                 'Excluded')
                    record.update(rev_status='excluded')
                record['excl_criteria'] = 'NA'

            utils.save_bib_file(bib_db, MAIN_REFERENCES)

    except IndexError:
        logging.error('Index error/ID not found '
                      f'in {MAIN_REFERENCES}: {record["ID"]}')
        pass
    except KeyboardInterrupt:
        logging.info('\n\nStopping screen 1\n')
        pass

    repo.index.add([MAIN_REFERENCES])
    # Ask whether to create a commit/if records remain for screening
    if i < stat_len:
        if 'y' != input('Create commit (y/n)?'):
            return
    utils.create_commit(repo, 'Screening (manual)',
                        saved_args,
                        manual_author=True)

    return
