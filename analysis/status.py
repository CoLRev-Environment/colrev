#! /usr/bin/env python
import os

import entry_hash_function
import pandas as pd
import utils
import yaml

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA = entry_hash_function.paths[HASH_ID_FUNCTION]['DATA']
SEARCH_DETAILS = entry_hash_function.paths[HASH_ID_FUNCTION]['SEARCH_DETAILS']

nr_duplicates_hash_ids = 0
nr_entries_added = 0
nr_current_entries = 0


def validate_files():
    print('todo: implement validation')
    return


if __name__ == '__main__':

    print('')
    print('')

    print('Status')
    validate_files()
    print('')

    if not os.path.exists(MAIN_REFERENCES):
        print(' ┌ Search')
        print(' |  - Not yet initiated')
    else:
        # Search
        bib_database = utils.load_references_bib(
            modification_check=False,
            initialize=False,
        )

        search_details = pd.read_csv(
            SEARCH_DETAILS, dtype=str,
        )
        search_details['number_records'] = \
            search_details['number_records'].astype(int)

        print(' ┌ Search')
        print(
            ' |  - total retrieved: ' +
            str(search_details['number_records'].sum()).rjust(7, ' '),
        )
        print(' |  - merged: ' + str(len(bib_database.entries)).rjust(16, ' '))
        print(' |')

        # Screen
        if not os.path.exists(SCREEN):
            print(' ┌ Screen')
            print(' |  - Not yet initiated')
        else:

            screen = pd.read_csv(SCREEN, dtype=str)
            print(' ├ Screen 1')
            print(' |  - total: ' + str(screen.shape[0]).rjust(17, ' '))
            print(
                ' |  - excluded: ' +
                str(screen[screen['inclusion_1'] == 'no'].shape[0])
                .rjust(14, ' '),
            )
            print(
                ' |  - included: ' +
                str(screen[screen['inclusion_1'] == 'yes'].shape[0])
                .rjust(14, ' '),
            )
            if 0 != screen[screen['inclusion_1'] == 'TODO'].shape[0]:
                print(
                    ' |  - TODO: ' + str(
                        screen.drop(
                            screen[screen['inclusion_1'] != 'TODO'].index,
                        ).shape[0],
                    ).rjust(18, ' '),
                )
            print(' |')

            screen.drop(
                screen[
                    screen['inclusion_1']
                    == 'no'
                ].index, inplace=True,
            )
            print(' ├ Screen 2')
            print(' |  - total: ' + str(screen.shape[0]).rjust(17, ' '))
            print(
                ' |  - excluded: ' +
                str(screen[screen['inclusion_2'] == 'no'].shape[0])
                .rjust(14, ' '),
            )
            print(
                ' |  - included: ' +
                str(screen[screen['inclusion_2'] == 'yes'].shape[0])
                .rjust(14, ' '),
            )
            if 0 != screen[screen['inclusion_2'] == 'TODO'].shape[0]:
                print(
                    ' |  - TODO: ' +
                    str(screen[screen['inclusion_2'] == 'TODO'].shape[0])
                    .rjust(18, ' '),
                )
            print(' |')

            # Data
            if not os.path.exists(DATA):
                print(' ├ Data')
                print(' |  - Not yet initiated')
            else:
                data = pd.read_csv(DATA, dtype=str)
                print(' ├ Data extraction')
                print(' |  - total: ' + str(data.shape[0]).rjust(17, ' '))
                if 0 != screen[screen['inclusion_2'] == 'yes'].shape[0] - \
                        data.shape[0]:
                    print(
                        ' |  - IMPORT FROM SCREEN: ' +
                        str(screen[screen['inclusion_2'] == 'yes'].shape[0] -
                            data.shape[0])
                        .rjust(4, ' '),
                    )

                print('')
                print('')
