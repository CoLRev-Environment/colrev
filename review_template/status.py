#! /usr/bin/env python3
import os
import sys

import git
import pandas as pd
import yaml

from review_template import repo_setup
from review_template import utils

repo, status_freq, cur_stati = None, None, None
SHARE_STAT_REQ, MAIN_REFERENCES, SCREEN, DATA = None, None, None, None


class colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    ORANGE = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def lsremote(url):
    remote_refs = {}
    g = git.cmd.Git()
    for ref in g.ls_remote(url).split('\n'):
        hash_ref_list = ref.split('\t')
        remote_refs[hash_ref_list[1]] = hash_ref_list[0]
    return remote_refs


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
    manual_preparation_entries = 0
    prepared_entries = 0
    manual_merging_entries = 0
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
                if '{needs_manual_preparation}' in line:
                    manual_preparation_entries += 1
                if '{prepared}' in line:
                    prepared_entries += 1
                if '{needs_manual_merging}' in line:
                    manual_merging_entries += 1
                if '{processed}' in line:
                    processed_entries += 1
                if 'entry_link' in line:
                    nr_entry_links = line.count(';')
                    entry_links += nr_entry_links + 1
                    merged_entry_links += nr_entry_links
                if 'file=' in line.replace(' ', ''):
                    pdf_available += 1

                line = f.readline()

    retrieved = get_nr_search()
    non_imported = retrieved - entry_links
    overall_imported = entry_links
    overall_prepared = prepared_entries + manual_merging_entries + \
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
        nr_to_pre_screen = \
            pre_screen_total - pre_screen_included - pre_screen_excluded
        # screen[screen['inclusion_1'] == 'TODO'].shape[0]
        pdfs_to_retrieve = \
            pre_screen_total - pre_screen_excluded - pdf_available
        screen.drop(screen[screen['inclusion_1'] == 'no'].index, inplace=True)
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
            nr_to_data = \
                screen[screen['inclusion_2'] == 'yes'].shape[0] - data.shape[0]
        else:
            nr_to_data = screen[screen['inclusion_2'] == 'yes'].shape[0]

    freqs = {'retrieved': retrieved,
             'non_imported': non_imported,
             'needs_manual_completion': needs_manual_completion_entries,
             'imported': imported_entries,
             'needs_manual_preparation': manual_preparation_entries,
             'prepared': prepared_entries,
             'needs_manual_merging': manual_merging_entries,
             'duplicates_removed': merged_entry_links,
             'overall_imported': overall_imported,
             'overall_prepared': overall_prepared,
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
        status_of_records = list(set(status_of_records))

    return status_of_records


def get_remote_commit_differences(repo):
    nr_commits_behind, nr_commits_ahead = -1, -1

    if repo.active_branch.tracking_branch() is not None:

        branch_name = str(repo.active_branch)
        tracking_branch_name = str(repo.active_branch.tracking_branch())
        print(f'{branch_name} - {tracking_branch_name}')
        behind_operation = branch_name + '..' + tracking_branch_name
        commits_behind = repo.iter_commits(behind_operation)
        ahead_operation = tracking_branch_name + '..' + branch_name
        commits_ahead = repo.iter_commits(ahead_operation)
        nr_commits_behind = (sum(1 for c in commits_behind))
        nr_commits_ahead = (sum(1 for c in commits_ahead))

        # TODO: check whether this also considers non-pulled changes!? (fetch?)

    return nr_commits_behind, nr_commits_ahead


def is_git_repo(path):
    try:
        _ = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        return False


def repository_validation():
    global repo
    if not is_git_repo(os.getcwd()):
        print('No git repository. Use '
              f'{colors.GREEN}review_template init{colors.END}')
        sys.exit()

    repo = git.Repo('')

    required_paths = ['search', 'private_config.ini',
                      'shared_config.ini', '.pre-commit-config.yaml',
                      '.gitignore']
    if not all(os.path.exists(x) for x in required_paths):
        print('No review_template repository\n  Missing: ' +
              ', '.join([x for x in required_paths if not os.path.exists(x)]) +
              '\n  To retrieve a shared repository, use ' +
              f'{colors.GREEN}review_template init{colors.END}.' +
              '\n  To initalize a new repository, execute the command ' +
              'in an empty directory.\nExit.')
        sys.exit()

    with open('.pre-commit-config.yaml') as pre_commit_y:
        pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
    installed_hooks = []
    remote_pv_hooks_repo = \
        'https://github.com/geritwagner/pipeline-validation-hooks'
    for repository in pre_commit_config['repos']:
        if repository['repo'] == remote_pv_hooks_repo:
            local_hooks_version = repository['rev']
            installed_hooks = [hook['id'] for hook in repository['hooks']]
    if not installed_hooks == ['consistency-checks', 'formatting']:
        print(f'{colors.RED}Pre-commit hooks not installed{colors.END}.'
              '\n See '
              'https://github.com/geritwagner/pipeline-validation-hooks'
              '#using-the-pre-commit-hook for details')
        sys.exit()

    try:
        refs = lsremote(remote_pv_hooks_repo)
        remote_sha = refs['HEAD']

        if not remote_sha == local_hooks_version:
            # Default: automatically update hooks
            print('Updating pre-commit hooks...')
            os.system('pre-commit autoupdate')

            print('Commit updated pre-commit hooks')
            repo.index.add(['.pre-commit-config.yaml'])
            flag, flag_details = utils.get_version_flags()
            repo.index.commit(
                'Update pre-commit-config' + flag + flag_details +
                '\n - ' + utils.get_package_details(),
                author=git.Actor('script:' + os.path.basename(__file__), ''),
                committer=git.Actor(repo_setup.config['GIT_ACTOR'],
                                    repo_setup.config['EMAIL']),
            )
        # we could offer a parameter to disable autoupdates (warn accordingly)
        #     print('  pipeline-validation-hooks version outdated.\n  use ',
        #           f'{colors.RED}pre-commit autoupdate{colors.END}')
        #     sys.exit()
        #     # once we use tags, we may consider recommending
        #     # pre-commit autoupdate --bleeding-edge
    except git.exc.GitCommandError:
        print('  Warning: No Internet connection, cannot check remote '
              'pipeline-validation-hooks repository for updates.')
        pass

    return


def repository_load():
    global repo
    global SHARE_STAT_REQ
    global MAIN_REFERENCES
    global SCREEN
    global DATA

    SHARE_STAT_REQ = repo_setup.config['SHARE_STAT_REQ']
    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']
    SCREEN = repo_setup.paths['SCREEN']
    DATA = repo_setup.paths['DATA']

    # TODO: check whether it is a valid git repo

    # Notify users when changes in bib files are not staged
    # (this may raise unexpected errors)
    non_tracked = [item.a_path for item in repo.index.diff(None)
                   if '.bib' == item.a_path[-4:]]
    if len(non_tracked) > 0:
        print('Warning: Non-tracked files that may cause failing checks: '
              + ','.join(non_tracked))
    return


def review_status():
    global status_freq

    print('\nStatus\n')

    if not os.path.exists(MAIN_REFERENCES):
        print(' | Search')
        print(' |  - Not yet initiated')
    else:
        status_freq = get_status_freq()
        # TODO: set all status_freq to str() to avoid frequent str() calls
        # for the Instructions, parse all to int
        # Search

        # Note:
        # retrieved, imported, prepared, processed are overall/cumulative,
        # the others (non_imported, ...) are the absolute nr. of records
        # currently having this status.

        print(' | Search')
        print(
            ' |  - Records retrieved: ' +
            f'{str(status_freq["retrieved"]).rjust(5, " ")}',
        )

        if status_freq['non_imported'] > 0:
            print(' |                               * ' +
                  f'{str(status_freq["non_imported"]).rjust(6, " ")}' +
                  ' record(s) not yet imported.')

        print(' |  - Records imported: ' +
              f'{str(status_freq["overall_imported"]).rjust(6, " ")}')

        if status_freq['needs_manual_completion'] > 0:
            nr_nmco = status_freq['needs_manual_completion']
            print(' |                               * ' +
                  f'{str(nr_nmco).rjust(6, " ")}' +
                  ' record(s) need manual completion.')

        if status_freq['needs_manual_preparation'] > 0:
            nr_nmcl = status_freq['needs_manual_preparation']
            print(' |                               * ' +
                  f'{str(nr_nmcl).rjust(6, " ")}' +
                  ' record(s) need manual preparation.')

        print(' |  - Records prepared: ' +
              f'{str(status_freq["overall_prepared"]).rjust(6, " ")}')

        if status_freq['prepared'] > 0 and \
                (status_freq['prepared'] == status_freq['overall_imported']):
            print(' |                               * ' +
                  f'{str(status_freq["prepared"]).rjust(6, " ")}' +
                  ' record(s) need merging.')

        if status_freq['needs_manual_merging'] > 0:
            print(' |                               * ' +
                  f'{str(status_freq["needs_manual_merging"]).rjust(6, " ")}' +
                  ' record(s) need manual merging.')

        print(' |  - Records processed: ' +
              f'{str(status_freq["overall_processed"]).rjust(5, " ")}' +
              '   ->' +
              f'{str(status_freq["duplicates_removed"]).rjust(6, " ")}' +
              ' duplicates removed'
              )
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
                f'{str(status_freq["pre_screen_included"]).rjust(14, " ")}' +
                '   ->' +
                f'{str(status_freq["pre_screen_excluded"]).rjust(6, " ")}' +
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
                      f'{str(status_freq["pdfs_to_retrieve"]).rjust(18, " ")}')
            print(' |')

            print(' | Screen')
            print(' |  - Total: ' +
                  f'{str(status_freq["screen_total"]).rjust(17, " ")}')

            print(
                ' |  - Included: ' +
                f'{str(status_freq["screen_included"]).rjust(14, " ")}   ->' +
                f'{str(status_freq["screen_excluded"]).rjust(6, " ")} ' +
                'records excluded'
            )
            if 0 != status_freq['nr_to_screen']:
                print(
                    ' |  - TODO: ' +
                    f'{str(status_freq["nr_to_screen"]).rjust(18, " ")}',
                )
            print(' |')

        # Data
        if not os.path.exists(DATA):
            print(' | Data')
            print(' |  - Not yet initiated')
        else:
            print(' | Data extraction')
            print(' |  - Total: ' +
                  f'{str(status_freq["data_total"]).rjust(17, " ")}')
            if 0 != status_freq['nr_to_data']:
                print(
                    ' |  - TODO: ' +
                    f'{str(status_freq["nr_to_data"]).rjust(18, " ")}',
                )

    return


