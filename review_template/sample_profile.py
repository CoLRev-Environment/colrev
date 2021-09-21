#! /usr/bin/env python
import os

import numpy as np
import pandas as pd
import yaml

from review_template import entry_hash_function
from review_template import utils

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']


def main():
    print('')
    print('')
    print('Sample profile')
    print('')

    bib_database = utils.load_references_bib(
        modification_check=False,
        initialize=False,
    )

    if not os.path.exists('output'):
        os.mkdir('output')

    references = pd.DataFrame.from_dict(bib_database.entries)
    references.rename(columns={'ID': 'citation_key'}, inplace=True)

    references['outlet'] = np.where(~references['journal'].isnull(),
                                    references['journal'],
                                    references['booktitle'])

    references = references[['citation_key',
                             'author',
                             'title',
                             'journal',
                             'booktitle',
                             'outlet',
                             'year',
                             'volume',
                             'number',
                             'pages',
                             'doi',
                             ]]

    screen = pd.read_csv(SCREEN, dtype=str)
    data = pd.read_csv(DATA, dtype=str)

    observations = \
        references[references['citation_key'].isin(
            screen[screen['inclusion_2'] == 'yes']['citation_key'].tolist()
        )]

    print(observations[observations['outlet'].isnull()]['citation_key'])

    observations = pd.merge(observations, data, how='left', on='citation_key')

    observations.to_csv('output/sample.csv', index=False)
    # print(observations.crosstab)
    tabulated = pd.pivot_table(observations[['outlet', 'year']],
                               index=['outlet'],
                               columns=['year'],
                               aggfunc=len,
                               fill_value=0,
                               margins=True)
    tabulated.to_csv('output/journals_years.csv')


if __name__ == '__main__':
    main()
