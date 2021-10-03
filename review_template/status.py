#! /usr/bin/env python3
import os

import git
import pandas as pd
import yaml

from review_template import entry_hash_function

default_shared_params = dict(
    params=dict(
        MERGING_NON_DUP_THRESHOLD=0.7,
        MERGING_DUP_THRESHOLD=0.95,
        BATCH_SIZE=500,
        HASH_ID_FUNCTION='v_0.3',
        SHARE_STATUS_REQUIREMENT='PROCESSED',
    )
)


def lsremote(url):
    remote_refs = {}
    g = git.cmd.Git()
    for ref in g.ls_remote(url).split('\n'):
        hash_ref_list = ref.split('\t')
        remote_refs[hash_ref_list[1]] = hash_ref_list[0]
    return remote_refs


try:
    remote_pv_hooks_repo = \
        'https://github.com/geritwagner/pipeline-validation-hooks'
    refs = lsremote(remote_pv_hooks_repo)
    remote_sha = refs['HEAD']

    with open('.pre-commit-config.yaml') as pre_commit_config_yaml:
        pre_commit_config = \
            yaml.load(pre_commit_config_yaml, Loader=yaml.FullLoader)

    for repo in pre_commit_config['repos']:
        if repo['repo'] == remote_pv_hooks_repo:
            local_sha = repo['rev']

    if not remote_sha == local_sha:
        print('pipeline-validation-hooks version outdated.\n',
              '  use pre-commit autoupdate')
        # once we use tags, we may consider recommending
        # pre-commit autoupdate --bleeding-edge
except git.exc.GitCommandError:
    print('Warning: No Internet connection, cannot check remote '
          'pipeline-validation-hooks repository for updates.')
    pass

if not os.path.exists('shared_config.yaml'):
    with open('shared_config.yaml', 'w') as outfile:
        yaml.dump(default_shared_params, outfile)
    print('Initiated shared_config.yaml with default parameters.')

with open('shared_config.yaml') as shared_config_yaml:
    shared_config = yaml.load(shared_config_yaml, Loader=yaml.FullLoader)

if shared_config is None:
    with open('shared_config.yaml', 'w') as outfile:
        yaml.dump(default_shared_params, outfile)
    shared_config = default_shared_params
    print('Initiated shared_config.yaml with default parameters.')

if 'params' not in shared_config:
    shared_config['params'] = default_shared_params['params']
    with open('shared_config.yaml', 'w') as outfile:
        yaml.dump(shared_config, outfile)
    print('Initiated shared_config.yaml with default parameters.')

for param, value in default_shared_params['params'].items():
    if param not in shared_config['params']:
        shared_config['params'][param] = value
        print(f'Added default value for {param} to shared_config.yaml')
        with open('shared_config.yaml', 'w') as outfile:
            yaml.dump(shared_config, outfile)

HASH_ID_FUNCTION = shared_config['params']['HASH_ID_FUNCTION']
SHARE_STATUS_REQUIREMENT = shared_config['params']['SHARE_STATUS_REQUIREMENT']


default_private_params = dict(
    params=dict(
        EMAIL='user@name.com',
        CPUS=2,
        DEBUG_MODE=0,
    ),
    PDFPATH=dict(
        path_1='/home/user/data/pdfs',
    )
)

if not os.path.exists('private_config.yaml'):
    with open('private_config.yaml', 'w') as outfile:
        yaml.dump(default_private_params, outfile)
    print('Initiated private_config.yaml with default parameters.')

with open('private_config.yaml') as private_config_yaml:
    private_config = yaml.load(private_config_yaml, Loader=yaml.FullLoader)

if private_config is None:
    with open('private_config.yaml', 'w') as outfile:
        yaml.dump(default_private_params, outfile)
    private_config = default_private_params
    print('Initiated private_config.yaml with default parameters.')

if 'params' not in private_config:
    private_config['params'] = default_private_params['params']
    with open('private_config.yaml', 'w') as outfile:
        yaml.dump(private_config, outfile)
    print('Initiated private_config.yaml with default parameters.')

