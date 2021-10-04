#! /usr/bin/env python
import os
import pkgutil
import sys

import git
import yaml


def retrieve_template_file(template_file, target):

    filedata = pkgutil.get_data(__name__, template_file)
    filedata = filedata.decode('utf-8')
    with open(target, 'w') as file:
        file.write(filedata)

    return


def inplace_change(filename, old_string, new_string):
    # Safely read the input filename using 'with'
    with open(filename) as f:
        s = f.read()
        if old_string not in s:
            print('"{old_string}" not found in {filename}.'.format(**locals()))
            return

    # Safely write the changed content, if found in the file
    with open(filename, 'w') as f:
        s = s.replace(old_string, new_string)
        f.write(s)
    return


def get_value(msg, options):

    valid_response = False
    user_input = ''
    while not valid_response:
        print(' ' + msg + ' (' + '|'.join(options) + ')', file=sys.stderr)
        user_input = input()
        if user_input in options:
            valid_response = True

    return user_input


def initialize_repo():

    r = git.Repo.init()

    print('')
    print('')

    print('Initialize review repository')
    project_title = input('Project title: ')

    committer_name = \
        input('Please provide your name (for the git committer name)')
    committer_email = \
        input('Please provide your e-mail (for the git committer e-mail)')

    print('\n\nParameters for the review project\n Details avilable at: '
          'TODO/docs')

    SCREEN_TYPE = get_value('Select screen type',
                            ['NONE', 'PRE_SCREEN', 'INCLUSION_SCREEN'])
    DATA_FORMAT = get_value('Select data structure',
                            ['NONE', 'CSV_TABLE', 'MD_SHEET',
                             'MD_SHEETS', 'MA_VARIABLES_CSV'])
    SHARE_STAT_REQ = \
        get_value('Select share status requirement',
                  ['NONE', 'PROCESSED', 'SCREENED', 'COMPLETED'])
    PDF_HANDLING = get_value('Select pdf handling', ['EXT', 'GIT'])
    print()

    os.mkdir('search')

    retrieve_template_file(
        '../template/readme.md',
        'readme.md',
    )
    retrieve_template_file(
        '../template/.pre-commit-config.yaml',
        '.pre-commit-config.yaml',
    )
    retrieve_template_file('../template/.gitattributes',
                           '.gitattributes')
    retrieve_template_file('../template/private_config.yaml',
                           'private_config.yaml')
    retrieve_template_file('../template/shared_config.yaml',
                           'shared_config.yaml')
    retrieve_template_file('../template/shared_config.yaml',
                           'shared_config.yaml')

    with open('shared_config.yaml') as shared_config_yaml:
        shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
    HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

    from review_template import entry_hash_function
    SEARCH_DETAILS = \
        entry_hash_function.paths[HASH_ID_FUNCTION]['SEARCH_DETAILS']

    f = open(SEARCH_DETAILS, 'w')
    header = '"filename","number_records","iteration","date_start",' + \
        '"date_completion","source_url",' + \
        '"search_parameters","responsible","comment"'
    f.write(header)
    f.close()

    inplace_change('private_config.yaml', 'EMAIL', committer_email)
    inplace_change('private_config.yaml', 'GIT_ACTOR', committer_name)
    inplace_change('readme.md', '{{project_title}}', project_title)
    inplace_change('shared_config.yaml', 'SCREEN_TYPE', SCREEN_TYPE)
    inplace_change('shared_config.yaml', 'DATA_FORMAT', DATA_FORMAT)
    inplace_change('shared_config.yaml', 'SHARE_STAT_REQ', SHARE_STAT_REQ)
    inplace_change('shared_config.yaml', 'PDF_HANDLING', PDF_HANDLING)

    # Note: need to write the .gitignore because file would otherwise be
    # ignored in the template directory.
    f = open('.gitignore', 'w')
    f.write('*.bib.sav\nprivate_config.yaml\n.local_pdf_indices' +
            '\n.index-*\nmissing_pdf_files.csv')
    f.close()

    os.system('pre-commit install')

    from review_template import utils

    r.index.add([
        'readme.md',
        SEARCH_DETAILS,
        '.pre-commit-config.yaml',
        '.gitattributes',
        '.gitignore',
        'shared_config.yaml',
    ])

    flag, flag_details = utils.get_version_flags()

    r.index.commit(
        'Initial commit' + flag + flag_details,
        author=git.Actor('script:initialize.py', ''),
        committer=git.Actor(committer_name, committer_email),
    )

    # TODO: connection to remote repo

    return r


def get_repo():

    try:
        # Alternatively: ask for remote url of git repo to clone?
        r = git.Repo()
        # TODO: further checks?
        return r
    except git.exc.InvalidGitRepositoryError:
        print('No git repository found.')
        pass

    r = initialize_repo()

    return r


if __name__ == '__main__':

    initialize_repo()
