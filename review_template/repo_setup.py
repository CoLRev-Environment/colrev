#!/usr/bin/env python3
import ast
import configparser
import logging
import multiprocessing as mp
import os

from review_template import init

# Note: including the paths here is useful to ensure that a passing pre-commit
# means that the files are in the specified places. This is particularly
# important for gathering crowd-sourced data across review repositories.

local_config = configparser.ConfigParser()
confs = []
if os.path.exists('shared_config.ini'):
    confs.append('shared_config.ini')
if os.path.exists('private_config.ini'):
    confs.append('private_config.ini')
local_config.read(confs)


def email_fallback() -> str:
    name, email = init.get_name_mail_from_global_git_config()
    return email


def actor_fallback() -> str:
    name, email = init.get_name_mail_from_global_git_config()
    return name


csl_fallback = 'https://raw.githubusercontent.com/citation-style-language/' + \
    'styles/6152ccea8b7d7a472910d36524d1bf3557a83bfc/mis-quarterly.csl'

word_template_url_fallback = \
    'https://raw.githubusercontent.com/geritwagner/templates/main/MISQ.docx'

config = dict(
    REPO_SETUP_VERSION=local_config.get('general',
                                        'REPO_SETUP_VERSION',
                                        fallback='v_0.1'),
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
    EMAIL=local_config.get('general', 'EMAIL', fallback=email_fallback()),
    GIT_ACTOR=local_config.get('general', 'GIT_ACTOR',
                               fallback=actor_fallback()),
    DEBUG_MODE=local_config.getboolean('general', 'DEBUG_MODE',
                                       fallback=False),
    DATA_FORMAT=local_config.get(
        'general', 'DATA_FORMAT', fallback='["MANUSCRIPT"]'),
    PDF_HANDLING=local_config.get(
        'general', 'PDF_HANDLING', fallback='EXT'),
    ID_PATTERN=local_config.get(
        'general', 'ID_PATTERN', fallback='THREE_AUTHORS'),
    CSL=local_config.get(
        'general', 'CSL', fallback=csl_fallback),
    WORD_TEMPLATE_URL=local_config.get(
        'general', 'WORD_TEMPLATE_URL', fallback=word_template_url_fallback),
)

if config['DEBUG_MODE']:
    logging_level = logging.DEBUG
else:
    logging_level = logging.INFO

logging.basicConfig(
    level=logging_level,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('report.log', mode='a'),
        logging.StreamHandler()
    ]
)

try:
    config['DATA_FORMAT'] = ast.literal_eval(config['DATA_FORMAT'])
except ValueError:
    logging.error(f'Could not load DATA_FORMAT ({config["DATA_FORMAT"] }), '
                  'using fallback')
    config['DATA_FORMAT'] = ['MANUSCRIPT']
    pass

# handle = "review_template"
# rt_logger = logging.getLogger(handle)


#############################################################################

paths_v1 = dict(
    MAIN_REFERENCES='references.bib',
    DATA='data.yaml',
    PDF_DIRECTORY='pdfs/',
    SEARCH_DETAILS='search_details.yaml',
    MANUSCRIPT='paper.md'
)

#############################################################################


# paths = \
#     {'v_0.1': paths_v_0_1}

if config['REPO_SETUP_VERSION'] == 'v_0.1':
    paths = paths_v1

logging.debug(f'config: {config}')
logging.debug(f'paths: {paths}')
