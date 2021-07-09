#! /usr/bin/env python
import os
import shutil
import sys

import entry_hash_function
import git

SEARCH_DETAILS = entry_hash_function.paths['SEARCH_DETAILS']


if __name__ == '__main__':

    print('')
    print('')

    print('Initialize review repository')

    if not len(os.listdir()) == 0:
        if not 'y' == input('initialize in non-empty directory (y/n)?'):
            sys.exit(0)
    project_title = input('Project title: ')

    r = git.Repo.init()
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
    shutil.copyfile('../template/.gitignore', '.gitignore')

    os.system('pre-commit install')

    r.index.add([
        'readme.md',
        SEARCH_DETAILS,
        '.pre-commit-config.yaml',
        '.gitattributes',
        '.gitignore',
    ])

    committer_name = \
        input('Please provide your name (for the git committer name)')
    committer_email = \
        input('Please provide your e-mail (for the git committer e-mail)')

    input('also save to config.py')

    r.index.commit(
        'Initial commit',
        author=git.Actor('script:initialize.py', ''),
        committer=git.Actor(committer_name, committer_email),
    )

    # TODO: connection to remote repo
