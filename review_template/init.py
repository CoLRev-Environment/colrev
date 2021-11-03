#! /usr/bin/env python
import configparser
import os
import pkgutil
import sys

import git
import requests


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


def get_name_mail_from_global_git_config():
    ggit_conf_path = os.path.normpath(os.path.expanduser('~/.gitconfig'))
    if os.path.exists(ggit_conf_path):
        glob_git_conf = git.GitConfigParser([ggit_conf_path], read_only=True)
        committer_name = glob_git_conf.get('user', 'name')
        committer_email = glob_git_conf.get('user', 'email')
        # TODO: test whether user and email are set in the global config
    else:
        committer_name = input('Please provide your name')
        committer_email = input('Please provide your e-mail')
    return committer_name, committer_email


def init_new_repo():

    print('\n\nInitialize review repository')
    project_title = input('Project title: ')

    committer_name, committer_email = get_name_mail_from_global_git_config()

    print('\n\nParameters for the review project\n Details avilable at: '
          'TODO/docs')

    # # TODO: allow multiple?
    # DATA_FORMAT = get_value('Select data structure',
    #                         ['NONE', 'TABLE', 'PAGE',
    #                          'SHEETs', 'MACODING'])
    SHARE_STAT_REQ = get_value('Select share status requirement',
                               ['NONE', 'PROCESSED', 'SCREENED', 'COMPLETED'])
    PDF_HANDLING = get_value('Select pdf handling', ['EXT', 'GIT'])
    print()

    repo = git.Repo.init()
    os.mkdir('search')

    retrieve_template_file('../template/readme.md', 'readme.md')
    retrieve_template_file(
        '../template/.pre-commit-config.yaml',
        '.pre-commit-config.yaml',
    )
    retrieve_template_file('../template/.gitattributes', '.gitattributes')

    inplace_change('readme.md', '{{project_title}}', project_title)

    private_config = configparser.ConfigParser()
    private_config.add_section('general')
    private_config['general']['EMAIL'] = committer_email
    private_config['general']['GIT_ACTOR'] = committer_name
    private_config['general']['CPUS'] = '4'
    private_config['general']['DEBUG_MODE'] = 'no'
    with open('private_config.ini', 'w') as configfile:
        private_config.write(configfile)

    # REPO_SETUP_VERSION = repo_setup.paths.keys()[-1]
    REPO_SETUP_VERSION = 'v_0.1'
    shared_config = configparser.ConfigParser()
    shared_config.add_section('general')
    shared_config['general']['REPO_SETUP_VERSION'] = REPO_SETUP_VERSION
    shared_config['general']['SHARE_STAT_REQ'] = SHARE_STAT_REQ
    shared_config['general']['PDF_HANDLING'] = PDF_HANDLING
    with open('shared_config.ini', 'w') as configfile:
        shared_config.write(configfile)

    # Note: need to write the .gitignore because file would otherwise be
    # ignored in the template directory.
    f = open('.gitignore', 'w')
    f.write('*.bib.sav\nprivate_config.ini\n.local_pdf_indices' +
            '\n.index-*\nmissing_pdf_files.csv')
    f.close()

    from review_template import repo_setup
    SEARCH_DETAILS = repo_setup.paths['SEARCH_DETAILS']
    f = open(SEARCH_DETAILS, 'w')
    header = '"filename","number_records","iteration","date_start",' + \
        '"date_completion","source_url",' + \
        '"search_parameters","responsible","comment"'
    f.write(header)
    f.close()

    os.system('pre-commit install')
    os.system('pre-commit autoupdate')

    from review_template import utils

    repo.index.add([
        'readme.md',
        SEARCH_DETAILS,
        '.pre-commit-config.yaml',
        '.gitattributes',
        '.gitignore',
        'shared_config.ini',
    ])

    repo.index.commit(
        'Initial commit' + utils.get_version_flag(),
        author=git.Actor('script:init.py', ''),
        committer=git.Actor(committer_name, committer_email),
    )

    if 'y' == input('Connect to shared (remote) repository (y)?'):
        remote_url = input('URL:')
        try:
            requests.get(remote_url)
            origin = repo.create_remote('origin', remote_url)
            repo.heads.main.set_tracking_branch(origin.refs.main)
            origin.push()
        except requests.ConnectionError:
            print('URL of shared repository cannot be reached. Use '
                  'git remote add origin https://github.com/user/repo\n'
                  'git push origin main')
            pass

    # git remote add origin https://github.com/geritwagner/octo-fiesta.git
    # git branch -M main
    # git push -u origin main

    return repo


def clone_shared_repo():
    print('Connecting to a shared repository ...')
    print('To initiate a new project, cancel (ctrl+c) and use '
          'review_template init in an empty directory')

    remote_url = input('URL of shared repository:')
    try:
        requests.get(remote_url)
        repo_name = os.path.splitext(os.path.basename(remote_url))[0]
        print('Clone shared repository...')
        repo = git.Repo.clone_from(remote_url, repo_name)
        print(f'Use cd {repo_name}')
    except requests.ConnectionError:
        print('URL of shared repository cannot be reached. Use '
              'git remote add origin https://github.com/user/repo\n'
              'git push origin main')
        pass
    return repo


def initialize_repo():
    if 0 != len(os.listdir(os.getcwd())):
        repo = clone_shared_repo()
    else:
        if 'y' == input('Retrieve shared repository?'):
            repo = clone_shared_repo()
        else:
            repo = init_new_repo()
    return repo


def get_repo():
    try:
        repo = git.Repo()
        # TODO: further checks?
        return repo
    except git.exc.InvalidGitRepositoryError:
        print('No git repository found.')
        pass

    repo = initialize_repo()
    return repo


if __name__ == '__main__':

    initialize_repo()
