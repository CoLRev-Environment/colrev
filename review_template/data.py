#! /usr/bin/env python
import logging
import os
import re
import sys

import git

from review_template import init
from review_template import repo_setup
from review_template import utils

MANUSCRIPT = 'paper.md'


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

    synthesized = \
        set(set(records_for_synthesis) - set(in_manuscript_to_synthesize))
    return list(synthesized)


def update_manuscript(repo, bib_db):

    included = utils.get_included_IDs(bib_db)

    if 0 == len(included):
        logging.info('No records included yet')
        sys.exit()

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

    logging.info('Updating manuscript')

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
        logging.info('Created manuscript.')
        logging.info('Please update title and authors.')

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
                    logging.info(f' {missing_record}'.ljust(
                        18, ' ') + ' added')

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
                logging.info(f' {missing_record}'.ljust(18, ' ') + ' added')

    os.remove(temp)

    nr_entries_added = len(missing_records)
    logging.info(f'{nr_entries_added} records added ({MANUSCRIPT})')

    return bib_db


def main():

    repo = git.Repo()
    utils.require_clean_repo(repo, ignore_pattern='paper.md')
    DATA_FORMAT = repo_setup.config['DATA_FORMAT']
    bib_db = utils.load_main_refs()

    if 'MANUSCRIPT' == DATA_FORMAT:
        bib_db = update_manuscript(repo, bib_db)

    # TODO: add other forms of data extraction/analysis/synthesis
    synthesized_in_manuscript = get_synthesized_ids(bib_db)

    for entry in bib_db.entries:
        # TODO: add other forms of data extraction/analysis/synthesis
        if entry['ID'] in synthesized_in_manuscript:
            entry.update(rev_status='synthesized')
            logging.info(f' {entry["ID"]}'.ljust(18, ' ') +
                         'set status "synthesized"')

    utils.save_bib_file(bib_db, repo_setup.paths['MAIN_REFERENCES'])
    repo.index.add([MANUSCRIPT])
    repo.index.add([repo_setup.paths['MAIN_REFERENCES']])

    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Data and synthesis', manual_author=True)

    return


if __name__ == '__main__':
    main()
