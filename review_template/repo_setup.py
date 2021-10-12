#!/usr/bin/env python3
import configparser
import multiprocessing as mp

# Note: including the paths here is useful to ensure that a passing pre-commit
# means that the files are in the specified places. This is particularly
# important for gathering crowd-sourced data across review repositories.


local_config = configparser.ConfigParser()
local_config.read(['shared_config.ini', 'private_config.ini'])


config = dict(
    REPO_SETUP_VERSION=local_config['general']['REPO_SETUP_VERSION'],
    DELAY_AUTOMATED_PROCESSING=local_config.getboolean(
        'general', 'DELAY_AUTOMATED_PROCESSING'),
    BATCH_SIZE=local_config.getint('general', 'BATCH_SIZE', fallback=500),
    SHARE_STAT_REQ=local_config['general']['SHARE_STAT_REQ'],
    CPUS=local_config.getint('general', 'CPUS', fallback=mp.cpu_count()-1),
    MERGING_NON_DUP_THRESHOLD=local_config.getfloat(
        'general', 'MERGING_NON_DUP_THRESHOLD'),
    MERGING_DUP_THRESHOLD=local_config.getfloat(
        'general', 'MERGING_DUP_THRESHOLD'),
    EMAIL=local_config['general']['EMAIL'],
    GIT_ACTOR=local_config['general']['GIT_ACTOR'],
)

#############################################################################

# v_0.1

paths_v_0_1 = dict(
    MAIN_REFERENCES='references.bib',
    SCREEN='screen.csv',
    DATA='data.csv',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search/search_details.csv'
)

#############################################################################


# paths = \
#     {'v_0.1': paths_v_0_1}

if config['REPO_SETUP_VERSION'] == 'v_0.1':
    paths = paths_v_0_1
