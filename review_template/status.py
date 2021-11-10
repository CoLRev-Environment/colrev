#! /usr/bin/env python3
import os
import sys

import git
import yaml

from review_template import init
from review_template import repo_setup
from review_template import screen
from review_template import utils

repo = None
SHARE_STAT_REQ, MAIN_REFERENCES = None, None


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


def get_completeness_condition():
    stat = get_status_freq()
    completeness_condition = True
    if 0 != stat['metadata_status']['currently']['non_imported']:
        completeness_condition = False
    if 0 != stat['metadata_status']['currently']['imported']:
        completeness_condition = False
    if 0 != stat['metadata_status']['currently']['prepared']:
        completeness_condition = False
    if 0 != stat['metadata_status']['currently']['needs_manual_preparation']:
        completeness_condition = False
    if 0 != stat['metadata_status']['currently']['needs_manual_merging']:
        completeness_condition = False
    if 0 != stat['pdf_status']['currently']['needs_retrieval']:
        completeness_condition = False
    if 0 != stat['pdf_status']['currently']['needs_manual_retrieval']:
        completeness_condition = False
    if 0 != stat['pdf_status']['currently']['imported']:
        completeness_condition = False
    if 0 != stat['pdf_status']['currently']['needs_manual_preparation']:
        completeness_condition = False
    if 0 != stat['review_status']['currently']['needs_prescreen']:
        completeness_condition = False
    if 0 != stat['review_status']['currently']['needs_screen']:
        completeness_condition = False
    if 0 != stat['review_status']['currently']['needs_synthesis']:
        completeness_condition = False
    return completeness_condition


