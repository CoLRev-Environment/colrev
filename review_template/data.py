#! /usr/bin/env python
import itertools
import json
import logging
import os
import re
import sys

import git
import pandas as pd
import yaml
from yaml import safe_load

from review_template import init
from review_template import repo_setup
from review_template import utils
PAD = 0
MANUSCRIPT = 'paper.md'
DATA = repo_setup.paths['DATA']


def get_data_page_missing(MANUSCRIPT, records):
    available = []
    with open(MANUSCRIPT) as f:
        line = f.read()
        for record in records:
            if record in line:
                available.append(record)

    return list(set(records) - set(available))


def get_to_synthesize_in_manuscript(records_for_synthesis):
    in_manuscript_to_synthesize = []
    with open(MANUSCRIPT) as f:
        for line in f:
            if '<!-- NEW_RECORD_SOURCE -->' in line:
                while line != '':
                    line = f.readline()
                    if re.search(r'- @.*', line):
                        ID = re.findall(r'- @(.*)$', line)
                        in_manuscript_to_synthesize.append(ID[0])
                        if line == '\n':
                            break

    in_manuscript_to_synthesize = [x for x in in_manuscript_to_synthesize
                                   if x in records_for_synthesis]
    return in_manuscript_to_synthesize


def get_synthesized_ids(bib_db):

    records_for_synthesis = [x['ID']for x in bib_db.entries
                             if x.get('rev_status', 'NA') in
                             ['included', 'in_manuscript']]

    in_manuscript_to_synthesize = \
        get_to_synthesize_in_manuscript(records_for_synthesis)
    # Assuming that all records have been added to the MANUSCRIPT before
    synthesized = [x for x in records_for_synthesis
                   if x not in in_manuscript_to_synthesize]

    return synthesized


def get_data_extracted(records_for_data_extraction):
    data_extracted = []
    with open(DATA) as f:
        data_df = pd.json_normalize(safe_load(f))

        for record in records_for_data_extraction:
            drec = data_df.loc[data_df['ID'] == record]
            if 1 == drec.shape[0]:
                if 'TODO' not in drec.iloc[0].tolist():
                    data_extracted.append(drec.loc[0, 'ID'])

    data_extracted = [x for x in data_extracted
                      if x in records_for_data_extraction]
    return data_extracted


def get_structured_data_extracted(bib_db):
    if not os.path.exists(DATA):
        return []

    records_for_data_extraction = [x['ID']for x in bib_db.entries
                                   if x.get('rev_status', 'NA') in
                                   ['included', 'in_manuscript']]

    data_extracted = get_data_extracted(records_for_data_extraction)

    data_extracted = [x for x in data_extracted
                      if x in records_for_data_extraction]

    return data_extracted


def update_manuscript(repo, bib_db, included):

    if os.path.exists(MANUSCRIPT):
        missing_records = get_data_page_missing(MANUSCRIPT, included)
        missing_records = sorted(missing_records)
    else:
        missing_records = included

    if 0 == len(missing_records):
        logging.info(f'All records included in {MANUSCRIPT}')
        return bib_db

    changedFiles = [item.a_path for item in repo.index.diff(None)]
    if MANUSCRIPT in changedFiles:
        logging.error(f'Changes in {MANUSCRIPT}. Use git add {MANUSCRIPT} and '
                      'try again.')
        sys.exit()

    title = 'Manuscript template'
    if os.path.exists('readme.md'):
        with open('readme.md') as f:
            title = f.readline()
            title = title.replace('# ', '').replace('\n', '')
    author = repo_setup.config['GIT_ACTOR']

    if not os.path.exists(MANUSCRIPT):
        init.retrieve_template_file('../template/paper.md', 'paper.md')
        init.inplace_change('paper.md', '{{project_title}}', title)
        init.inplace_change('paper.md', '{{author}}', author)
        logging.info('Created manuscript')
        logging.info('Please update title and authors.')
    else:
        logging.info('Updating manuscript')

    temp = f'.tmp_{MANUSCRIPT}'
    os.rename(MANUSCRIPT, temp)
    with open(temp) as reader, open(MANUSCRIPT, 'w') as writer:
        appended = False
        completed = False
        line = reader.readline()
        while line != '':
            if '<!-- NEW_RECORD_SOURCE -->' in line:
                if '_Records to synthesize' not in line:
                    line = '_Records to synthesize_:' + line + '\n'
                    writer.write(line)
                else:
                    writer.write(line)
                    writer.write('\n')

                for missing_record in missing_records:
                    writer.write('- @' + missing_record + '\n')
                    logging.info(f' {missing_record}'.ljust(PAD, ' ') +
                                 f' added to {MANUSCRIPT}')

                # skip empty lines between to connect lists
                line = reader.readline()
                if '\n' != line:
                    writer.write(line)

                appended = True

            elif appended and not completed:
                if '- @' == line[:3]:
                    writer.write(line)
                else:
                    if '\n' != line:
                        writer.write('\n')
                    writer.write(line)
                    completed = True
            else:
                writer.write(line)
            line = reader.readline()

        if not appended:
            logging.warning('Marker <!-- NEW_RECORD_SOURCE --> not found in '
                            f'{MANUSCRIPT}. Adding records at the end of '
                            'the document.')
            if line != '\n':
                writer.write('\n')
            marker = '<!-- NEW_RECORD_SOURCE -->_Records to synthesize_:\n\n'
            writer.write(marker)
            for missing_record in missing_records:
                writer.write('- @' + missing_record + '\n')
                logging.info(f' {missing_record}'.ljust(PAD, ' ') + ' added')

    os.remove(temp)

    nr_records_added = len(missing_records)
    logging.info(f'{nr_records_added} records added ({MANUSCRIPT})')

    return bib_db


