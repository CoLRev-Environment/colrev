#! /usr/bin/env python
import csv
import logging
import os
import pprint

import git
import pandas as pd
from bibtexparser.bibdatabase import BibDatabase

from review_template import process
from review_template import repo_setup
from review_template import screen
from review_template import status
from review_template import utils

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
PAD = 0


def export_table(bib_db: BibDatabase,
                 export_table_format: str) -> None:

    tbl = []
    for record in bib_db.entries:

        if 'retrieved' == record['rev_status']:
            inclusion_1 = 'TODO'
        if 'prescreen_excluded' == record['rev_status']:
            inclusion_1 = 'no'
        else:
            inclusion_1 = 'yes'
            inclusion_2 = 'TODO'
            if 'excluded' == record['rev_status']:
                inclusion_2 = 'no'
            if record['rev_status'] in ['included', 'synthesized', 'coded']:
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

    if 'csv' == export_table_format.lower():
        screen_df = pd.DataFrame(tbl)
        screen_df.to_csv('screen_table.csv', index=False,
                         quoting=csv.QUOTE_ALL)
        logging.info('Created screen_table (csv)')

    if 'xlsx' == export_table_format.lower():
        print('TODO: XLSX')

    return


def import_table(bib_db: BibDatabase,
                 import_table_path: str) -> None:
    if not os.path.exists(import_table_path):
        logging.error(f'Did not find {import_table_path} - exiting.')
        return
    screen_df = pd.read_csv(import_table_path)
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

    utils.save_bib_file(bib_db)

    return


def include_all_in_prescreen(bib_db: BibDatabase,
                             repo: git.Repo,
                             saved_args: dict) -> None:

    for record in bib_db.entries:
        if record.get('rev_status', 'NA') in ['retrieved', 'processed']:
            continue
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     'Included in prescreen (automatically)')
        record.update(rev_status='prescreen_included')
        record.update(pdf_status='needs_retrieval')

    utils.save_bib_file(bib_db)
    repo.index.add([MAIN_REFERENCES])
    # Ask whether to create a commit/if records remain for pre-screening
    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Pre-screening (manual)',
                            saved_args,
                            manual_author=False)

    return


def prescreen(bib_db: BibDatabase,
              repo: git.Repo,
              saved_args: dict) -> None:

    logging.info('Start prescreen')

    pp = pprint.PrettyPrinter(indent=4, width=140)
    i, quit_pressed = 1, False
    stat_len = len([x for x in bib_db.entries
                    if 'retrieved' == x.get('rev_status', 'NA')])

    for record in bib_db.entries:

        if 'retrieved' != record.get('rev_status', 'NA'):
            continue

        print('\n\n')
        revrecord = screen.customsort(record, screen.desired_order_list)
        pp.pprint(revrecord)

        ret, inclusion_decision = 'NA', 'NA'
        while ret not in ['y', 'n', 's', 'q']:
            ret = input(f'({i}/{stat_len}) Include this record [y,n,q,s]? ')
            if 'q' == ret:
                quit_pressed = True
            elif 's' == ret:
                continue
            else:
                inclusion_decision = ret.replace('y', 'yes').replace('n', 'no')
        i += 1

        if quit_pressed:
            logging.info('Stop prescreen')
            break

        if 'no' == inclusion_decision:
            record.update(rev_status='prescreen_excluded')
            logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                         'Excluded in prescreen')
        if 'yes' == inclusion_decision:
            logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                         'Included in prescreen')
            record.update(rev_status='prescreen_included')
            record.update(pdf_status='needs_retrieval')

        utils.save_bib_file(bib_db)

    if 0 == stat_len:
        logging.info('No records to prescreen')

    else:
        if i < stat_len:  # if records remain for pre-screening
            if 'y' != input('Create commit (y/n)?'):
                return
        repo.index.add([MAIN_REFERENCES])
        utils.create_commit(repo, 'Pre-screening (manual)',
                            saved_args,
                            manual_author=True)
    return


def main(include_all: bool = False,
         export_table_format: str = None,
         import_table_path: str = None) -> None:
    saved_args = locals()
    bib_db = utils.load_main_refs()

    if export_table_format:
        export_table(bib_db, export_table_format)
    elif import_table_path:
        import_table(bib_db, import_table_path)
    else:
        del saved_args['export_table_format']
        del saved_args['import_table_path']
        repo = git.Repo('')
        utils.require_clean_repo(repo, ignore_pattern=MAIN_REFERENCES)
        process.check_delay(bib_db, min_status_requirement='md_processed')
        global PAD
        PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)

        if include_all:
            include_all_in_prescreen(bib_db, repo, saved_args)
        else:
            del saved_args['include_all']
            prescreen(bib_db, repo, saved_args)
        status.review_instructions()

    return
