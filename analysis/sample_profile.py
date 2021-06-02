#! /usr/bin/env python
import os

import numpy as np
import pandas as pd
import utils

if __name__ == '__main__':

    print('')
    print('')
    print('Sample profile')
    print('')

    bib_database = utils.load_references_bib(
        modification_check=False,
        initialize=False,
    )

    if not os.path.exists('data/output'):
        os.mkdir('data/output')

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

    screen = pd.read_csv('data/screen.csv', dtype=str)
    data = pd.read_csv('data/data.csv', dtype=str)

    observations = \
        references[references['citation_key'].isin(
            screen[screen['inclusion_2'] == 'yes']['citation_key'].tolist()
        )]

    print(observations[observations['outlet'].isnull()]['citation_key'])

    observations = pd.merge(observations, data, how='left', on='citation_key')

    observations.to_csv('data/output/sample.csv', index=False)
    # print(observations.crosstab)
    tabulated = pd.pivot_table(observations[['outlet', 'year']],
                               index=['outlet'],
                               columns=['year'],
                               aggfunc=len,
                               fill_value=0,
                               margins=True)
    tabulated.to_csv('data/output/journals_years.csv')
