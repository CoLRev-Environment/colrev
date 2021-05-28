#! /usr/bin/env python
import os
import shutil

import git

if __name__ == '__main__':

    print('')
    print('')

    print('Initialize review repository')

    if os.path.exists('data'):
        assert len(os.listdir('data')) == 0
    project_title = input('Project title: ')

    if not os.path.exists('data'):
        os.mkdir('data')
    r = git.Repo.init('data')
    os.chdir('data')
    os.mkdir('search')

    f = open('search/search_details.csv', 'w')
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
    shutil.copyfile('../docker-compose.yaml', 'docker-compose.yaml')
    shutil.copyfile('../template/.gitattributes', '.gitattributes')
    shutil.copyfile('../template/.gitignore', '.gitignore')

    os.system('pre-commit install')

    r.index.add([
        'readme.md',
        'search/search_details.csv',
        '.pre-commit-config.yaml',
        '.gitattributes',
        '.gitignore',
    ])

    committer_name = \
        input('Please provide your name (for the git committer name)')
    committer_email = \
        input('Please provide your e-mail (for the git committer e-mail)')

    r.index.commit(
        'Initial commit',
        author=git.Actor('script:initialize.py', ''),
        committer=git.Actor(committer_name, committer_email),
    )

    # TODO: connection to remote repo
