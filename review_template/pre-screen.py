#! /usr/bin/env python
import csv
import os
import sys

import pandas as pd
import yaml

from review_template import entry_hash_function
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def main():
    print('')
    print('')

    print('Run screen 1')

    # TODO: check prior commits whether duplicates have been removed
    if 'y' != input(
        'Note: start screening only after removing duplicates ' +
        'from ' + MAIN_REFERENCES + '! Proceed with the screen (y/n)?'
    ):
        sys.exit()

    utils.git_modification_check(SCREEN)

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    assert os.path.exists(SCREEN)

    screen = pd.read_csv(SCREEN, dtype=str)
    # Note: this seems to be necessary to ensure that
    # pandas saves quotes around the last column
    screen.comment = screen.comment.fillna('-')

    references = pd.DataFrame.from_dict(bib_database.entries)
    references.rename(columns={'ID': 'citation_key'}, inplace=True)
    references = references[[
        'citation_key',
        'author',
        'title',
        'year',
        'journal',
        'volume',
        'number',
        'pages',
        'file',
        'doi',
    ]]
    references.fillna('', inplace=True)

    # TODO: check if citation_keys in MAIN_REFERENCES and SCREEN are identical?

    print('To stop screening, press ctrl-c')
    try:
        for i, row in screen.iterrows():
            if 'TODO' == row['inclusion_1']:
                inclusion_decision = 'TODO'
                reference = references.loc[
                    references['citation_key'] == row['citation_key']
                ].iloc[0].to_dict()
                while inclusion_decision not in ['y', 'n']:
                    print()
                    print()
                    print(
                        reference['title'],
                        '  -  ',
                        reference['author'],
                        '  ',
                        reference['journal'],
                        '  ',
                        str(reference['year']),
                        '  (',
                        str(reference['volume']),
                        ':',
                        str(reference['number']),
                        ') *',
                        reference['citation_key'],
                        '*',
                    )
                    print()
                    inclusion_decision = input('include (y) or exclude (n)?')
                inclusion_decision = inclusion_decision\
                    .replace('y', 'yes')\
                    .replace('n', 'no')
                screen.at[i, 'inclusion_1'] = inclusion_decision
                if 'no' == inclusion_decision:
                    screen.at[i, 'inclusion_2'] = 'NA'
                    for column in screen.columns:
                        if 'ec_' in column:
                            screen.at[i, column] = 'NA'

                screen.sort_values(by=['citation_key'], inplace=True)
                screen.to_csv(
                    SCREEN, index=False,
                    quoting=csv.QUOTE_ALL, na_rep='NA',
                )
    except KeyboardInterrupt:
        print()
        print()
        print('stopping screen 1')
        print()
        pass

    return


if __name__ == '__main__':
    main()
