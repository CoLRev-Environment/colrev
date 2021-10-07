#! /usr/bin/env python
import configparser
import os
import pkgutil
import sys

import git


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
            print(f'"{old_string}" not found in {filename}.')
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
        print(f' {msg} (' + '|'.join(options) + ')', file=sys.stderr)
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

    glob_git_conf = git.GitConfigParser(
        [os.path.normpath(os.path.expanduser('~/.gitconfig'))], read_only=True)
    committer_name = glob_git_conf.get('user', 'name')
    # input('Please provide your name (for the git committer name)')
    committer_email = glob_git_conf.get('user', 'email')
    # input('Please provide your e-mail (for the git committer e-mail)')
    # TODO: test whether user and email are set in the global config

    print('\n\nParameters for the review project\n Details avilable at: '
          'TODO/docs')

    SCREEN_TYPE = get_value('Select screen type',
                            ['NONE', 'PRE_SCREEN', 'SCREEN'])
    DATA_FORMAT = get_value('Select data structure',
                            ['NONE', 'TABLE', 'PAGE',
                             'SHEETs', 'MACODING'])
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

    inplace_change('readme.md', '{{project_title}}', project_title)

    private_config = configparser.ConfigParser()
    private_config.add_section('general')
    private_config['general']['EMAIL'] = committer_email
    private_config['general']['GIT_ACTOR'] = committer_name
    private_config['general']['CPUS'] = '4'
    private_config['general']['DEBUG_MODE'] = 'no'
    with open('private_config.ini', 'w') as configfile:
        private_config.write(configfile)

    HASH_ID_FUNCTION = 'v_0.3'
    shared_config = configparser.ConfigParser()
    shared_config.add_section('general')
    shared_config['general']['HASH_ID_FUNCTION'] = HASH_ID_FUNCTION
    shared_config['general']['SCREEN_TYPE'] = SCREEN_TYPE
    shared_config['general']['DATA_FORMAT'] = DATA_FORMAT
    shared_config['general']['SHARE_STAT_REQ'] = SHARE_STAT_REQ
    shared_config['general']['PDF_HANDLING'] = PDF_HANDLING
    shared_config['general']['BATCH_SIZE'] = '2000'
    shared_config['general']['MERGING_DUP_THRESHOLD'] = '0.95'
    shared_config['general']['MERGING_NON_DUP_THRESHOLD'] = '0.7'
    shared_config['general']['DELAY_AUTOMATED_PROCESSING'] = 'yes'
    with open('shared_config.ini', 'w') as configfile:
        shared_config.write(configfile)

    # Note: need to write the .gitignore because file would otherwise be
    # ignored in the template directory.
    f = open('.gitignore', 'w')
    f.write('*.bib.sav\nprivate_config.ini\n.local_pdf_indices' +
            '\n.index-*\nmissing_pdf_files.csv')
    f.close()

    from review_template import entry_hash_function
    SEARCH_DETAILS = \
        entry_hash_function.paths[HASH_ID_FUNCTION]['SEARCH_DETAILS']
    f = open(SEARCH_DETAILS, 'w')
    header = '"filename","number_records","iteration","date_start",' + \
        '"date_completion","source_url",' + \
        '"search_parameters","responsible","comment"'
    f.write(header)
    f.close()

    os.system('pre-commit install')
    os.system('pre-commit autoupdate')

    from review_template import utils

    r.index.add([
        'readme.md',
        SEARCH_DETAILS,
        '.pre-commit-config.yaml',
        '.gitattributes',
        '.gitignore',
        'shared_config.ini',
    ])

    flag, flag_details = utils.get_version_flags()

    r.index.commit(
        'Initial commit' + flag + flag_details,
        author=git.Actor('script:init.py', ''),
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
