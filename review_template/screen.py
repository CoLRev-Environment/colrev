#! /usr/bin/env python
import configparser
import csv
import os

import git
import pandas as pd

from review_template import entry_hash_function
from review_template import utils

config = configparser.ConfigParser()
config.read(['shared_config.ini', 'private_config.ini'])
HASH_ID_FUNCTION = config['general']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def screen_commit():

    r = git.Repo('')
    r.index.add([SCREEN])

    hook_skipping = 'false'
    if not config.getboolean('general', 'DEBUG_MODE'):
        hook_skipping = 'true'

    flag, flag_details = utils.get_version_flags()

    r.index.commit(
        'Screening (manual)' + flag + flag_details +
        '\n - Using screen.py' +
        '\n - ' + utils.get_package_details(),
        author=git.Actor(config['general']['GIT_ACTOR'],
                         config['general']['EMAIL']),
        committer=git.Actor(config['general']['GIT_ACTOR'],
                            config['general']['EMAIL']),
        skip_hooks=hook_skipping
    )

    return


def main():
    print('')
    print('')

    print('Run screen 2')

    assert os.path.exists(SCREEN)
    utils.git_modification_check(SCREEN)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    screen = pd.read_csv(SCREEN, dtype=str)

    print('To stop screening, press ctrl-c')

    references = pd.DataFrame.from_dict(bib_database.entries)
    references.rename(columns={'ID': 'citation_key'}, inplace=True)
    req_cols = ['citation_key',
                'author',
                'title',
                'year',
                'journal',
                'volume',
                'number',
                'pages',
                'file',
                'doi',
                ]

    for req_col in req_cols:
        if req_col not in references:
            references[req_col] = ''
    references = references[req_cols]
    references.fillna('', inplace=True)

    exclusion_criteria_available = 0 < len(
        [col for col in screen.columns if col.startswith('ec_')],
    )

    try:
        for i, row in screen.iterrows():
            try:
                if 'TODO' == row['inclusion_2']:
                    reference = references.loc[
                        references['citation_key'] == row['citation_key']
                    ].iloc[0].to_dict()
                    print()
                    print()
                    print()
                    print(
                        f'{reference["title"]}  -  ',
                        f'{reference["author"]}  ',
                        f'{reference["journal"]}  ',
                        f'{reference["year"]}  (',
                        f'{reference["volume"]}:',
                        f'{reference["number"]}) ',
                        f'{reference["file"]} *',
                        f'{reference["citation_key"]}*',
                    )
                    if exclusion_criteria_available:
                        for column in [
                            col for col in screen.columns
                            if col.startswith('ec_')
                        ]:
                            decision = 'TODO'

                            while decision not in ['y', 'n']:
                                decision = \
                                    input('Violates ' + column + ' (y/n)?')
                            decision = \
                                decision.replace('y', 'yes')\
                                        .replace('n', 'no')
                            screen.at[i, column] = decision

                        if all([
                            screen.at[i, col] == 'no' for col in screen.columns
                            if col.startswith('ec_')
                        ]):
                            screen.at[i, 'inclusion_2'] = 'yes'
                            print('Inclusion recorded')
                        else:
                            screen.at[i, 'inclusion_2'] = 'no'
                            print('Exclusion recorded')
                    else:
                        decision = 'TODO'
                        while decision not in ['y', 'n']:
                            decision = input('Include (y/n)?')
                        decision = decision.replace('y', 'yes')\
                                           .replace('n', 'no')
                        screen.at[i, 'inclusion_2'] = 'yes'

                    screen.sort_values(by=['citation_key'], inplace=True)
                    screen.to_csv(
                        SCREEN, index=False,
                        quoting=csv.QUOTE_ALL, na_rep='NA',
                    )
            except IndexError:
                print('Index error/citation_key not found in ' +
                      f'{MAIN_REFERENCES}: {row["citation_key"]}')
                pass
    except KeyboardInterrupt:
        print()
        print()
        print('stopping screen 1')
        print()
        pass

    # If records remain for screening, ask whether to create a commit
    if 0 < screen[screen['inclusion_2'] == 'TODO'].shape[0]:
        if 'y' == input('Create commit (y/n)?'):
            screen_commit()
    else:
        screen_commit()

    return

    return


if __name__ == '__main__':
    main()