def get_status_freq():
    MAIN_REFERENCES = repo_setup.paths['MAIN_REFERENCES']

    stat = {}
    stat['metadata_status'] = {}
    stat['metadata_status']['overall'] = {}
    stat['metadata_status']['currently'] = {}
    stat['pdf_status'] = {}
    stat['pdf_status']['overall'] = {}
    stat['pdf_status']['currently'] = {}
    stat['review_status'] = {}
    stat['review_status']['overall'] = {}
    stat['review_status']['currently'] = {}

    md_imported = 0
    md_prepared = 0
    md_needs_manual_preparation = 0
    md_needs_manual_merging = 0
    md_duplicates_removed = 0
    md_processed = 0

    pdfs_needs_retrieval = 0
    pdfs_imported = 0
    pdfs_needs_manual_retrieval = 0
    pdfs_needs_manual_preparation = 0
    pdfs_prepared = 0
    pdfs_not_available = 0

    rev_retrieved = 0
    rev_prescreen_included = 0
    rev_prescreen_excluded = 0
    rev_screen_included = 0
    rev_screen_excluded = 0
    rev_synthesized = 0

    record_links = 0
    excl_criteria = []

    if os.path.exists(MAIN_REFERENCES):
        with open(MAIN_REFERENCES) as f:
            line = f.readline()
            while line:
                if ' rev_status ' in line:
                    if '{retrieved}' in line:
                        rev_retrieved += 1
                    if '{prescreen_included}' in line:
                        rev_prescreen_included += 1
                    if '{prescreen_excluded}' in line:
                        rev_prescreen_excluded += 1
                    if '{included}' in line:
                        rev_screen_included += 1
                    if '{excluded}' in line:
                        rev_screen_excluded += 1
                    if '{synthesized}' in line:
                        rev_synthesized += 1
                if ' md_status ' in line:
                    if '{imported}' in line:
                        md_imported += 1
                    if '{needs_manual_preparation}' in line:
                        md_needs_manual_preparation += 1
                    if '{prepared}' in line:
                        md_prepared += 1
                    if '{needs_manual_merging}' in line:
                        md_needs_manual_merging += 1
                    if '{processed}' in line:
                        md_processed += 1
                if ' pdf_status ' in line:
                    if '{needs_retrieval}' in line:
                        pdfs_needs_retrieval += 1
                    if '{imported}' in line:
                        pdfs_imported += 1
                    if '{needs_manual_retrieval}' in line:
                        pdfs_needs_manual_retrieval += 1
                    if '{needs_manual_preparation}' in line:
                        pdfs_needs_manual_preparation += 1
                    if '{prepared}' in line:
                        pdfs_prepared += 1
                    if '{not_available}' in line:
                        pdfs_not_available += 1
                if 'origin' == line.lstrip()[:6]:
                    nr_record_links = line.count(';')
                    record_links += nr_record_links + 1
                    md_duplicates_removed += nr_record_links
                if ' excl_criteria ' in line:
                    excl_criteria_field = \
                        line[line.find('{')+1:line.find('}')]
                    excl_criteria.append(excl_criteria_field)
                line = f.readline()

    exclusion_statistics = {}
    if excl_criteria:
        criteria = screen.get_excl_criteria(excl_criteria[0])
        exclusion_statistics = {crit: 0 for crit in criteria}
        for exclusion_case in excl_criteria:
            for crit in criteria:
                if crit+'=yes' in exclusion_case:
                    exclusion_statistics[crit] += 1

    # Reverse order (overall_x means x or later status)
    md_overall_processed = md_processed
    md_overall_prepared = md_overall_processed + \
        md_needs_manual_merging + md_duplicates_removed + md_prepared
    md_overall_imported = \
        md_overall_prepared + md_needs_manual_preparation + md_imported
    md_overall_retrieved = get_nr_search()

    md_non_imported = md_overall_retrieved - record_links

    # Reverse order (overall_x means x or later status)
    pdfs_overall_prepared = pdfs_prepared
    pdfs_overall_retrieved = \
        pdfs_overall_prepared + pdfs_needs_manual_preparation + pdfs_imported
    pdfs_overall_needs_retrieval = \
        pdfs_overall_retrieved + pdfs_needs_retrieval + pdfs_not_available + \
        pdfs_needs_manual_retrieval

    # Reverse order (overall_x means x or later status)
    # rev_overall_synthesized = rev_synthesized
    rev_overall_included = rev_screen_included + rev_synthesized
    rev_overall_excluded = rev_screen_excluded
    rev_overall_prescreen_included = \
        rev_prescreen_included + rev_overall_excluded + rev_overall_included
    rev_overall_screen = rev_overall_prescreen_included
    rev_overall_prescreen = md_processed

    rev_needs_prescreen = rev_overall_prescreen - \
        rev_overall_prescreen_included - rev_prescreen_excluded
    rev_needs_screen = \
        rev_overall_screen - rev_overall_included - rev_screen_excluded
    rev_overall_synthesis = rev_overall_included
    rev_needs_synthesis = rev_overall_included - rev_synthesized

    # PDF_DIRECTORY = repo_setup.paths['PDF_DIRECTORY']
    # if os.path.exists(PDF_DIRECTORY):
    #     pdf_files = [x for x in os.listdir(PDF_DIRECTORY)]
    #     search_files = [x for x in os.listdir('search/') if '.bib' == x[-4:]]
    #     non_bw_searched = len([x for x in pdf_files
    #                            if not x.replace('.pdf', 'bw_search.bib')
    #                            in search_files])

    md_cur_stat = stat['metadata_status']['currently']
    md_cur_stat['non_imported'] = md_non_imported
    md_cur_stat['imported'] = md_imported
    md_cur_stat['prepared'] = md_prepared
    md_cur_stat['needs_manual_preparation'] = md_needs_manual_preparation
    md_cur_stat['needs_manual_merging'] = md_needs_manual_merging
    md_cur_stat['processed'] = md_processed
    md_cur_stat['duplicates_removed'] = md_duplicates_removed

    md_overall_stat = stat['metadata_status']['overall']
    md_overall_stat['retrieved'] = md_overall_retrieved
    md_overall_stat['imported'] = md_overall_imported
    md_overall_stat['prepared'] = md_overall_prepared
    md_overall_stat['processed'] = md_overall_processed

    pdf_cur_stat = stat['pdf_status']['currently']
    pdf_cur_stat['needs_retrieval'] = pdfs_needs_retrieval
    pdf_cur_stat['imported'] = pdfs_imported
    pdf_cur_stat['needs_manual_retrieval'] = pdfs_needs_manual_retrieval
    pdf_cur_stat['needs_manual_preparation'] = pdfs_needs_manual_preparation
    pdf_cur_stat['not_available'] = pdfs_not_available
    pdf_cur_stat['prepared'] = pdfs_prepared

    pdf_overall_stat = stat['pdf_status']['overall']
    pdf_overall_stat['needs_retrieval'] = pdfs_overall_needs_retrieval
    pdf_overall_stat['retrieved'] = pdfs_overall_retrieved
    pdf_overall_stat['prepared'] = pdfs_overall_prepared

    rev_cur_stat = stat['review_status']['currently']
    rev_cur_stat['retrieved'] = rev_retrieved
    rev_cur_stat['prescreen_included'] = rev_prescreen_included
    rev_cur_stat['prescreen_excluded'] = rev_prescreen_excluded
    rev_cur_stat['screen_included'] = rev_screen_included
    rev_cur_stat['screen_excluded'] = rev_screen_excluded
    rev_cur_stat['synthesized'] = rev_synthesized
    rev_cur_stat['needs_prescreen'] = rev_needs_prescreen
    rev_cur_stat['needs_screen'] = rev_needs_screen
    rev_cur_stat['needs_synthesis'] = rev_needs_synthesis

    stat['review_status']['currently']['exclusion'] = exclusion_statistics

    rev_overall_stat = stat['review_status']['overall']
    rev_overall_stat['prescreen'] = rev_overall_prescreen
    rev_overall_stat['prescreen_included'] = rev_overall_prescreen_included
    rev_overall_stat['screen'] = rev_overall_screen
    rev_overall_stat['included'] = rev_overall_included
    rev_overall_stat['synthesized'] = rev_synthesized
    rev_overall_stat['synthesis'] = rev_overall_synthesis

    return stat