for param, value in default_private_params['params'].items():
    if param not in private_config['params']:
        private_config['params'][param] = value
        print(f'Added default value for {param} to private_config.yaml')
        with open('private_config.yaml', 'w') as outfile:
            yaml.dump(private_config, outfile)

if 'PDFPATH' not in private_config:
    private_config['PDFPATH'] = default_private_params['PDFPATH']
    with open('private_config.yaml', 'w') as outfile:
        yaml.dump(private_config, outfile)
    print('Initiated private_config.yaml with default parameters.')

for param, value in default_private_params['PDFPATH'].items():
    if param not in private_config['PDFPATH']:
        private_config['PDFPATH'][param] = value
        print(f'Added default value for {param} to private_config.yaml')
        with open('private_config.yaml', 'w') as outfile:
            yaml.dump(private_config, outfile)

CPUS = private_config['params']['CPUS']
DEBUG_MODE = private_config['params']['DEBUG_MODE']

if private_config['params']['EMAIL'] == 'user@name.com':
    print('Please set the EMAIL field in private_config.yaml.')

defaul_gitignore = ['private_config.yaml',
                    '.local_pdf_indices',
                    '.index-*',
                    'missing_pdf_files.csv',
                    '*.bib.sav']

if not os.path.exists('.gitignore'):
    first_line = True
    with open('.gitignore', 'a') as gigitnore:
        for def_item in defaul_gitignore:
            if first_line:
                gigitnore.write(def_item)
                first_line = False
            else:
                gigitnore.write('\n' + def_item)
    print('Created default .gitignore file.')


for def_item in defaul_gitignore:
    with open('.gitignore') as gigitnore:
        if def_item not in gigitnore.read():
            with open('.gitignore', 'a') as gigitnore:
                gigitnore.write('\n' + def_item)
            print('Updated .gitignore file with defaults.')

MAIN_REFERENCES = \
    entry_hash_function.paths[HASH_ID_FUNCTION]['MAIN_REFERENCES']
SCREEN = entry_hash_function.paths[HASH_ID_FUNCTION]['SCREEN']
DATA = entry_hash_function.paths[HASH_ID_FUNCTION]['DATA']

PASS = 0
FAIL = 1


class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def get_bib_files():
    bib_files = []
    search_dir = os.path.join(os.getcwd(), 'search/')
    bib_files = [os.path.join(search_dir, x)
                 for x in os.listdir(search_dir) if x.endswith('.bib')]
    return bib_files


def get_nr_in_bib(file_path):

    number_in_bib = 0

    with open(file_path) as f:
        line = f.readline()
        while line:
            # Note: the '﻿' occured in some bibtex files
            # (e.g., Publish or Perish exports)
            if line.replace('﻿', '').lstrip()[:1] == '@':
                if not '@comment' == \
                        line.replace('﻿', '').lstrip()[:8].lower():
                    number_in_bib += 1
            line = f.readline()

    return number_in_bib


def get_nr_search():
    number_search = 0

    for search_file in get_bib_files():
        number_search += get_nr_in_bib(search_file)

    return number_search


