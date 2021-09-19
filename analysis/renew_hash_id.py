#! /usr/bin/env python
import sys

import bibtexparser
import entry_hash_function
import git
import utils
import yaml
from bibtexparser.customization import convert_to_unicode

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']


def prefix_old_hash_ids(bib_file):

    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        pairs = []
        for entry in individual_bib_database.entries:
            old_hash = \
                entry_hash_function.create_hash_function[PRIOR_VERSION](entry)
            old_hash_prefixed = 'old_hash_' + old_hash
            pairs.append([old_hash, old_hash_prefixed])

        # replace in MAIN_REFERENCES
        with open(MAIN_REFERENCES) as file:
            filedata = file.read()

        for old_hash, old_hash_prefixed in pairs:

            filedata = filedata.replace(old_hash, old_hash_prefixed)\
                .replace('old_hash_old_hash_', 'old_hash_')

        with open(MAIN_REFERENCES, 'w') as file:
            file.write(filedata)

    return


def replace_hash_ids(bib_file):
    with open(bib_file) as bibtex_file:
        individual_bib_database = bibtexparser.bparser.BibTexParser(
            customization=convert_to_unicode, common_strings=True,
        ).parse_file(bibtex_file, partial=True)

        pairs = []
        for entry in individual_bib_database.entries:
            old_hash = entry_hash_function.create_hash_function[PRIOR_VERSION](
                entry)
            old_hash_prefixed = 'old_hash_' + old_hash
            new_hash = entry_hash_function.create_hash_function[NEW_VERSION](
                entry)
            pairs.append([old_hash_prefixed, new_hash])

        if old_hash == new_hash:
            print('old_hash == new_hash (identical hash function?)')

        # replace in MAIN_REFERENCES
        with open(MAIN_REFERENCES) as file:
            filedata = file.read()

        for old_hash_prefixed, new_hash in pairs:
            filedata = filedata.replace(old_hash_prefixed, new_hash)

        with open(MAIN_REFERENCES, 'w') as file:
            file.write(filedata)

    return


if __name__ == '__main__':

    print('')
    print('')

    print('Renew hash_ids')
    print('')
    print('Simply change the HASH_ID_FUNCTION in shared_config.yaml')
    print('')

    repo = git.Repo()
    shared_config_path = 'shared_config.yaml'
    revlist = (
        (commit, (commit.tree / shared_config_path).data_stream.read())
        for commit in repo.iter_commits(paths=shared_config_path)
    )
    PRIOR_VERSION = ''
    for commit, filecontents in list(revlist):
        shared_config = yaml.load(filecontents, Loader=yaml.FullLoader)
        PRIOR_VERSION = shared_config['params']['HASH_ID_FUNCTION']
        break

    with open(shared_config_path) as shared_config_yaml:
        shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)
    NEW_VERSION = shared_config['params']['HASH_ID_FUNCTION']

    if PRIOR_VERSION == NEW_VERSION:
        print('Please change the HASH_ID_FUNCTION in shared_config.yaml')
        sys.exit()

    print('Changing from ' + PRIOR_VERSION + ' to ' + NEW_VERSION)

    input('retrieve the latest remote commit-id from pipeline-repo and ' +
          ' set it to the pre_commit_hook_version_id variable')
    pre_commit_hook_version_id = '12a31e8'
    # import git
    # from pathlib import Path

    # repo_url = 'https://github.com/path/to/your/repo.git'
    # local_repo_dir = Path('/path/to/your/repo')

    # delete the repo if it exists, perform shallow clone, get SHA, delete repo
    # local_repo_dir.unlink(missing_ok=True)
    # repo = git.Repo.clone_from(repo_url, local_repo_dir, depth=1)
    # sha = repo.rev_parse('origin/master')
    # local_repo_dir.unlink()
    # print(sha)

    with open('.pre-commit-config.yaml') as pre_commit_config_yaml:
        pre_commit_config = yaml.load(
            pre_commit_config_yaml, Loader=yaml.FullLoader)
    for hook in pre_commit_config['repos']:
        if hook['repo'] == \
                'https://github.com/geritwagner/pipeline-validation-hooks':
            old_pre_commit_hook_id = hook['rev']

    # Note: do not use the yaml library to preserve the formatting
    fin = open('.pre-commit-config.yaml')
    data = fin.read()
    data = data.replace(old_pre_commit_hook_id, pre_commit_hook_version_id)
    fin.close()
    fin = open('.pre-commit-config.yaml', 'wt')
    fin.write(data)
    fin.close()

    repo.index.add(['.pre-commit-config.yaml'])
    repo.index.add([shared_config_path])

    print('\nTODO: check for entries that have no old_hash prefix')
    print('Check: git clean state?')
    print('CHECK: will hash_ids be replaced in al relevant files? ')

    # Warn if "old_hash_" in any of the files
    with open(MAIN_REFERENCES) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in MAIN_REFERENCES')

    # (perhaps replace in all files, not just selected ones?)

    # To avoid creating odl/new hash_collisions in the replacement process,
    # create prefixes for the old hash_ids
    for bib_file in utils.get_bib_files():
        prefix_old_hash_ids(bib_file)

    for bib_file in utils.get_bib_files():
        replace_hash_ids(bib_file)

    # Warn if "old_hash_" in any of the files
    with open(MAIN_REFERENCES) as file:
        filedata = file.read()

    if 'old_hash_' in filedata:
        print('ERROR: "old_hash_" in MAIN_REFERENCES')
    else:
        repo.index.add([MAIN_REFERENCES])