def review_instructions():
    global status_freq
    global cur_stati

    print('\n\nInstructions (review_template)\n')
    # Note: review_template init is suggested in repository_validation()
    if not os.path.exists(MAIN_REFERENCES):
        print('  To import, copy search results to the search directory. ' +
              'Then use\n     review_template process')
        return

    cur_stati = get_status()

    if status_freq['non_imported'] > 0:
        print('  To import, use\n     review_template process')
        return

    if status_freq['needs_manual_completion'] > 0:
        print('  To continue with manual completion or records, '
              'use\n     review_template man-comp')
        return

    if status_freq['prepared'] > 0:
        print('  To continue with entry preparation, '
              'use\n     review_template process')
        return

    if status_freq['needs_manual_preparation'] > 0:
        print('  To continue with manual preparation, '
              'use\n     review_template man-prep')
        return

    if status_freq['needs_manual_merging'] > 0:
        print('  To continue manual processing of duplicates, '
              'use\n     review_template man-dedupe')
        return

    # TODO: if pre-screening activated in template variables
    if status_freq['nr_to_pre_screen'] > 0:
        print('  To continue with prescreen, '
              'use\n     review_template prescreen')
        return

    if status_freq['pdfs_to_retrieve'] > 0:
        print('  To continue with pdf acquisition, '
              'use\n     review_template pdfs')
        return

    if status_freq['non_bw_searched'] > 0:
        print('  To execute backward search, '
              'use\n     review_template back-search')
        # no return because backward searches are optional

    if status_freq['nr_to_screen'] > 0:
        print('  To continue with screen, '
              'use\n     review_template screen')
        return

    # TODO: if data activated in template variables
    if status_freq['nr_to_data'] > 0:
        print('  To continue with data extraction/analysis, '
              'use\n     review_template data')
        return

    # if any(cs in ['imported', 'prepared', 'pre-screened',
    #                 'pdf_acquired', 'included']
    #         for cs in cur_stati):
    #     print(
    #         '  To continue (automated) processing, ',
    #         'use\n     review_template process')
    print('\n  Nothing to do. To start another review cycle, add '
          'papers to search/ and use\n     review_template process')
    if 'MANUSCRIPT' == repo_setup.config['DATA_FORMAT']:
        print('\n  To build the paper use\n     review_template paper')
    return