def get_status_freq():
    needs_manual_completion_entries = 0
    imported_entries = 0
    manual_cleansing_entries = 0
    cleansed_entries = 0
    manual_merging_entries = 0
    merged_hash_ids = 0
    processed_entries = 0
    entry_links = 0
    merged_entry_links = 0
    pdf_available = 0

    if os.path.exists(MAIN_REFERENCES):
        with open(MAIN_REFERENCES) as f:
            line = f.readline()
            while line:
                if '{needs_manual_completion}' in line:
                    needs_manual_completion_entries += 1
                if '{imported}' in line:
                    imported_entries += 1
                if '{needs_manual_cleansing}' in line:
                    manual_cleansing_entries += 1
                if '{cleansed}' in line:
                    cleansed_entries += 1
                if '{needs_manual_merging}' in line:
                    manual_merging_entries += 1
                if '{processed}' in line:
                    processed_entries += 1
                if 'hash_id' == line.lstrip()[:7]:
                    # note: do not consider last comma (field separator)
                    nr_hash_ids = line.count(',') - 1
                    merged_hash_ids += nr_hash_ids
                if 'entry_link' in line:
                    nr_entry_links = line.count(';')
                    entry_links += nr_entry_links + 1
                    merged_entry_links += nr_entry_links
                if 'file=' in line.replace(' ', ''):
                    pdf_available += 1

                line = f.readline()

    retrieved = get_nr_search()
    non_imported = retrieved - entry_links
    overall_imported = entry_links - needs_manual_completion_entries
    overall_cleansed = cleansed_entries + manual_merging_entries + \
        processed_entries + merged_entry_links

    pre_screen_total = processed_entries
    pre_screen_included = 0
    pre_screen_excluded = 0
    nr_to_pre_screen = pre_screen_total - pre_screen_included - \
        pre_screen_excluded
    pdfs_to_retrieve = 0
    non_bw_searched = 0
    screen_total = 0
    screen_included = 0
    screen_excluded = 0
    nr_to_screen = 0
    data_total = 0
    nr_to_data = 0

    if os.path.exists(SCREEN):
        screen = pd.read_csv(SCREEN, dtype=str)
        pre_screen_total = screen.shape[0]
        pre_screen_included = screen[screen['inclusion_1'] == 'yes'].shape[0]
        pre_screen_excluded = screen[screen['inclusion_1'] == 'no'].shape[0]
        nr_to_pre_screen = pre_screen_total - pre_screen_included - \
            pre_screen_excluded
        # screen[screen['inclusion_1'] == 'TODO'].shape[0]
        pdfs_to_retrieve = pre_screen_total - pre_screen_excluded - \
            pdf_available
        screen.drop(
            screen[screen['inclusion_1'] == 'no'].index, inplace=True,
        )
        screen_total = screen.shape[0]
        screen_included = screen[screen['inclusion_2'] == 'yes'].shape[0]
        screen_excluded = screen[screen['inclusion_2'] == 'no'].shape[0]
        nr_to_screen = screen[screen['inclusion_2'] == 'TODO'].shape[0]

        if os.path.exists('pdfs/'):
            pdf_files = [x for x in os.listdir('pdfs/')]
            search_files = [x for x in os.listdir('search/')
                            if '.bib' == x[-4:]]
            non_bw_searched = len([x for x in pdf_files
                                   if not x.replace('.pdf', 'bw_search.bib')
                                   in search_files])

        if os.path.exists(DATA):
            data = pd.read_csv(DATA, dtype=str)
            data_total = data.shape[0]
            nr_to_data = screen[screen['inclusion_2'] == 'yes'].shape[0] - \
                data.shape[0]

    freqs = {'retrieved': retrieved,
             'non_imported': non_imported,
             'needs_manual_completion': needs_manual_completion_entries,
             'imported': imported_entries,
             'needs_manual_cleansing': manual_cleansing_entries,
             'cleansed': cleansed_entries,
             'needs_manual_merging': manual_merging_entries,
             'merged_hash_ids': merged_hash_ids,
             'overall_imported': overall_imported,
             'overall_cleansed': overall_cleansed,
             'overall_processed': processed_entries,
             'pre_screen_total': pre_screen_total,
             'nr_to_pre_screen': nr_to_pre_screen,
             'pre_screen_included': pre_screen_included,
             'pre_screen_excluded': pre_screen_excluded,
             'nr_to_screen': nr_to_screen,
             'pdf_available': pdf_available,
             'pdfs_to_retrieve': pdfs_to_retrieve,
             'non_bw_searched': non_bw_searched,
             'screen_total': screen_total,
             'screen_included': screen_included,
             'screen_excluded': screen_excluded,
             'nr_to_data': nr_to_data,
             'data_total': data_total,
             }

    return freqs


