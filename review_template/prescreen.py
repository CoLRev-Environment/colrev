#! /usr/bin/env python
import csv
import logging
import os
import pprint

import git
import pandas as pd

from review_template import process
from review_template import repo_setup
from review_template import screen
from review_template import status
from review_template import utils


MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']


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

    utils.save_bib_file(bib_db, MAIN_REFERENCES)

    return


def prescreen(include_all=False, export_csv=None, import_csv=None):
    saved_args = locals()
    bib_db = utils.load_main_refs()
    if not include_all:
        del saved_args['include_all']
    if export_csv:
        export_spreadsheet(bib_db, export_csv)
        return
    else:
        del saved_args['export_csv']
    if import_csv:
        import_csv_file(bib_db)
        return
        del saved_args['import_csv']

    repo = git.Repo('')
    utils.require_clean_repo(repo)
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
        utils.save_bib_file(bib_db, MAIN_REFERENCES)
        repo.index.add([MAIN_REFERENCES])
        # Ask whether to create a commit/if records remain for pre-screening
        if 'y' == input('Create commit (y/n)?'):
            utils.create_commit(repo, 'Pre-screening (manual)',
                                saved_args,
                                manual_author=False)

    else:

        logging.info('Run prescreen')

        pp = pprint.PrettyPrinter(indent=4, width=140)

        i = 1
        stat_len = len([x for x in bib_db.entries
                        if 'retrieved' == x.get('rev_status', 'NA')])
        if 0 == stat_len:
            logging.info('No records to prescreen')
            return

        try:
            for record in bib_db.entries:
                # Skip records that have already been screened
                if 'retrieved' != record.get('rev_status', 'NA'):
                    continue
                if 'processed' != record.get('md_status', 'NA'):
                    print(f'Skipping {record["ID"]} - not yet processed')
                    input('Enter to continue')
                    continue

                inclusion_decision = 'TODO'

                os.system('cls' if os.name == 'nt' else 'clear')
                print(f'{i}/{stat_len}')
                i += 1
                revrecord = screen.customsort(record,
                                              screen.desired_order_list)
                pp.pprint(revrecord)

                while inclusion_decision not in ['y', 'n']:
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

                utils.save_bib_file(bib_db, MAIN_REFERENCES)

        except KeyboardInterrupt:
            print('\n\nstopping screen 1\n')
            pass
        os.system('cls' if os.name == 'nt' else 'clear')

        repo.index.add([MAIN_REFERENCES])
        # Ask whether to create a commit/if records remain for pre-screening
        if i < stat_len:
            if 'y' != input('Create commit (y/n)?'):
                return
        utils.create_commit(repo, 'Pre-screening (manual)',
                            saved_args,
                            manual_author=True)

    status.review_instructions()

    return