def get_status():
    status_of_records = []

    with open(repo_setup.paths['MAIN_REFERENCES']) as f:
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

    # Note : 'private_config.ini', 'shared_config.ini' are optional
    required_paths = ['search', '.pre-commit-config.yaml', '.gitignore']
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
    if not installed_hooks == ['check', 'format']:
        os.rename('.pre-commit-config.yaml', 'bak_pre-commit-config.yaml')
        init.retrieve_template_file(
            '../template/.pre-commit-config.yaml',
            '.pre-commit-config.yaml',
        )
        os.system('pre-commit install')
        os.system('pre-commit autoupdate')

        print('Updated pre-commit hook. Please check/remove '
              'bak_pre-commit-config.yaml')
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
            repo.index.commit(
                'Update pre-commit-config' + utils.get_version_flag() +
                utils.get_commit_report(),
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
    except git.exc.GitCommandError as e:
        print(e)
        print('  Warning: No Internet connection, cannot check remote '
              'pipeline-validation-hooks repository for updates.')
        pass

    return


def repository_load():
    global repo

    # TODO: check whether it is a valid git repo

    # Notify users when changes in bib files are not staged
    # (this may raise unexpected errors)
    non_tracked = [item.a_path for item in repo.index.diff(None)
                   if '.bib' == item.a_path[-4:]]
    if len(non_tracked) > 0:
        print('Warning: Non-tracked files that may cause failing checks: '
              + ','.join(non_tracked))
    return


def stat_print(field1, val1, connector=None, field2=None, val2=None):
    if field2 is None:
        field2 = ''
    if val2 is None:
        val2 = ''
    if field1 != '':
        stat = ' |  - ' + field1
    else:
        stat = ' | '
    rjust_padd = 35-len(stat)
    stat = stat + str(val1).rjust(rjust_padd, ' ')
    if connector is not None:
        stat = stat + '  ' + connector + '  '
    if val2 != '':
        rjust_padd = 45-len(stat)
        stat = stat + str(val2).rjust(rjust_padd, ' ') + ' '
    if field2 != '':
        stat = stat + str(field2)
    print(stat)
    return


def review_status():
    global status_freq

    # Principle: first column shows total records/PDFs in each stage
    # the second column shows
    # (blank call)  * the number of records requiring manual action
    #               -> the number of records excluded/merged

    print('\nStatus\n')

    if not os.path.exists(repo_setup.paths['MAIN_REFERENCES']):
        print(' | Search')
        print(' |  - Not initiated')
    else:
        stat = get_status_freq()
        metadata, review, pdfs = \
            stat['metadata_status'], stat['review_status'], stat['pdf_status']

        print(' | Search')
        stat_print('Records retrieved', metadata['overall']['retrieved'])
        if metadata['currently']['non_imported'] > 0:
            stat_print('', '', '*', 'record(s) not yet imported',
                       metadata['currently']['non_imported'])
        stat_print('Records imported', metadata['overall']['imported'])
        if metadata['currently']['imported'] > 0:
            stat_print('', '', '*', 'record(s) need preparation',
                       metadata['currently']['imported'])
        if metadata['currently']['needs_manual_preparation'] > 0:
            stat_print('', '', '*', 'record(s) need manual preparation',
                       metadata['currently']['needs_manual_preparation'])
        stat_print('Records prepared', metadata['overall']['prepared'])
        if metadata['currently']['prepared'] > 0:
            stat_print('', '', '*', 'record(s) need merging',
                       metadata['currently']['prepared'])
        if metadata['currently']['needs_manual_merging'] > 0:
            stat_print('', '', '*', 'record(s) need manual merging',
                       metadata['currently']['needs_manual_merging'])
        stat_print('Records processed',
                   metadata['overall']['processed'], '->',
                   'duplicates removed',
                   metadata['currently']['duplicates_removed'])

        print(' |')
        print(' | Pre-screen')
        if review['overall']['prescreen'] == 0:
            stat_print('Not initiated', '')
        else:
            stat_print('Prescreen size', review['overall']['prescreen'])
            if 0 != review['currently']['needs_prescreen']:
                stat_print('', '', '*', 'records to prescreen',
                           review['currently']['needs_prescreen'])
            stat_print('Included',
                       review['overall']['prescreen_included'],
                       '->', 'records excluded',
                       review['currently']['prescreen_excluded'])

        print(' |')
        print(' | PDFs')
        stat_print('PDFs need retrieval', pdfs['overall']['needs_retrieval'])
        if 0 != pdfs['currently']['needs_retrieval']:
            stat_print('', '', '*', 'PDFs to retrieve',
                       pdfs['currently']['needs_retrieval'])
        if 0 != pdfs['currently']['needs_manual_retrieval']:
            stat_print('', '', '*', 'PDFs to retrieve manually',
                       pdfs['currently']['needs_manual_retrieval'])
        if pdfs['currently']['not_available'] > 0:
            stat_print('PDFs retrieved',
                       pdfs['overall']['retrieved'],
                       '*', 'PDFs not available',
                       pdfs['currently']['not_available'])
        else:
            stat_print('PDFs retrieved',
                       pdfs['overall']['retrieved'])
        if pdfs['currently']['needs_manual_preparation'] > 0:
            stat_print('', '', '*', 'PDFs need manual preparation',
                       pdfs['currently']['needs_manual_preparation'])
        if 0 != pdfs['currently']['imported']:
            stat_print('', '', '*', 'PDFs to prepare',
                       pdfs['currently']['imported'])
        stat_print('PDFs prepared', pdfs['overall']['prepared'])

        print(' |')
        print(' | Screen')
        if review['overall']['screen'] == 0:
            stat_print('Not initiated', '')
        else:
            stat_print('Screen size', review['overall']['screen'])
            if 0 != review['currently']['needs_screen']:
                stat_print('', '', '*', 'records to screen',
                           review['currently']['needs_screen'])
            stat_print('Included', review['overall']['included'],
                       '->', 'records excluded',
                       review['currently']['screen_excluded'])
            if 'exclusion' in review['currently']:
                for crit, nr in review['currently']['exclusion'].items():
                    stat_print('', '', '->', f'reason: {crit}', nr)

        print(' |')
        print(' | Data and synthesis')
        if review['overall']['synthesis'] == 0:
            stat_print('Not initiated', '')
        else:
            stat_print('Total', review['overall']['synthesis'])
            if 0 != review['currently']['needs_synthesis']:
                stat_print('Synthesized', review['overall']['synthesized'],
                           '*', 'need synthesis',
                           review['currently']['needs_synthesis'])
            else:
                stat_print('Synthesized', review['overall']['synthesized'])
    return


def review_instructions(status_freq=None):
    if status_freq is None:
        stat = get_status_freq()
    metadata, review, pdfs = \
        stat['metadata_status'], stat['review_status'], stat['pdf_status']

    print('\n\nInstructions\n')
    # Note: review_template init is suggested in repository_validation()
    if not os.path.exists(repo_setup.paths['MAIN_REFERENCES']):
        print('  To import, copy search results to the search directory. ' +
              'Then use\n     review_template process')
        return

    if metadata['currently']['non_imported'] > 0:
        print('  To import, use\n     review_template process')
        return

    if metadata['currently']['needs_manual_preparation'] > 0:
        print('  To continue with manual preparation, '
              'use\n     review_template man-prep')
        return

    if metadata['currently']['prepared'] > 0:
        print('  To continue with record preparation, '
              'use\n     review_template process')
        return

    if metadata['currently']['needs_manual_merging'] > 0:
        print('  To continue manual processing of duplicates, '
              'use\n     review_template man-dedupe')
        return

    # TODO: if pre-screening activated in template variables
    if review['currently']['needs_prescreen'] > 0:
        print('  To continue with prescreen, '
              'use\n     review_template prescreen')
        return

    if pdfs['currently']['needs_retrieval'] > 0:
        print('  To continue with pdf retrieval, '
              'use\n     review_template pdfs')
        return

    if pdfs['currently']['needs_manual_retrieval'] > 0:
        print('  To continue with manual pdf retrieval, '
              'use\n     review_template pdf-get-man')
        return

    if pdfs['currently']['imported'] > 0:
        print('  To continue with pdf preparation, '
              'use\n     review_template pdf-prepare')
        return

    # TBD: how/when should we offer that option?
    # if status_freq['non_bw_searched'] > 0:
    #     print('  To execute backward search, '
    #           'use\n     review_template back-search')
        # no return because backward searches are optional

    if review['currently']['needs_screen'] > 0:
        print('  To continue with screen, '
              'use\n     review_template screen')
        return

    # TODO: if data activated in template variables
    if review['currently']['needs_synthesis'] > 0:
        print('  To continue with data extraction/analysis, '
              'use\n     review_template data')
        return

    print('  Iteration completed. To start another review cycle, add '
          'papers to search/ and use\n     review_template process')
    if 'MANUSCRIPT' == repo_setup.config['DATA_FORMAT']:
        print('\n  To build the paper use\n     review_template paper')
    return status_freq


def collaboration_instructions(status_freq):

    print('\n\nVersioning and collaboration\n')

    if repo.is_dirty():
        print(f'  {colors.RED}Uncommitted changes{colors.END}'
              '\n  To add, use\n     git add .'
              '\n  To commit, use\n     git commit -m')
    print('\n  To inspect changes, use\n     gitk')

    print()
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
            non_processed = status_freq['md_non_imported'] + \
                status_freq['md_imported'] + \
                status_freq['md_prepared'] + \
                status_freq['md_needs_manual_preparation'] + \
                status_freq['md_duplicates_removed'] + \
                status_freq['md_needs_manual_merging']
            if len(non_processed) == 0:
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
            non_screened = status_freq['rev_retrieved'] + \
                status_freq['rev_needs_prescreen'] + \
                status_freq['rev_needs_screen']

            if len(non_screened) == 0:
                print(f' Currently:'
                      f' {colors.GREEN}ready for sharing{colors.END}'
                      f' (if consistency checks pass)')
            else:
                print(f' Currently: '
                      f'{colors.RED}not ready for sharing{colors.END}\n'
                      f'  All records should be screened before sharing '
                      '(see instructions above).')

        if SHARE_STAT_REQ == 'COMPLETED':
            non_completed = status_freq['rev_retrieved'] + \
                status_freq['rev_needs_prescreen'] + \
                status_freq['rev_needs_screen'] + \
                status_freq['rev_overall_included']
            if len(non_completed) == 0:
                print(f' Currently: '
                      f'{colors.GREEN}ready for sharing{colors.END}'
                      f' (if consistency checks pass)')
            else:
                print(f' Currently: '
                      f'{colors.RED}not ready for sharing{colors.END}\n'
                      f'  All records should be completed before sharing '
                      '(see instructions above).')

    print('\n')

    return


def main():

    repository_validation()
    repository_load()
    status_freq = review_status()
    review_instructions(status_freq)
    collaboration_instructions(status_freq)

    print('Documentation\n\n   '
          'See https://github.com/geritwagner/review_template/docs\n')

    return