def get_status():
    status_of_records = []

    with open(MAIN_REFERENCES) as f:
        line = f.readline()
        while line:
            if line.lstrip().startswith('status'):
                status_of_records.append(line.replace('status', '')
                                             .replace('=', '')
                                             .replace('{', '')
                                             .replace('}', '')
                                             .replace(',', '')
                                             .lstrip().rstrip())
            line = f.readline()

    return list(set(status_of_records))


def get_remote_commit_differences(repo):
    nr_commits_behind, nr_commits_ahead = -1, -1

    if repo.active_branch.tracking_branch() is not None:

        branch_name = str(repo.active_branch)
        tracking_branch_name = str(repo.active_branch.tracking_branch())
        print(branch_name + ' - ' + tracking_branch_name)
        behind_operation = branch_name + '..' + tracking_branch_name
        commits_behind = repo.iter_commits(behind_operation)
        ahead_operation = tracking_branch_name + '..' + branch_name
        commits_ahead = repo.iter_commits(ahead_operation)
        nr_commits_behind = (sum(1 for c in commits_behind))
        nr_commits_ahead = (sum(1 for c in commits_ahead))

        # TODO: check whether this also considers non-pulled changes!? (fetch?)

    return nr_commits_behind, nr_commits_ahead


def main():

    # TBD: copy all of the initialize.py to this position?

    # Notify users when changes in bib files are not staged
    # (this may raise unexpected errors)
    status_freq = get_status_freq()

    if DEBUG_MODE:
        print('\nConfiguration\n')

        print(' - Hash function:                 ' + HASH_ID_FUNCTION)
        print(' - Local:                         ' +
              str(CPUS) + ' CPUS available')
        print('   DEBUG mode enabled')

    repo = git.Repo('')

    non_tracked = [item.a_path for item in repo.index.diff(None)
                   if '.bib' == item.a_path[-4:]]

    if len(non_tracked) > 0:
        print('Warning: Non-tracked files that may cause failing checks: '
              + ','.join(non_tracked))

    print('\nStatus\n')
    if not os.path.exists(MAIN_REFERENCES):
        print(' | Search')
        print(' |  - Not yet initiated')

        print('\n\nInstructions\n')
        # TBD: print(' To start, use \n\n     review_template initalize\n\n')
        print('  To import, copy search results to the search directory.' +
              '  Then use\n     review_template process')
    else:
        # Search

        # Note:
        # retrieved, imported, cleansed, processed are overall/cumulative,
        # the others (non_imported, ...) are the absolute nr. of records
        # currently having this status.

        print(' | Search')
        print(
            ' |  - Records retrieved: ' +
            str(status_freq['retrieved']).rjust(5, ' '),
        )

        if status_freq['non_imported'] > 0:
            print(' |                               * ' +
                  str(status_freq['non_imported']).rjust(6, ' ') +
                  ' record(s) not yet imported.')

        if status_freq['needs_manual_completion'] > 0:
            print(' |                               * ' +
                  str(status_freq['needs_manual_completion']).rjust(6, ' ') +
                  ' record(s) need manual completion before import.')

        print(' |  - Records imported: ' +
              str(status_freq['overall_imported']).rjust(6, ' '))

        if status_freq['needs_manual_cleansing'] > 0:
            print(' |                               * ' +
                  str(status_freq['needs_manual_cleansing']).rjust(6, ' ') +
                  ' record(s) need manual cleansing.')

        print(' |  - Records cleansed: ' +
              str(status_freq['overall_cleansed']).rjust(6, ' '))

        if status_freq['cleansed'] > 0:
            print(' |                               * ' +
                  str(status_freq['cleansed']).rjust(6, ' ') +
                  ' record(s) need merging.')

        if status_freq['needs_manual_merging'] > 0:
            print(' |                               * ' +
                  str(status_freq['needs_manual_merging']).rjust(6, ' ') +
                  ' record(s) need manual merging.')

        # if status_freq['identical_hash_id'] > 0:
        #     print(' |                               -> ' +
        #           str(status_freq['identical_hash_id']).rjust(5, ' ') +
        #           ' record(s) merged (identical hash_ids).')
        # Some records may not have been processed yet.
        # counting commas in the hash_id field does not consider
        # implicit merging (based on identical hash_ids)!
        if status_freq['merged_hash_ids'] > 0:
            print(' |                               -> ' +
                  str(status_freq['merged_hash_ids']).rjust(5, ' ') +
                  ' record(s) merged (non-identical hash_ids).')

        print(' |  - Records processed: ' +
              str(status_freq['overall_processed']).rjust(5, ' '))

        print(' |')

        # Screen
        if not os.path.exists(SCREEN):
            print(' | Screen')
            print(' |  - Not yet initiated')
            print(' |')
        else:

            print(' | Pre-screen')
            print(' |  - Total: ' +
                  str(status_freq['pre_screen_total']).rjust(17, ' '))
            print(
                ' |  - Included: ' +
                str(status_freq['pre_screen_included'])
                .rjust(14, ' ') +
                '   ->' +
                str(status_freq['pre_screen_excluded']).rjust(6, ' ') +
                ' records excluded'
            )

            if 0 != status_freq['nr_to_pre_screen']:
                print(
                    ' |  - TODO: ' +
                    str(status_freq['nr_to_pre_screen']).rjust(18, ' '),
                )

            print(' |')
            print(' | PDF acquisition')
            print(' |  - Retrieved: ' +
                  str(status_freq['pdf_available']).rjust(13, ' '))
            if 0 != status_freq['pdfs_to_retrieve']:
                print(' |  - TODO: ' +
                      str(status_freq['pdfs_to_retrieve']).rjust(18, ' '))
            print(' |')

            print(' | Screen')
            print(' |  - Total: ' +
                  str(status_freq['screen_total']).rjust(17, ' '))

            print(
                ' |  - Included: ' +
                str(status_freq['screen_included'])
                .rjust(14, ' ') +
                '   ->' +
                str(status_freq['screen_excluded'])
                .rjust(6, ' ') + ' records excluded'
            )
            if 0 != status_freq['nr_to_screen']:
                print(
                    ' |  - TODO: ' +
                    str(status_freq['nr_to_screen'])
                    .rjust(18, ' '),
                )
            print(' |')

        # Data
        if not os.path.exists(DATA):
            print(' | Data')
            print(' |  - Not yet initiated')
        else:
            print(' | Data extraction')
            print(' |  - Total: ' +
                  str(status_freq['data_total']).rjust(17, ' '))
            if 0 != status_freq['nr_to_data']:
                print(
                    ' |  - TODO: ' +
                    str(status_freq['nr_to_data']).rjust(18, ' '),
                )

        # Sharing conditions
        cur_stati = get_status()

        print('\n\nInstructions\n')
        # TODO: include 'processed' once status information beyond 'processed'
        # is joined/available
        automated_processing_completed = True
        if status_freq['needs_manual_completion'] > 0:
            print('  To complete records manually for import, '
                  'use\n     review_template complete-manual')
            automated_processing_completed = False

        if any(cs in ['imported', 'cleansed', 'pre-screened',
                      'pdf_acquired', 'included']
               for cs in cur_stati):
            print(
                '  To continue (automated) processing, ',
                'use\n     review_template process')
            automated_processing_completed = False
        manual_processing_completed = True
        if status_freq['needs_manual_cleansing'] > 0:
            print('  To continue manual cleansing, '
                  'use\n     review_template cleanse-manual')
            manual_processing_completed = False
        if status_freq['needs_manual_merging'] > 0:
            print('  To continue manual processing of duplicates, '
                  'use\n     review_template proc-duplicates-manual')
            manual_processing_completed = False
        if not (automated_processing_completed and
                manual_processing_completed):
            print(f'\n  {colors.RED}Info{colors.END}:'
                  ' to avoid (git) merge conflicts, it is recommended to '
                  'complete the processing \n  before starting '
                  'the pre-screen/screen.')
        else:
            print('  Processing completed for all records.\n\n')
            # TODO: if pre-screening activated in template variables
            if 0 != status_freq['nr_to_pre_screen']:
                print('  To initiate/continue pre-screen,'
                      'use\n     review_template pre-screen')
            # TODO: if pre-screening activated in template variables
            if 0 == status_freq['nr_to_pre_screen'] and \
                    0 != status_freq['non_bw_searched']:
                print('  To initiate/continue backward-search,'
                      'use\n     review_template backward-search')
            elif 0 == status_freq['nr_to_pre_screen'] and \
                    0 != status_freq['nr_to_screen']:
                print('  To initiate/continue screen,'
                      'use\n     review_template screen')
                # TODO: if data activated in template variables
            if 0 == status_freq['nr_to_screen']:
                print('  To initiate/continue data extraction/analysis, '
                      'use\n     review_template data')

        print('\n')
        nr_commits_behind, nr_commits_ahead = \
            get_remote_commit_differences(repo)

        if nr_commits_behind == -1 and nr_commits_ahead == -1:
            print('Collaboration and sharing hints (git)\n\n'
                  '  Not tracking a remote branch. '
                  'Create remote repository and use\n'
                  '     git remote add origin https://github.com/user/repo\n'
                  '     git push origin ' + repo.active_branch.name)
        else:
            print(f'\n\nCollaboration and sharing hints (git)\n\n'
                  f' Requirement: {SHARE_STATUS_REQUIREMENT}')

            if nr_commits_behind > 0:
                print('Remote changes available on the server.\n'
                      'Once you have committed your changes, get the latest '
                      'remote changes. Use '
                      '\n   git pull')
            if nr_commits_ahead > 0:
                print('Local changes not yet on the server.\n'
                      'Once you have committed your changes, upload them '
                      'to the remote server. Use '
                      '\n   git push')

            if SHARE_STATUS_REQUIREMENT == 'NONE':
                print(f' Currently: '
                      f'{colors.GREEN}ready for sharing{colors.END}'
                      f' (if consistency checks pass)')

            # TODO all the following: should all search results be imported?!
            if SHARE_STATUS_REQUIREMENT == 'PROCESSED':
                if not any(cs in ['needs_manual_completion', 'imported',
                                  'needs_manual_cleansing', 'cleansed',
                                  'needs_manual_merging']
                           for cs in cur_stati):
                    print(f' Currently: '
                          f'{colors.GREEN}ready for sharing{colors.END}'
                          f' (if consistency checks pass)')
                else:
                    print(f' Currently: '
                          f'{colors.RED}not ready for sharing{colors.END}\n'
                          f'  All records should be processed before sharing '
                          '(see instructions above).')

            # Note: if we use all(...) in the following,
            # we do not need to distinguish whether
            # a PRE_SCREEN or INCLUSION_SCREEN is needed
            if SHARE_STATUS_REQUIREMENT == 'SCREENED':
                if all(cs in ['pre_screen_excluded', 'excluded',
                              'included', 'coded']
                        for cs in cur_stati):
                    print(f' Currently:'
                          f' {colors.GREEN}ready for sharing{colors.END}'
                          f' (if consistency checks pass)')
                else:
                    print(f' Currently: '
                          f'{colors.RED}not ready for sharing{colors.END}\n'
                          f'  All records should be processed before sharing '
                          '(see instructions above).')
                    print('TODO: update instructions/'
                          'check non-screened records')

            if SHARE_STATUS_REQUIREMENT == 'COMPLETED':
                if all(cs in ['coded', 'excluded', 'pre_screen_excluded']
                        for cs in cur_stati):
                    print(f' Currently: '
                          f'{colors.GREEN}ready for sharing{colors.END}'
                          f' (if consistency checks pass)')
                else:
                    print(f' Currently: '
                          f'{colors.RED}not ready for sharing{colors.END}\n'
                          f'  All records should be processed before sharing '
                          '(see instructions above).')
                    print('TODO: update instructions /check non-screened '
                          'and non-analyzed records')

    print('\n\n')

    return PASS


if __name__ == '__main__':
    main()
