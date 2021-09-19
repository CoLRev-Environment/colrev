#! /usr/bin/env python
import entry_hash_function
import utils
import yaml

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


def reformat_bib():
    bib_database = utils.load_references_bib(
        modification_check=False, initialize=False,
    )
    utils.save_bib_file(bib_database, MAIN_REFERENCES)
    return


if __name__ == '__main__':

    print('')
    print('')

    print('Reformat bibliography')

    reformat_bib()
