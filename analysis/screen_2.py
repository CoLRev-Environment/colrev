#! /usr/bin/env python
import csv
import os

import pandas as pd
import utils


def run_screen_2(screen_filename, bib_database):

    screen = pd.read_csv(screen_filename, dtype=str)

    print('To stop screening, press ctrl-c')

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
                        ') ',
                        reference['file'],
                        ' *',
                        reference['citation_key'],
                        '*',
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
                        screen_filename, index=False,
                        quoting=csv.QUOTE_ALL, na_rep='NA',
                    )
            except IndexError:
                print('Index error/citation_key not found in references.bib: ',
                      row['citation_key'])
                pass
    except KeyboardInterrupt:
        print()
        print()
        print('stopping screen 1')
        print()
        pass

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Run screen 2')

    screen_file = 'data/screen.csv'
    assert os.path.exists(screen_file)
    utils.git_modification_check('screen.csv')

    bib_database = utils.load_references_bib(
        modification_check=True, initialize=False,
    )

    run_screen_2(screen_file, bib_database)