def collaboration_instructions():
    global cur_stati

    print('\n\nCollaboration and sharing (git)\n\n')

    nr_commits_behind, nr_commits_ahead = get_remote_commit_differences(repo)

    if nr_commits_behind == -1 and nr_commits_ahead == -1:
        print('  Not connected to a shared repository '
              '(tracking a remote branch).\n  Create remote repository and '
              'use\n     git remote add origin https://github.com/user/repo\n'
              f'     git push origin {repo.active_branch.name}')
    else:
        print(f' Requirement: {SHARE_STAT_REQ}')

        if nr_commits_behind > 0:
            print('Remote changes available on the server.\n'
                  'Once you have committed your changes, get the latest '
                  'remote changes. Use \n   git pull')
        if nr_commits_ahead > 0:
            print('Local changes not yet on the server.\n'
                  'Once you have committed your changes, upload them '
                  'to the remote server. Use \n   git push')

        if SHARE_STAT_REQ == 'NONE':
            print(f' Currently: '
                  f'{colors.GREEN}ready for sharing{colors.END}'
                  f' (if consistency checks pass)')

        # TODO all the following: should all search results be imported?!
        if SHARE_STAT_REQ == 'PROCESSED':
            if not any(cs in ['needs_manual_completion', 'imported',
                              'needs_manual_preparation', 'prepared',
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
        if SHARE_STAT_REQ == 'SCREENED':
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

        if SHARE_STAT_REQ == 'COMPLETED':
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
    return


def main():

    repository_validation()
    repository_load()
    review_status()
    review_instructions()
    collaboration_instructions()

    return


if __name__ == '__main__':
    main()
