#!/usr/bin/env python3
import configparser
import logging
import multiprocessing as mp
import os

# Note: including the paths here is useful to ensure that a passing pre-commit
# means that the files are in the specified places. This is particularly
# important for gathering crowd-sourced data across review repositories.

repo_version_fallback = 'v_0.1'

if os.path.exists('shared_config.ini') and \
        os.path.exists('private_config.ini'):
    local_config = configparser.ConfigParser()
    local_config.read(['shared_config.ini', 'private_config.ini'])

    config = dict(
        REPO_SETUP_VERSION=local_config.get('general',
                                            'REPO_SETUP_VERSION',
                                            fallback=repo_version_fallback),
        DELAY_AUTOMATED_PROCESSING=local_config.getboolean(
            'general', 'DELAY_AUTOMATED_PROCESSING', fallback=True),
        BATCH_SIZE=local_config.getint('general', 'BATCH_SIZE', fallback=500),
        SHARE_STAT_REQ=local_config.get(
            'general', 'SHARE_STAT_REQ', fallback='PROCESSED'),
        CPUS=local_config.getint('general', 'CPUS', fallback=mp.cpu_count()-1),
        MERGING_NON_DUP_THRESHOLD=local_config.getfloat(
            'general', 'MERGING_NON_DUP_THRESHOLD', fallback=0.7),
        MERGING_DUP_THRESHOLD=local_config.getfloat(
            'general', 'MERGING_DUP_THRESHOLD', fallback=0.95),
        EMAIL=local_config['general']['EMAIL'],
        GIT_ACTOR=local_config['general']['GIT_ACTOR'],
        DEBUG_MODE=local_config.get('general', 'DEBUG_MODE', fallback=False),
        DATA_FORMAT=local_config.get(
            'general', 'DATA_FORMAT', fallback='CSV_TABLE'),
        PDF_HANDLING=local_config.get(
            'general', 'PDF_HANDLING', fallback='EXT')
    )

else:
    config = dict(REPO_SETUP_VERSION=repo_version_fallback)

if os.path.exists('report.log'):
    os.remove('report.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('report.log'),
        logging.StreamHandler()
    ]
)

#############################################################################

paths_v1 = dict(
    MAIN_REFERENCES='references.bib',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search/search_details.csv'
)

#############################################################################


# paths = \
#     {'v_0.1': paths_v_0_1}

if config['REPO_SETUP_VERSION'] == 'v_0.1':
    paths = paths_v1