def update_structured_data(repo, bib_db, included):

    if not os.path.exists(DATA):
        included = utils.get_included_IDs(bib_db)

        coding_dimensions = \
            input('Enter columns for data extraction (comma-separted)')
        coding_dimensions = coding_dimensions.replace(' ', '_').split(',')

        data = []
        for included_id in included:
            item = [[included_id], ['TODO'] * len(coding_dimensions)]
            data.append(list(itertools.chain(*item)))

        data_df = pd.DataFrame(data, columns=['ID'] + coding_dimensions)
        data_df.sort_values(by=['ID'], inplace=True)

        with open(DATA, 'w') as f:
            yaml.dump(json.loads(data_df.to_json(orient='records')),
                      f, default_flow_style=False)

    else:

        nr_records_added = 0

        with open(DATA) as f:
            data = pd.json_normalize(safe_load(f))

        for record_id in included:
            # skip when already available
            if 0 < len(data[data['ID'].str.startswith(record_id)]):
                continue

            add_record = pd.DataFrame({'ID': [record_id]})
            add_record = \
                add_record.reindex(columns=data.columns, fill_value='TODO')
            data = pd.concat([data, add_record], axis=0, ignore_index=True)
            nr_records_added = nr_records_added + 1

        data.sort_values(by=['ID'], inplace=True)
        with open(DATA, 'w') as f:
            yaml.dump(json.loads(data.to_json(orient='records')),
                      f, default_flow_style=False)

        logging.info(f'{nr_records_added} records added ({DATA})')

    return


def main(edit_csv, load_csv):
    saved_args = locals()

    DATA_CSV = DATA.replace('.yaml', '.csv')
    if edit_csv:
        with open(DATA) as f:
            data_df = pd.json_normalize(safe_load(f))
            data_df.to_csv(DATA.replace('.yaml', '.csv'), index=False)
            logging.info(f'Created {DATA_CSV} based on {DATA}')
        return

    if load_csv:
        data_df = pd.read_csv(DATA_CSV)
        with open(DATA, 'w') as f:
            yaml.dump(json.loads(data_df.to_json(orient='records')),
                      f, default_flow_style=False)
        logging.info(f'Loaded {DATA_CSV} into {DATA}')
        return

    global PAD
    repo = git.Repo()
    utils.require_clean_repo(repo, ignore_pattern='paper.md')
    DATA_FORMAT = repo_setup.config['DATA_FORMAT']
    bib_db = utils.load_main_refs()
    PAD = min((max(len(x['ID']) for x in bib_db.entries) + 2), 35)

    included = utils.get_included_IDs(bib_db)

    if 0 == len(included):
        logging.info('No records included yet (use review_template screen)')
        sys.exit()

    if 'MANUSCRIPT' in DATA_FORMAT:
        bib_db = update_manuscript(repo, bib_db, included)
        repo.index.add([MANUSCRIPT])
    if 'STRUCTURED' in DATA_FORMAT:
        update_structured_data(repo, bib_db, included)
        repo.index.add([DATA])

    synthesized_in_manuscript = get_synthesized_ids(bib_db)
    structured_data_extracted = get_structured_data_extracted(bib_db)

    for record in bib_db.entries:
        if 'MANUSCRIPT' in DATA_FORMAT and \
                record['ID'] not in synthesized_in_manuscript:
            continue
        if 'STRUCTURED' in DATA_FORMAT and \
                record['ID'] not in structured_data_extracted:
            continue

        record.update(rev_status='synthesized')
        logging.info(f' {record["ID"]}'.ljust(PAD, ' ') +
                     'set status to synthesized')

    utils.save_bib_file(bib_db, repo_setup.paths['MAIN_REFERENCES'])
    repo.index.add([repo_setup.paths['MAIN_REFERENCES']])

    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Data and synthesis',
                            saved_args,
                            manual_author=True)

    return
