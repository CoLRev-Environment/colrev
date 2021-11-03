#! /usr/bin/env python
import os

import click
import requests

import docker
from review_template import repo_setup
from review_template import utils


def main():

    utils.build_docker_images()

    uid = os.stat(repo_setup.paths['MAIN_REFERENCES']).st_uid
    gid = os.stat(repo_setup.paths['MAIN_REFERENCES']).st_gid

    CSL_FILE = repo_setup.config['CSL']
    WORD_TEMPLATE_URL = repo_setup.config['WORD_TEMPLATE_URL']

    # TODO: maybe update?
    if not os.path.exists(os.path.basename(WORD_TEMPLATE_URL)):
        # try:
        url = WORD_TEMPLATE_URL
        r = requests.get(url)
        with open(os.path.basename(WORD_TEMPLATE_URL), 'wb') as output:
            output.write(r.content)
        # except:
        #     pass
    if 'github.com' not in CSL_FILE and not os.path.exists(CSL_FILE):
        CSL_FILE = 'https://raw.githubusercontent.com/citation-style-' + \
            'language/styles/6152ccea8b7d7a472910d36524d1bf3557a83bfc/' + \
            f'{CSL_FILE}'

    script = 'paper.md --citeproc --bibliography references.bib ' + \
        f'--csl {CSL_FILE} ' + \
        f'--reference-doc {os.path.basename(WORD_TEMPLATE_URL)} ' + \
        '--output paper.docx'

    client = docker.from_env()
    try:
        client.containers.run(image='pandoc/ubuntu-latex:2.14',
                              command=script,
                              user=f'{uid}:{gid}',
                              volumes=[os.getcwd() + ':/data']
                              )
    except docker.errors.ImageNotFound:
        print('Docker image not found')
        return
        pass

    return


@click.command()
def paper():
    main()
    return 0


if __name__ == '__main__':
    main()
