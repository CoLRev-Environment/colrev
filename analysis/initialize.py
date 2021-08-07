#! /usr/bin/env python
import os
import shutil

import entry_hash_function
import git
import yaml

with open('../template/shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SEARCH_DETAILS = entry_hash_function.paths[HASH_ID_FUNCTION]['SEARCH_DETAILS']


def initialize_repo():

    try:
        # Alternatively: ask for remote url of git repo to clone?
        r = git.Repo()
        # TODO: further checks?
        return r
    except git.exc.InvalidGitRepositoryError:
        pass

    r = git.Repo.init()

    print('')
    print('')

    print('Initialize review repository')
    project_title = input('Project title: ')

    # TODO: check: initialize in non-empty directory (y/n)?

    os.mkdir('search')

    f = open(SEARCH_DETAILS, 'w')
    header = '"filename","number_records","iteration","date_start",' + \
        '"date_completion","source_url",' + \
        '"search_parameters","responsible","comment"'
    f.write(header)
    f.close()

    with open('../template/readme.md') as file:
        filedata = file.read()
    filedata = filedata.replace('{{project_title}}', project_title)
    with open('readme.md', 'w') as file:
        file.write(filedata)

    shutil.copyfile(
        '../template/.pre-commit-config.yaml',
        '.pre-commit-config.yaml',
    )
    shutil.copyfile('../docker-compose.yml', 'docker-compose.yml')
    shutil.copyfile('../template/.gitattributes', '.gitattributes')
    shutil.copyfile('../template/private_config.yaml', 'private_config.yaml')
    shutil.copyfile('../template/shared_config.yaml', 'shared_config.yaml')

    # Note: need to write the .gitignore because file would otherwise be
    # ignored in the template directory.
    f = open('.gitignore', 'w')
    f.write('*.bib.sav\nprivate_config.yaml')
    f.close()

    os.system('pre-commit install')

    r.index.add([
        'readme.md',
        SEARCH_DETAILS,
        '.pre-commit-config.yaml',
        '.gitattributes',
        '.gitignore',
        'shared_config.yaml',
    ])

    committer_name = \
        input('Please provide your name (for the git committer name)')
    committer_email = \
        input('Please provide your e-mail (for the git committer e-mail)')
    input('run "pre-commit autoupdate"')
    input('also save to config.py')

    r.index.commit(
        'Initial commit',
        author=git.Actor('script:initialize.py', ''),
        committer=git.Actor(committer_name, committer_email),
    )

    # TODO: connection to remote repo

    return r


if __name__ == '__main__':

    initialize_repo()
