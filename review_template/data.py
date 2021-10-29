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


def get_to_code_in_manuscript(records_for_coding):
    in_manuscript_to_code = []
    print(MANUSCRIPT)
    with open(MANUSCRIPT) as f:
        for line in f:
            if '<!-- NEW_RECORD_SOURCE -->' in line:
                while line != '':
                    line = f.readline()
                    if re.search(r'- @.*', line):
                        citation_key = re.findall(r'- @(.*)$', line)
                        in_manuscript_to_code.append(citation_key[0])
                        if line == '\n':
                            break

    in_manuscript_to_code = [x for x in in_manuscript_to_code
                             if x in records_for_coding]
    return in_manuscript_to_code


def get_synthesized_ids(bib_database):

    records_for_coding = [x['ID']for x in bib_database.entries
                          if x.get('rev_status', 'NA') in
                          ['included', 'in_manuscript']]

    in_manuscript_to_code = get_to_code_in_manuscript(records_for_coding)

    synthesized = set(set(records_for_coding) - set(in_manuscript_to_code))
    return list(synthesized)


def update_manuscript(repo, bib_database):

    synthesized_in_manuscript = get_synthesized_ids(bib_database)
    included = utils.get_included_IDs(bib_database)

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
        return synthesized_in_manuscript

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
                if '_Records to analyze_' not in line:
                    line = '_Records to analyze_:' + line + '\n'
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
            writer.write('<!-- NEW_RECORD_SOURCE -->_Records to analyze_:\n\n')
            for missing_record in missing_records:
                writer.write('- @' + missing_record + '\n')
                logging.info(f' {missing_record}'.ljust(18, ' ') + ' added')

    os.remove(temp)

    nr_entries_added = len(missing_records)
    logging.info(f'{nr_entries_added} records added ({MANUSCRIPT})\n')

    synthesized_in_manuscript = get_synthesized_ids(bib_database)

    return synthesized_in_manuscript


def main():

    repo = git.Repo()
    utils.require_clean_repo(repo, ignore_pattern='paper.md')
    DATA_FORMAT = repo_setup.config['DATA_FORMAT']

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    if 'MANUSCRIPT' == DATA_FORMAT:
        synthesized_in_manuscript = update_manuscript(repo, bib_database)

    # TODO: add other forms of data extraction/analysis/synthesis

    for entry in bib_database.entries:
        # TODO: add other forms of data extraction/analysis/synthesis
        if entry['ID'] in synthesized_in_manuscript:
            entry.update(rev_status='coded')
            logging.info(f'{entry["ID"]}'.ljust(18, ' ') +
                         'set status "coded"')

    utils.save_bib_file(bib_database, repo_setup.paths['MAIN_REFERENCES'])
    repo.index.add([MANUSCRIPT])
    repo.index.add([repo_setup.paths['MAIN_REFERENCES']])

    if 'y' == input('Create commit (y/n)?'):
        utils.create_commit(repo, 'Data and synthesis', manual_author=True)

    return


if __name__ == '__main__':
    main()
