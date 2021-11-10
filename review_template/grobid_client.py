#! /usr/bin/env python
import logging
import os
import subprocess
import sys
import time

import requests

GROBID_URL = 'http://localhost:8070'
grobid_image = 'grobid/grobid:0.7.1-SNAPSHOT'


def get_grobid_url():
    return GROBID_URL


def check_grobid_availability():
    i = 0
    while True:
        i += 1
        time.sleep(1)
        try:
            r = requests.get(GROBID_URL + '/api/isalive')
            if r.text == 'true':
                i = -1
        except requests.exceptions.ConnectionError:
            pass
        if i == -1:
            break
        if i > 20:
            sys.exit(0)
    return


def start_grobid():
    logging.info(f'Running docker container created from {grobid_image}')
    try:
        r = requests.get(GROBID_URL + '/api/isalive')
        if r.text == 'true':
            logging.debug('Docker running')
            return True
    except requests.exceptions.ConnectionError:
        logging.info('Starting grobid service...')
        subprocess.Popen(['docker run -t --rm -m "4g" -p 8070:8070 ' +
                          f'-p 8071:8071 {grobid_image}'],
                         shell=True,
                         stdin=None,
                         stdout=open(os.devnull, 'wb'),
                         stderr=None,
                         close_fds=True,
                         )
        pass

    i = 0
    while True:
        i += 1
        time.sleep(1)
        try:
            r = requests.get(GROBID_URL + '/api/isalive')
            if r.text == 'true':
                logging.info('Grobid service alive.')
                return True
        except requests.exceptions.ConnectionError:
            pass
        if i > 30:
            break
    return False
