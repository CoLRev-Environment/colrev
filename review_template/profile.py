#! /usr/bin/env python
import logging
import os

import pandas as pd

from review_template import status
from review_template import utils


class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def prep_references(bib_db):
    for record in bib_db.entries:
        record['outlet'] = record.get('journal', record.get('booktitle', 'NA'))

    references = pd.DataFrame.from_dict(bib_db.entries)

    required_cols = ['ID',
                     'ENTRYTYPE',
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
                     ]
    available_cols = references.columns.intersection(set(required_cols))
    cols = [x for x in required_cols if x in available_cols]
    references = references[cols]
    return references


def prep_observations(references, bib_db):

    included_papers = utils.get_included_IDs(bib_db)
    observations = references[references['ID'].isin(included_papers)]
    observations['year'] = observations['year'].astype(int)
    missing_outlet = \
        observations[observations['outlet'].isnull()]['ID'].tolist()
    if len(missing_outlet) > 0:
        print(f'No outlet: {missing_outlet}')
    return observations


def main():

    print('\n\nSample profile\n')

    if not status.get_completeness_condition():
        logging.warning(
            f'{colors.RED}Sample not completely processed!{colors.END}')

    bib_db = utils.load_main_refs(mod_check=False)

    if not os.path.exists('output'):
        os.mkdir('output')

    references = prep_references(bib_db)
    observations = prep_observations(references, bib_db)

    if observations.empty:
        logging.info('No sample/observations available')
        return

    # TODO: fill missing years
    logging.info('Generate output/sample.csv')
    observations.to_csv('output/sample.csv', index=False)

    tabulated = pd.pivot_table(observations[['outlet', 'year']],
                               index=['outlet'],
                               columns=['year'],
                               aggfunc=len,
                               fill_value=0,
                               margins=True)
    logging.info('Generate profile output/journals_years.csv')
    tabulated.to_csv('output/journals_years.csv')

    tabulated = pd.pivot_table(observations[['ENTRYTYPE', 'year']],
                               index=['ENTRYTYPE'],
                               columns=['year'],
                               aggfunc=len,
                               fill_value=0,
                               margins=True)
    logging.info('Generate output/ENTRYTYPES.csv')
    tabulated.to_csv('output/ENTRYTYPES.csv')

    return


if __name__ == '__main__':
    main()
