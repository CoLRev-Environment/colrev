#! /usr/bin/env python
import os

import click

import docker
from review_template import repo_setup
from review_template import utils


def main():

    utils.build_docker_images()

    uid = os.stat(repo_setup.paths['MAIN_REFERENCES']).st_uid
    gid = os.stat(repo_setup.paths['MAIN_REFERENCES']).st_gid

    script = 'coding.md --citeproc --bibliography references.bib ' + \
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
