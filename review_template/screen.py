#! /usr/bin/env python
import logging
import pprint
from collections import OrderedDict

import git
from bibtexparser.bibdatabase import BibDatabase

from review_template import process
from review_template import repo_setup
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

key_order = ['ENTRYTYPE',
             'ID',
             'year',
             'author',
             'title',
             'journal',
             'booktitle',
             'volume',
             'number',
             'doi',
             'link',
             'url',
             'fulltext']


def customsort(dict1: dict) -> OrderedDict:
    items = [dict1[k] if k in dict1.keys() else '' for k in key_order]
    sorted_dict = OrderedDict()
    for i in range(len(key_order)):
        sorted_dict[key_order[i]] = items[i]
    return sorted_dict


def get_excl_criteria(ec_string: str) -> list:
    return [ec.split('=')[0] for ec in ec_string.split(';') if ec != 'NA']


def get_exclusion_criteria(bib_db: BibDatabase) -> list:
    ec_string = [x.get('excl_criteria') for x in bib_db.entries
                 if 'excl_criteria' in x]

    if ec_string:
        excl_criteria = get_excl_criteria(ec_string[0])
    else:
        excl_criteria = input('Exclusion criteria (comma separated or NA)')
        excl_criteria = excl_criteria.split(',')
        if '' in excl_criteria:
            excl_criteria = excl_criteria.remove('')
    if 'NA' in excl_criteria:
        excl_criteria = excl_criteria.remove('NA')

    return excl_criteria


def screen() -> None:
    saved_args = locals()
    bib_db = utils.load_main_refs(mod_check=False)
    repo = git.Repo('')
    utils.require_clean_repo(repo, ignore_pattern=MAIN_REFERENCES)

    req = 'prescreened_and_pdf_prepared'
    process.check_delay(bib_db, min_status_requirement=req)

    logging.info('Start screen')

    pp = pprint.PrettyPrinter(indent=4, width=140)

    excl_criteria = get_exclusion_criteria(bib_db)
    if excl_criteria:
        excl_criteria_available = True
    else:
        excl_criteria_available = False
        excl_criteria = ['NA']

    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)
    i, quit_pressed = 0, False
    stat_len = len([x for x in bib_db.entries
                    if 'prescreen_included' == x.get('rev_status', 'NA')])

    for record in bib_db.entries:
        if 'prepared' != record.get('pdf_status', 'NA') or \
                'prescreen_included' != record.get('rev_status', 'NA'):
            continue

        print('\n\n')
        i += 1
        skip_pressed = False
        revrecord = customsort(record)
        pp.pprint(revrecord)

        if excl_criteria_available:
            decisions = []

            for exclusion_criterion in excl_criteria:

                decision, ret = 'NA', 'NA'
                while ret not in ['y', 'n', 'q', 's']:
                    ret = input(f'({i}/{stat_len}) Violates'
                                f' {exclusion_criterion} [y,n,q,s]? ')
                    if 'q' == ret:
                        quit_pressed = True
                    elif 's' == ret:
                        skip_pressed = True
                        continue
                    elif ret in ['y', 'n']:
                        decision = ret

                if quit_pressed or skip_pressed:
                    break

                decisions.append([exclusion_criterion, decision])

            if skip_pressed:
                continue
            if quit_pressed:
                break

            if all([decision == 'n' for ec, decision in decisions]):
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
                decision = decision.replace('y', 'yes').replace('n', 'no')
                ec_field = f'{ec_field}{exclusion_criterion}={decision}'
            record['excl_criteria'] = ec_field.replace(' ', '')

        else:

            decision, ret = 'NA', 'NA'
            while ret not in ['y', 'n', 'q', 's']:
                ret = input(f'({i}/{stat_len}) Include'
                            f' {exclusion_criterion} [y,n,q,s]? ')
                if 'q' == ret:
                    quit_pressed = True
                elif 's' == ret:
                    skip_pressed = True
                    continue
                elif ret in ['y', 'n']:
                    decision = ret

            if quit_pressed:
                break

            if decision == 'y':
                logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                             'Included')
                record.update(rev_status='included')
            if decision == 'n':
                logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                             'Excluded')
                record.update(rev_status='excluded')

            record['excl_criteria'] = 'NA'

        if quit_pressed:
            logging.info('Stop screen')
            break

        utils.save_bib_file(bib_db, MAIN_REFERENCES)

    if stat_len == 0:
        logging.info('No records to screen')
        return

    if i < stat_len:  # if records remain for screening
        if 'y' != input('Create commit (y/n)?'):
            return
    repo.index.add([MAIN_REFERENCES])
    utils.create_commit(repo, 'Screening (manual)',
                        saved_args,
                        manual_author=True)

    return
