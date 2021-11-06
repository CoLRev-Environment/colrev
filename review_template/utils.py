#!/usr/bin/env python3
import inspect
import io
import logging
import os
import pkgutil
import re
import sys
import unicodedata
from contextlib import redirect_stdout
from importlib.metadata import version
from string import ascii_lowercase

import bibtexparser
import git
import pandas as pd
import yaml
from bibtexparser.bibdatabase import BibDatabase
from bibtexparser.bparser import BibTexParser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.customization import convert_to_unicode

import docker
from review_template import prepare
from review_template import repo_setup
from review_template import status

MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
DATA = repo_setup.paths['DATA']
SEARCH_DETAILS = repo_setup.paths['SEARCH_DETAILS']


def rmdiacritics(char):
    '''
    Return the base character of char, by "removing" any
    diacritics like accents or curls and strokes and the like.
    '''
    desc = unicodedata.name(char)
    cutoff = desc.find(' WITH ')
    if cutoff != -1:
        desc = desc[:cutoff]
        try:
            char = unicodedata.lookup(desc)
        except KeyError:
            pass  # removing "WITH ..." produced an invalid name
    return char


def remove_accents(input_str):
    try:
        nfkd_form = unicodedata.normalize('NFKD', input_str)
        wo_ac = [
            rmdiacritics(c)
            for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac = ''.join(wo_ac)
    except ValueError:
        wo_ac = input_str
        pass
    return wo_ac


class CitationKeyPropagationError(Exception):
    pass


def propagated_ID(ID):

    propagated = False

    if os.path.exists(DATA):
        # Note: this may be redundant, but just to be sure:
        data = pd.read_csv(DATA, dtype=str)
        if ID in data['ID'].tolist():
            propagated = True

    # TODO: also check data_pages?

    return propagated


def generate_ID(record, bib_db=None, record_in_bib_db=False,
                raise_error=True):
    if bib_db is not None:
        ID_blacklist = [record['ID'] for record in bib_db.entries]
    else:
        ID_blacklist = None
    ID = generate_ID_blacklist(record, ID_blacklist, record_in_bib_db,
                               raise_error)
    return ID


def generate_ID_blacklist(record, ID_blacklist=None,
                          record_in_bib_db=False,
                          raise_error=True):

    # Make sure that IDs that have been propagated to the
    # screen or data will not be replaced
    # (this would break the chain of evidence)
    if raise_error:
        if propagated_ID(record['ID']):
            raise CitationKeyPropagationError(
                'WARNING: do not change IDs that have been ' +
                f'propagated to {DATA} ({record["ID"]})')

    if 'author' in record:
        authors = prepare.format_author_field(record['author'])
    else:
        authors = ''

    if ' and ' in authors:
        authors = authors.split(' and ')
    else:
        authors = [authors]

    # Use family names
    for author in authors:
        if ',' in author:
            author = author.split(',')[0]
        else:
            author = author.split(' ')[0]

    ID_PATTERN = repo_setup.config['ID_PATTERN']

    assert ID_PATTERN in ['FIRST_AUTHOR', 'THREE_AUTHORS']
    if 'FIRST_AUTHOR' == ID_PATTERN:
        temp_ID = f'{author.replace(" ", "")}{str(record.get("year", ""))}'

    if 'THREE_AUTHORS' == ID_PATTERN:
        temp_ID = ''
        indices = len(authors)
        if len(authors) > 3:
            indices = 3
        for ind in range(0, indices):
            temp_ID = temp_ID + \
                f'{authors[ind].split(",")[0].replace(" ", "")}'
        if len(authors) > 3:
            temp_ID = temp_ID + 'EtAl'
        temp_ID = temp_ID + str(record.get('year', ''))

    if temp_ID.isupper():
        temp_ID = temp_ID.capitalize()
    # Replace special characters
    # (because IDs may be used as file names)
    temp_ID = remove_accents(temp_ID)
    temp_ID = re.sub(r'\(.*\)', '', temp_ID)
    temp_ID = re.sub('[^0-9a-zA-Z]+', '', temp_ID)

    if ID_blacklist is not None:
        if record_in_bib_db:
            # allow IDs to remain the same.
            other_ids = ID_blacklist
            # Note: only remove it once. It needs to change when there are
            # other records with the same ID
            if record['ID'] in other_ids:
                other_ids.remove(record['ID'])
        else:
            # ID can remain the same, but it has to change
            # if it is already in bib_db
            other_ids = ID_blacklist

        letters = iter(ascii_lowercase)
        while temp_ID in other_ids:
            try:
                next_letter = next(letters)
                if next_letter == 'a':
                    temp_ID = temp_ID + next_letter
                else:
                    temp_ID = temp_ID[:-1] + next_letter
            except StopIteration:
                letters = iter(ascii_lowercase)
                pass

    return temp_ID


def set_IDs(bib_db):
    ID_list = [record['ID'] for record in bib_db.entries]
    for record in bib_db.entries:
        if record['md_status'] in ['imported', 'prepared']:
            old_id = record['ID']
            new_id = generate_ID_blacklist(
                record, ID_list,
                record_in_bib_db=True,
                raise_error=False)
            record.update(ID=new_id)
            if old_id != new_id:
                logging.info(f'set_ID({old_id}) to {new_id}')
            ID_list.append(record['ID'])
    return bib_db


def load_main_refs(mod_check=None, init=None):
    if mod_check is None:
        mod_check = True
    if init is None:
        init = False

    if os.path.exists(os.path.join(os.getcwd(), MAIN_REFERENCES)):
        if mod_check:
            git_modification_check(MAIN_REFERENCES)
        with open(MAIN_REFERENCES) as target_db:
            bib_db = BibTexParser(
                customization=convert_to_unicode,
                ignore_nonstandard_types=False,
                common_strings=True,
            ).parse_file(target_db, partial=True)
    else:
        if init:
            bib_db = BibDatabase()
        else:
            print(f'{MAIN_REFERENCES} does not exist')
            sys.exit()

    return bib_db


def git_modification_check(filename):
    repo = git.Repo()
    index = repo.index
    if filename in [record.a_path for record in index.diff(None)]:
        print(
            f'WARNING: There are changes in {filename}',
            ' that are not yet added to the git index. ',
            'They may be overwritten by this script. ',
            f'Please consider to MANUALLY add the {filename}',
            ' to the index before executing script.',
        )
        if 'y' != input('override changes (y/n)?'):
            sys.exit()
    return


def get_bib_files():
    bib_files = []
    search_dir = os.path.join(os.getcwd(), 'search/')
    bib_files = [os.path.join(search_dir, x)
                 for x in os.listdir(search_dir) if x.endswith('.bib')]
    return bib_files


def get_included_IDs(db):
    included = []
    for record in db.entries:
        if record.get('rev_status', 'NA') in ['included', 'synthesized']:
            included.append(record['ID'])
    return included


def save_bib_file(bib_db, target_file=None):

    if target_file is None:
        target_file = MAIN_REFERENCES

    writer = BibTexWriter()

    writer.contents = ['entries', 'comments']
    # Note: IDs should be at the beginning to facilitate git versioning
    writer.display_order = [
        'origin',
        'rev_status',
        'md_status',
        'pdf_status',
        'excl_criteria',
        'doi',
        'author',
        'booktitle',
        'journal',
        'title',
        'year',
        'editor',
        'number',
        'pages',
        'series',
        'volume',
        'abstract',
        'book-author',
        'book-group-author',
        'file',
    ]

    try:
        bib_db.comments.remove('% Encoding: UTF-8')
    except ValueError:
        pass

    writer.order_entries_by = ('ID', 'author', 'year')
    writer.add_trailing_comma = True
    writer.align_values = True
    writer.indent = '  '
    bibtex_str = bibtexparser.dumps(bib_db, writer)

    with open(target_file, 'w') as out:
        out.write(bibtex_str)

    return


def require_clean_repo(repo=None, ignore_pattern=None):
    if repo is None:
        repo = git.Repo('')
    if repo.is_dirty():
        if ignore_pattern is None:
            print('Clean repository required '
                  '(commit, discard or stash changes).')
            sys.exit()
        else:
            changedFiles = [item.a_path for item in repo.index.diff(None)
                            if ignore_pattern not in item.a_path]
            if changedFiles:
                print('Clean repository required '
                      '(commit, discard or stash changes).')
                sys.exit()
    return True


def get_package_details():
    details = '\n - review_template:'.ljust(33, ' ') + 'version ' + \
        version('review_template')
    return details


def get_commit_report(script_name=None, saved_args=None):
    report = '\n\nReport\n\n'

    if script_name is not None:
        report = report + f'Command\n {script_name}\n'
    if saved_args is not None:
        repo = None
        for k, v in saved_args.items():
            if isinstance(v, str) or isinstance(v, bool) or isinstance(v, int):
                report = report + f'   --{k}={v}\n'
            if isinstance(v, git.repo.base.Repo):
                repo = v.head.commit.hexsha
            # TODO: should we do anything with the bib_db?
        if repo:
            # Note: this allows users to see whether the commit was changed!
            report = report + f' On git repo with version {repo}.\n'
        report = report + '\n'

    report = report + 'Software'
    report = report + get_package_details()

    from importlib.metadata import version
    version('pipeline_validation_hooks')
    report = report + '\n - pre-commit hooks:'.ljust(33, ' ') + 'version ' + \
        version('pipeline_validation_hooks')

    if 'dirty' in report:
        report = \
            report + '\n  ⚠ created with a modified version (not reproducible)'

    # Note: write-tree because commits can be amended
    # check tree:
    #   git write-tree
    #   git log --pretty=raw
    # To validate: check whether tree is identical with commit-tree:
    #   git log --pretty=raw -1
    g = git.Repo('').git
    tree_hash = g.execute(['git', 'write-tree'])
    report = report + f'\n\nCertified properties (for tree {tree_hash})\n'
    report = report + '- Traceability of records: '.ljust(32, ' ') + 'YES\n'
    report = \
        report + '- Consistency (based on hooks): '.ljust(32, ' ') + 'YES\n'
    completeness_condition = status.get_completeness_condition()
    if completeness_condition:
        report = \
            report + '- Completeness of iteration: '.ljust(32, ' ') + 'YES\n'
    else:
        report = \
            report + '- Completeness of iteration: '.ljust(32, ' ') + 'NO\n'

    # url = g.execut['git', 'config', '--get remote.origin.url']

    # append status
    f = io.StringIO()
    with redirect_stdout(f):
        status.review_status()
    # Remove colors for commit message
    status_page = f.getvalue().replace('\033[91m', '').replace('\033[92m', '')\
        .replace('\033[93m', '').replace('\033[94m', '').replace('\033[0m', '')
    report = report + status_page

    return report


def get_version_flag():
    flag = ''
    if 'dirty' in get_package_details():
        flag = ' ⚠️'
    return flag


def update_status_yaml():

    status_freq = status.get_status_freq()

    with open('status.yaml', 'w') as f:
        yaml.dump(status_freq, f, allow_unicode=True)

    repo = git.Repo()
    repo.index.add(['status.yaml'])

    return


def reset_log():
    with open('report.log', 'r+') as f:
        f.truncate(0)
    return


def create_commit(repo, msg, saved_args, manual_author=False):

    if repo.is_dirty():

        update_status_yaml()
        repo.index.add(['status.yaml'])

        hook_skipping = 'false'
        if not repo_setup.config['DEBUG_MODE']:
            hook_skipping = 'true'

        processing_report = ''
        if os.path.exists('report.log'):
            with open('report.log') as f:
                line = f.readline()
                debug_part = False
                while line:
                    if '[DEBUG]' in line or debug_part:
                        debug_part = True
                        if any(x in line for x in
                                ['[INFO]', '[ERROR]',
                                 '[WARNING]', '[CRITICAL']):
                            debug_part = False
                    if not debug_part:
                        processing_report = processing_report + line
                    line = f.readline()

            processing_report = \
                '\nProcessing report\n\n' + ''.join(processing_report)

        script = str(os.path.basename(inspect.stack()[1][1]))
        if manual_author:
            git_author = git.Actor(repo_setup.config['GIT_ACTOR'],
                                   repo_setup.config['EMAIL'])
        else:
            git_author = git.Actor(f'script:{script}', '')

        repo.index.commit(
            msg + get_version_flag() +
            get_commit_report(f'{script}',
                              saved_args) +
            processing_report,
            author=git_author,
            committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                                repo_setup.config['EMAIL']),
            skip_hooks=hook_skipping
        )
        logging.info('Created commit')
        print()
        reset_log()
        return True
    else:
        return False


def build_docker_images():

    client = docker.from_env()

    repo_tags = [x.attrs.get('RepoTags', '') for x in client.images.list()]
    repo_tags = [item[:item.find(':')]
                 for sublist in repo_tags for item in sublist]

    if 'bibutils' not in repo_tags:
        print('Building bibutils Docker image...')
        filedata = pkgutil.get_data(__name__, '../docker/bibutils/Dockerfile')
        fileobj = io.BytesIO(filedata)
        client.images.build(fileobj=fileobj, tag='bibutils:latest')
    if 'lfoppiano/grobid' not in repo_tags:
        print('Pulling grobid Docker image...')
        client.images.pull('lfoppiano/grobid:0.7.0')
    if 'pandoc/ubuntu-latex' not in repo_tags:
        print('Pulling v image...')
        client.images.pull('pandoc/ubuntu-latex:2.14')

    # jbarlow83/ocrmypdf

    return
