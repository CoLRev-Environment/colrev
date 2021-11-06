#! /usr/bin/env python
import csv
import logging
import os
import pprint
from collections import OrderedDict

import git
import pandas as pd

from review_template import process
from review_template import repo_setup
from review_template import status
from review_template import utils


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
        criteria.append(exclusion_criterion)
    return criteria


def prescreen(include_all=False):
    saved_args = locals()
    if not include_all:
        del saved_args['include_all']

    repo = git.Repo('')
    utils.require_clean_repo(repo)
    bib_db = utils.load_main_refs()
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)

    process.check_delay(bib_db, min_status_requirement='md_processed')

    if include_all:
        for record in bib_db.entries:
            if 'retrieved' != record.get('rev_status', 'NA'):
                continue
            if 'processed' != record.get('md_status', 'NA'):
                continue

            logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                         'Included in prescreen (automatically)')
            record.update(rev_status='prescreen_included')
            record.update(pdf_status='needs_retrieval')
        utils.save_bib_file(
            bib_db, repo_setup.paths['MAIN_REFERENCES'])
        repo.index.add([repo_setup.paths['MAIN_REFERENCES']])
        # Ask whether to create a commit/if records remain for pre-screening
        if 'y' == input('Create commit (y/n)?'):
            utils.create_commit(repo, 'Pre-screening (manual)',
                                saved_args,
                                manual_author=False)

    else:

        print('\n\nRun prescreen')

        pp = pprint.PrettyPrinter(indent=4, width=140)

        print('To stop screening, press ctrl-c')
        try:
            for record in bib_db.entries:
                os.system('cls' if os.name == 'nt' else 'clear')
                # Skip records that have already been screened
                if 'retrieved' != record.get('rev_status', 'NA'):
                    continue
                if 'processed' != record.get('md_status', 'NA'):
                    print(f'Skipping {record["ID"]} - not yet processed')
                    input('Enter to continue')
                    continue

                inclusion_decision = 'TODO'

                while inclusion_decision not in ['y', 'n']:
                    revrecord = customsort(record, desired_order_list)
                    pp.pprint(revrecord)

                    print()
                    inclusion_decision = input('include (y) or exclude (n)?')
                inclusion_decision = inclusion_decision\
                    .replace('y', 'yes')\
                    .replace('n', 'no')
                if 'no' == inclusion_decision:
                    record.update(rev_status='prescreen_excluded')
                    logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                                 'Excluded in prescreen')
                if 'yes' == inclusion_decision:
                    logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                                 'Included in prescreen')
                    record.update(rev_status='prescreen_included')
                    record.update(pdf_status='needs_retrieval')

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
                                saved_args,
                                manual_author=True)

    status.review_instructions()

    return


def export_spreadsheet(bib_db, export_csv):

    tbl = []
    for record in bib_db.entries:
        inclusion_2 = 'NA'
        if 'retrieved' == record['rev_status']:
            inclusion_1 = 'TODO'
        if 'prescreen_excluded' == record['rev_status']:
            inclusion_1 = 'no'
        else:
            inclusion_1 = 'yes'
            inclusion_2 = 'TODO'
            if 'excluded' == record['rev_status']:
                inclusion_2 = 'no'
            else:
                inclusion_2 = 'yes'

        excl_criteria = {}
        if 'excl_criteria' in record:
            for ecrit in record['excl_criteria'].split(';'):
                criteria = {ecrit.split('=')[0]: ecrit.split('=')[1]}
                excl_criteria.update(criteria)

        row = {'ID': record['ID'],
               'author': record.get('author', ''),
               'title': record.get('title', ''),
               'journal': record.get('journal', ''),
               'booktitle': record.get('booktitle', ''),
               'year': record.get('year', ''),
               'volume': record.get('volume', ''),
               'number': record.get('number', ''),
               'pages': record.get('pages', ''),
               'doi': record.get('doi', ''),
               'abstract': record.get('abstract', ''),
               'inclusion_1': inclusion_1,
               'inclusion_2': inclusion_2}
        row.update(excl_criteria)
        tbl.append(row)

    if 'csv' == export_csv.lower():
        screen_df = pd.DataFrame(tbl)
        screen_df.to_csv('screen_table.csv', index=False,
                         quoting=csv.QUOTE_ALL)
        logging.info('Created screen_table (csv)')

    if 'xlsx' == export_csv.lower():
        print('TODO: XLSX')

    return


def import_csv_file(bib_db):
    if not os.path.exists('screen_table.csv'):
        print('Did not find screen_table.csv - exiting.')
        return
    screen_df = pd.read_csv('screen_table.csv')
    screen_df.fillna('', inplace=True)
    records = screen_df.to_dict('records')

    for x in [[x.get('ID', ''),
               x.get('inclusion_1', ''),
               x.get('inclusion_2', '')] for x in records]:
        record = [e for e in bib_db.entries if e['ID'] == x[0]]
        if len(record) == 1:
            record = record[0]
            if x[1] == 'no':
                record['rev_status'] = 'prescreen_excluded'
            if x[1] == 'yes':
                record['rev_status'] = 'prescreen_inclued'
            if x[2] == 'no':
                record['rev_status'] = 'excluded'
            if x[2] == 'yes':
                record['rev_status'] = 'included'
            # TODO: exclusion-criteria

    utils.save_bib_file(
        bib_db, repo_setup.paths['MAIN_REFERENCES'])

    return


def screen(export_csv=None, import_csv=None):
    saved_args = locals()
    if not export_csv:
        del saved_args['export_csv']
    if not import_csv:
        del saved_args['export_csv']
    repo = git.Repo('')
    utils.require_clean_repo(repo)
    bib_db = utils.load_main_refs()

    process.check_delay(bib_db,
                        min_status_requirement='prescreened_and_pdf_prepared')

    if export_csv:
        export_spreadsheet(bib_db, export_csv)
        return
    if import_csv:
        import_csv_file(bib_db)
        return

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
        for record in bib_db.entries:
            if 'prepared' != record.get('pdf_status', 'NA') or \
                    'prescreen_included' != record.get('rev_status', 'NA'):
                continue
            os.system('cls' if os.name == 'nt' else 'clear')

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

            utils.save_bib_file(
                bib_db, repo_setup.paths['MAIN_REFERENCES'])

    except IndexError:
        MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
        print(f'Index error/ID not found in {MAIN_REFERENCES}: {record["ID"]}')
        pass
    except KeyboardInterrupt:
        print('\n\nStopping screen 1\n')
        pass

    repo.index.add([repo_setup.paths['MAIN_REFERENCES']])
    # Ask whether to create a commit/if records remain for screening
    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Screening (manual)',
                            saved_args,
                            manual_author=True)

    return


if __name__ == '__main__':
    prescreen(include_all=False)
    screen()
