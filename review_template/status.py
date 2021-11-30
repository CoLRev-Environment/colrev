#! /usr/bin/env python3
import io
import logging
import os

import git
import yaml

from review_template import screen


def get_nr_search(REVIEW_MANAGER) -> int:
    number_search = 0
    for search_file in REVIEW_MANAGER.get_bib_files():
        number_search += REVIEW_MANAGER.get_nr_in_bib(search_file)
    return number_search


def get_completeness_condition(REVIEW_MANAGER) -> bool:
    stat = get_status_freq(REVIEW_MANAGER)
    completeness_condition = True
    if 0 != stat["metadata_status"]["currently"]["retrieved"]:
        completeness_condition = False
    if 0 != stat["metadata_status"]["currently"]["imported"]:
        completeness_condition = False
    if 0 != stat["metadata_status"]["currently"]["prepared"]:
        completeness_condition = False
    if 0 != stat["metadata_status"]["currently"]["needs_manual_preparation"]:
        completeness_condition = False
    if 0 != stat["metadata_status"]["currently"]["needs_manual_merging"]:
        completeness_condition = False
    if 0 != stat["pdf_status"]["currently"]["needs_retrieval"]:
        completeness_condition = False
    if 0 != stat["pdf_status"]["currently"]["needs_manual_retrieval"]:
        completeness_condition = False
    if 0 != stat["pdf_status"]["currently"]["imported"]:
        completeness_condition = False
    if 0 != stat["pdf_status"]["currently"]["needs_manual_preparation"]:
        completeness_condition = False
    if 0 != stat["review_status"]["currently"]["needs_prescreen"]:
        completeness_condition = False
    if 0 != stat["review_status"]["currently"]["needs_screen"]:
        completeness_condition = False
    if 0 != stat["review_status"]["currently"]["needs_synthesis"]:
        completeness_condition = False
    return completeness_condition


def get_status_freq(REVIEW_MANAGER) -> dict:
    MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]

    stat = {}
    stat["metadata_status"] = {}
    stat["metadata_status"]["overall"] = {}
    stat["metadata_status"]["currently"] = {}
    stat["pdf_status"] = {}
    stat["pdf_status"]["overall"] = {}
    stat["pdf_status"]["currently"] = {}
    stat["review_status"] = {}
    stat["review_status"]["overall"] = {}
    stat["review_status"]["currently"] = {}

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
                if " rev_status " in line:
                    if "{retrieved}" in line:
                        rev_retrieved += 1
                    if "{prescreen_included}" in line:
                        rev_prescreen_included += 1
                    if "{prescreen_excluded}" in line:
                        rev_prescreen_excluded += 1
                    if "{included}" in line:
                        rev_screen_included += 1
                    if "{excluded}" in line:
                        rev_screen_excluded += 1
                    if "{synthesized}" in line:
                        rev_synthesized += 1
                if " md_status " in line:
                    if "{imported}" in line:
                        md_imported += 1
                    if "{needs_manual_preparation}" in line:
                        md_needs_manual_preparation += 1
                    if "{prepared}" in line:
                        md_prepared += 1
                    if "{needs_manual_merging}" in line:
                        md_needs_manual_merging += 1
                    if "{processed}" in line:
                        md_processed += 1
                if " pdf_status " in line:
                    if "{needs_retrieval}" in line:
                        pdfs_needs_retrieval += 1
                    if "{imported}" in line:
                        pdfs_imported += 1
                    if "{needs_manual_retrieval}" in line:
                        pdfs_needs_manual_retrieval += 1
                    if "{needs_manual_preparation}" in line:
                        pdfs_needs_manual_preparation += 1
                    if "{prepared}" in line:
                        pdfs_prepared += 1
                    if "{not_available}" in line:
                        pdfs_not_available += 1
                if "origin" == line.lstrip()[:6]:
                    nr_record_links = line.count(";")
                    record_links += nr_record_links + 1
                    md_duplicates_removed += nr_record_links
                if " excl_criteria " in line:
                    excl_criteria_field = line[line.find("{") + 1 : line.find("}")]
                    excl_criteria.append(excl_criteria_field)
                line = f.readline()

    exclusion_statistics = {}
    if excl_criteria:
        criteria = screen.get_excl_criteria(excl_criteria[0])
        exclusion_statistics = {crit: 0 for crit in criteria}
        for exclusion_case in excl_criteria:
            for crit in criteria:
                if crit + "=yes" in exclusion_case:
                    exclusion_statistics[crit] += 1

    # Reverse order (overall_x means x or later status)
    md_overall_processed = md_processed
    md_overall_prepared = (
        md_overall_processed
        + md_needs_manual_merging
        + md_duplicates_removed
        + md_prepared
    )
    md_overall_imported = (
        md_overall_prepared + md_needs_manual_preparation + md_imported
    )
    md_overall_retrieved = get_nr_search(REVIEW_MANAGER)

    md_retrieved = md_overall_retrieved - record_links

    # Reverse order (overall_x means x or later status)
    pdfs_overall_prepared = pdfs_prepared
    pdfs_overall_retrieved = (
        pdfs_overall_prepared + pdfs_needs_manual_preparation + pdfs_imported
    )
    pdfs_overall_needs_retrieval = (
        pdfs_overall_retrieved
        + pdfs_needs_retrieval
        + pdfs_not_available
        + pdfs_needs_manual_retrieval
    )

    # Reverse order (overall_x means x or later status)
    # rev_overall_synthesized = rev_synthesized
    rev_overall_included = rev_screen_included + rev_synthesized
    rev_overall_excluded = rev_screen_excluded
    rev_overall_prescreen_included = (
        rev_prescreen_included + rev_overall_excluded + rev_overall_included
    )
    rev_overall_screen = rev_overall_prescreen_included
    rev_overall_prescreen = md_processed

    rev_needs_prescreen = (
        rev_overall_prescreen - rev_overall_prescreen_included - rev_prescreen_excluded
    )
    rev_needs_screen = rev_overall_screen - rev_overall_included - rev_screen_excluded
    rev_overall_synthesis = rev_overall_included
    rev_needs_synthesis = rev_overall_included - rev_synthesized

    # PDF_DIRECTORY = REVIEW_MANAGER.paths['PDF_DIRECTORY']
    # if os.path.exists(PDF_DIRECTORY):
    #     pdf_files = [x for x in os.listdir(PDF_DIRECTORY)]
    #     search_files = [x for x in os.listdir('search/') if '.bib' == x[-4:]]
    #     non_bw_searched = len([x for x in pdf_files
    #                            if not x.replace('.pdf', 'bw_search.bib')
    #                            in search_files])

    md_cur_stat = stat["metadata_status"]["currently"]
    md_cur_stat["retrieved"] = md_retrieved
    md_cur_stat["imported"] = md_imported
    md_cur_stat["prepared"] = md_prepared
    md_cur_stat["needs_manual_preparation"] = md_needs_manual_preparation
    md_cur_stat["needs_manual_merging"] = md_needs_manual_merging
    md_cur_stat["processed"] = md_processed
    md_cur_stat["duplicates_removed"] = md_duplicates_removed
    md_cur_stat["non_processed"] = (
        md_retrieved
        + md_imported
        + md_prepared
        + md_needs_manual_preparation
        + md_duplicates_removed
        + md_needs_manual_merging
    )

    md_overall_stat = stat["metadata_status"]["overall"]
    md_overall_stat["retrieved"] = md_overall_retrieved
    md_overall_stat["imported"] = md_overall_imported
    md_overall_stat["prepared"] = md_overall_prepared
    md_overall_stat["processed"] = md_overall_processed

    pdf_cur_stat = stat["pdf_status"]["currently"]
    pdf_cur_stat["needs_retrieval"] = pdfs_needs_retrieval
    pdf_cur_stat["imported"] = pdfs_imported
    pdf_cur_stat["needs_manual_retrieval"] = pdfs_needs_manual_retrieval
    pdf_cur_stat["needs_manual_preparation"] = pdfs_needs_manual_preparation
    pdf_cur_stat["not_available"] = pdfs_not_available
    pdf_cur_stat["prepared"] = pdfs_prepared

    pdf_overall_stat = stat["pdf_status"]["overall"]
    pdf_overall_stat["needs_retrieval"] = pdfs_overall_needs_retrieval
    pdf_overall_stat["retrieved"] = pdfs_overall_retrieved
    pdf_overall_stat["prepared"] = pdfs_overall_prepared

    rev_cur_stat = stat["review_status"]["currently"]
    rev_cur_stat["retrieved"] = rev_retrieved
    rev_cur_stat["prescreen_included"] = rev_prescreen_included
    rev_cur_stat["prescreen_excluded"] = rev_prescreen_excluded
    rev_cur_stat["screen_included"] = rev_screen_included
    rev_cur_stat["screen_excluded"] = rev_screen_excluded
    rev_cur_stat["non_screened"] = (
        rev_retrieved + rev_needs_prescreen + rev_needs_screen
    )
    rev_cur_stat["synthesized"] = rev_synthesized
    rev_cur_stat["needs_prescreen"] = rev_needs_prescreen
    rev_cur_stat["needs_screen"] = rev_needs_screen
    rev_cur_stat["needs_synthesis"] = rev_needs_synthesis

    stat["review_status"]["currently"]["exclusion"] = exclusion_statistics

    rev_overall_stat = stat["review_status"]["overall"]
    rev_overall_stat["prescreen"] = rev_overall_prescreen
    rev_overall_stat["prescreen_included"] = rev_overall_prescreen_included
    rev_overall_stat["screen"] = rev_overall_screen
    rev_overall_stat["included"] = rev_overall_included
    rev_overall_stat["synthesized"] = rev_synthesized
    rev_overall_stat["synthesis"] = rev_overall_synthesis
    rev_overall_stat["non_completed"] = (
        rev_retrieved + rev_needs_prescreen + rev_needs_screen + rev_overall_included
    )

    # Note: prepare, dedupe, prescreen, pdfs, pdf_prepare, screen, data
    nr_steps = 7
    total_atomic_steps = nr_steps * stat["metadata_status"]["overall"]["retrieved"]
    # Remove record steps no longer required
    # (multiplied by number of following steps no longer required)
    total_atomic_steps = (
        total_atomic_steps
        - 5 * stat["metadata_status"]["currently"]["duplicates_removed"]
    )
    total_atomic_steps = (
        total_atomic_steps
        - 4 * stat["review_status"]["currently"]["prescreen_excluded"]
    )
    total_atomic_steps = (
        total_atomic_steps - 2 * stat["pdf_status"]["currently"]["not_available"]
    )
    total_atomic_steps = (
        total_atomic_steps - 1 * stat["review_status"]["currently"]["screen_excluded"]
    )
    rev_overall_stat["atomic_steps"] = total_atomic_steps

    completed_steps = (
        7 * stat["review_status"]["overall"]["synthesized"]
        + 6 * stat["review_status"]["overall"]["screen"]
        + 5 * stat["pdf_status"]["overall"]["prepared"]
        + 4 * stat["pdf_status"]["overall"]["retrieved"]
        + 3 * stat["review_status"]["overall"]["prescreen"]
        + 2 * stat["metadata_status"]["overall"]["processed"]
        + 1 * stat["metadata_status"]["overall"]["prepared"]
    )
    rev_cur_stat["completed_atomic_steps"] = completed_steps

    return stat


def is_git_repo(path: str) -> bool:
    try:
        _ = git.Repo(path).git_dir
        return True
    except git.exc.InvalidGitRepositoryError:
        return False


def is_review_template_project() -> bool:
    # Note : 'private_config.ini', 'shared_config.ini' are optional
    required_paths = ["search", ".pre-commit-config.yaml", ".gitignore"]
    if not all(os.path.exists(x) for x in required_paths):
        return False
    return True


def get_installed_hooks() -> dict:
    installed_hooks = {}
    with open(".pre-commit-config.yaml") as pre_commit_y:
        pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.FullLoader)
    installed_hooks[
        "remote_pv_hooks_repo"
    ] = "https://github.com/geritwagner/pipeline-validation-hooks"
    for repository in pre_commit_config["repos"]:
        if repository["repo"] == installed_hooks["remote_pv_hooks_repo"]:
            installed_hooks["local_hooks_version"] = repository["rev"]
            installed_hooks["hooks"] = [hook["id"] for hook in repository["hooks"]]
    return installed_hooks


def lsremote(url: str) -> str:
    remote_refs = {}
    g = git.cmd.Git()
    for ref in g.ls_remote(url).split("\n"):
        hash_ref_list = ref.split("\t")
        remote_refs[hash_ref_list[1]] = hash_ref_list[0]
    return remote_refs


def hooks_up_to_date(installed_hooks: dict) -> bool:
    refs = lsremote(installed_hooks["remote_pv_hooks_repo"])
    remote_sha = refs["HEAD"]
    if remote_sha == installed_hooks["local_hooks_version"]:
        return True
    return False


def required_hooks_installed(installed_hooks: dict) -> bool:
    return installed_hooks["hooks"] == ["check", "format"]


def repository_validation() -> dict:
    global repo

    repo_report = {}

    # 1. git repository?
    if not is_git_repo(os.getcwd()):
        repo_report["msg"] = "No git repository. Use review_template init"
        repo_report["level"] = "ERROR"
        return repo_report
    repo = git.Repo("")

    # 2. review_template project?
    if not is_review_template_project():
        repo_report["msg"] = (
            "No review_template repository"
            + "\n  To retrieve a shared repository, use review_template init."
            + "\n  To initalize a new repository, execute the "
            + "command in an empty directory.\nExit."
        )
        repo_report["level"] = "ERROR"
        return repo_report

    # 3. Pre-commit hooks installed?
    installed_hooks = get_installed_hooks()
    if not required_hooks_installed(installed_hooks):
        repo_report["msg"] = (
            "Pre-commit hooks not installed. See"
            + " https://github.com/geritwagner/pipeline-validation-hooks for details"
        )
        repo_report["level"] = "ERROR"
        return repo_report

    # 4. Pre-commit hooks up-to-date?
    try:
        if not hooks_up_to_date(installed_hooks):
            repo_report["msg"] = (
                "Pre-commit hooks not up-to-date. "
                + "Use pre-commit autoupdate (--bleeding-edge)"
            )
            repo_report["level"] = "WARNING"

    except git.exc.GitCommandError as e:
        repo_report["msg"] = (
            "No Internet connection, cannot check remote "
            "pipeline-validation-hooks repository for updates."
        )
        repo_report["level"] = "WARNING"
        logging.error(e)
        pass

    return repo_report


def get_priority_transition(current_states: set, active_processing_functions: list):
    from review_template.review_manager import Record

    # get "earliest" states (going backward)
    earliest_state = []
    search_states = ["rev_synthesized"]
    while True:
        if any(search_state in list(current_states) for search_state in search_states):
            earliest_state = [
                search_state
                for search_state in search_states
                if search_state in current_states
            ]
        search_states = [
            x["source"] for x in Record.transitions if x["dest"] in search_states
        ]
        if [] == search_states:
            break
    # print(f'earliest_state: {earliest_state}')

    # next: get the priority transition for the earliest states
    priority_transitions = [
        x for x in Record.transitions if x["source"] in earliest_state
    ]
    # print(f'priority_transitions (before following "automatically"):"
    #   f" {priority_transitions}')
    for priority_transition in priority_transitions:
        if "automatically" == priority_transition["trigger"]:
            priority_transitions.extend(
                [
                    x
                    for x in Record.transitions
                    if x["source"] == priority_transition["dest"]
                ]
            )
    priority_transitions = [
        x for x in priority_transitions if "automatically" != x["trigger"]
    ]
    # print(f'priority_transitions: {priority_transitions}')
    return priority_transitions


def get_active_processing_functions(current_states_set):
    from review_template.review_manager import Record

    active_processing_functions = []
    for state in current_states_set:
        srec = Record("item", state)
        t = srec.get_valid_transitions()
        if "automatically" in t:
            srec = Record(
                "item",
                [x["dest"] for x in Record.transitions if state == x["source"]][0],
            )
            t = srec.get_valid_transitions()
        active_processing_functions.extend(t)
    return active_processing_functions


def get_remote_commit_differences(repo: git.Repo) -> list:
    nr_commits_behind, nr_commits_ahead = -1, -1

    origin = repo.remotes.origin
    if origin.exists():
        origin.fetch()

    if repo.active_branch.tracking_branch() is not None:

        branch_name = str(repo.active_branch)
        tracking_branch_name = str(repo.active_branch.tracking_branch())
        logging.debug(f"{branch_name} - {tracking_branch_name}")

        behind_operation = branch_name + ".." + tracking_branch_name
        commits_behind = repo.iter_commits(behind_operation)
        nr_commits_behind = sum(1 for c in commits_behind)

        ahead_operation = tracking_branch_name + ".." + branch_name
        commits_ahead = repo.iter_commits(ahead_operation)
        nr_commits_ahead = sum(1 for c in commits_ahead)

    return nr_commits_behind, nr_commits_ahead


def get_instructions(REVIEW_MANAGER, stat: dict) -> dict:

    review_instructions = []

    git_repo = git.Repo()
    MAIN_REFERENCES = REVIEW_MANAGER.paths["MAIN_REFERENCES"]

    non_staged = [
        item.a_path for item in git_repo.index.diff(None) if ".bib" == item.a_path[-4:]
    ]

    if len(non_staged) > 0:
        instruction = {
            "msg": "Add non-staged changes.",
            "cmd": f"git add {', '.join(non_staged)}",
        }
        if REVIEW_MANAGER.paths["MAIN_REFERENCES"] in non_staged:
            instruction["priority"] = "yes"
        review_instructions.append(instruction)

    current_record_state_list = REVIEW_MANAGER.get_record_state_list()
    current_states_set = REVIEW_MANAGER.get_states_set(current_record_state_list)
    # temporarily override for testing
    # current_states_set = {'pdf_imported', 'pdf_needs_retrieval'}
    # from review_template.review_manager import Record
    # current_states_set = set([x['source'] for x in Record.transitions])

    MAIN_REFS_CHANGED = MAIN_REFERENCES in [
        item.a_path for item in git_repo.index.diff(None)
    ] + [x.a_path for x in git_repo.head.commit.diff()]

    # If changes in MAIN_REFERENCES are staged, we need to detect the process type
    if MAIN_REFS_CHANGED:
        from review_template.review_manager import Record

        revlist = (
            (commit.hexsha, (commit.tree / MAIN_REFERENCES).data_stream.read())
            for commit in git_repo.iter_commits(paths=MAIN_REFERENCES)
        )
        filecontents = list(revlist)[0][1]
        committed_record_states_list = (
            REVIEW_MANAGER.get_record_state_list_from_file_obj(
                io.StringIO(filecontents.decode("utf-8"))
            )
        )

        items = [
            record_state
            for record_state in current_record_state_list
            if record_state not in committed_record_states_list
        ]
        transitioned_records = []
        for item in items:
            transitioned_record = {"ID": item[0], "dest": item[1]}

            source_state = [
                rec[1] for rec in committed_record_states_list if rec[0] == item[0]
            ]
            if len(source_state) != 1:
                print(f"Error (no source_state): {transitioned_record}")
                review_instructions.append(
                    {
                        "msg": f"Resolve commited status of {transitioned_record}",
                        "priority": "yes",
                    }
                )
                continue
            transitioned_record["source"] = source_state[0]

            process_type = [
                x["trigger"]
                for x in Record.transitions
                if x["source"] == transitioned_record["source"]
                and x["dest"] == transitioned_record["dest"]
            ]
            if len(process_type) == 0:
                review_instructions.append(
                    {
                        "msg": "Resolve invalid transition of "
                        + f"{transitioned_record['ID']} from "
                        + f"{transitioned_record['source']} to "
                        + " {transitioned_record['dest']}",
                        "priority": "yes",
                    }
                )
                continue
            transitioned_record["process_type"] = process_type[0]
            transitioned_records.append(transitioned_record)

        in_progress_processes = list({x["process_type"] for x in transitioned_records})
        if len(in_progress_processes) == 1:
            instruction = {
                "msg": f"Detected {in_progress_processes[0]} in progress. "
                + "Complete this process",
                "cmd": f"review_template {in_progress_processes[0]}",
            }
            instruction["priority"] = "yes"
            review_instructions.append(instruction)
        elif len(in_progress_processes) > 1:
            instruction = {
                "msg": "Detected multiple processes in progress "
                + f"({', '.join(in_progress_processes)}). Complete one "
                + "(save and revert the other) and commit before continuing!\n"
                + f"  Records: {', '.join([x['ID'] for x in transitioned_records])}",
                # "cmd": f"review_template {in_progress_processes}",
            }
            instruction["priority"] = "yes"
            review_instructions.append(instruction)

    logging.debug(f"current_states_set: {current_states_set}")
    active_processing_functions = get_active_processing_functions(current_states_set)
    logging.debug(f"active_processing_functions: {active_processing_functions}")
    priority_processing_functions = get_priority_transition(
        current_states_set, active_processing_functions
    )
    logging.debug(f"priority_processing_function: {priority_processing_functions}")

    msgs = {
        "load": "Import search results",
        "prepare": "Prepare records",
        "man_prep": "Prepare records (manually)",
        "dedupe": "Deduplicate records",
        "man_dedupe": "Deduplicate records (manually)",
        "prescreen": "Prescreen records",
        "pdf_get": "Retrieve pdfs",
        "pdf_get_man": "Retrieve pdfs (manually)",
        "pdf_prep": "Prepare pdfs",
        "pdf_prep_man": "Prepare pdfs (manually)",
        "screen": "Screen records",
        "data": "Extract data/synthesize records",
    }

    for active_processing_function in active_processing_functions:
        instruction = {
            "msg": msgs[active_processing_function],
            "cmd": f"review_template {active_processing_function}"
            # "high_level_cmd": "review_template metadata",
        }
        if active_processing_function in [
            x["trigger"] for x in priority_processing_functions
        ]:
            keylist = [list(x.keys()) for x in review_instructions]
            keys = [item for sublist in keylist for item in sublist]
            if "priority" not in keys:
                instruction["priority"] = "yes"
        else:
            if REVIEW_MANAGER.config["DELAY_AUTOMATED_PROCESSING"]:
                continue

        review_instructions.append(instruction)

    if not os.path.exists(REVIEW_MANAGER.paths["MAIN_REFERENCES"]):
        instruction = {
            "msg": "To import, copy search results to the search directory.",
            "cmd": "review_template load",
        }
        review_instructions.append(instruction)

    if get_completeness_condition(REVIEW_MANAGER):
        instruction = {
            "info": "Iterationed completed.",
            "msg": "To start the next iteration of the review, "
            + "add records to search/ directory",
            "cmd_after": "review_template load",
        }
        review_instructions.append(instruction)

    if "MANUSCRIPT" == REVIEW_MANAGER.config["DATA_FORMAT"]:
        instruction = {
            "msg": "Build the paper",
            "cmd": "review_template paper",
        }
        review_instructions.append(instruction)

    collaboration_instructions = {"items": []}

    found_a_conflict = False
    unmerged_blobs = repo.index.unmerged_blobs()
    for path in unmerged_blobs:
        list_of_blobs = unmerged_blobs[path]
        for (stage, blob) in list_of_blobs:
            if stage != 0:
                found_a_conflict = True

    nr_commits_behind, nr_commits_ahead = 0, 0

    SHARE_STAT_REQ = REVIEW_MANAGER.config["SHARE_STAT_REQ"]
    CONNECTED_REMOTE = 0 != len(repo.remotes)
    if CONNECTED_REMOTE:
        origin = repo.remotes.origin
        if origin.exists():
            nr_commits_behind, nr_commits_ahead = get_remote_commit_differences(repo)
    if CONNECTED_REMOTE:
        collaboration_instructions["title"] = "Versioning and collaboration"
        collaboration_instructions["SHARE_STAT_REQ"] = SHARE_STAT_REQ
    else:
        collaboration_instructions[
            "title"
        ] = "Versioning (not connected to shared repository)"

    if found_a_conflict:
        item = {
            "title": "Git merge conflict detected",
            "level": "WARNING",
            "msg": "To resolve:\n  1 https://docs.github.com/en/"
            + "pull-requests/collaborating-with-pull-requests/"
            + "addressing-merge-conflicts/resolving-a-merge-conflict-"
            + "using-the-command-line",
        }
        collaboration_instructions["items"].append(item)

    # Notify when changes in bib files are not staged
    # (this may raise unexpected errors)

    if len(non_staged) > 0:
        item = {
            "title": f"Non-staged files: {','.join(non_staged)}",
            "level": "WARNING",
        }
        collaboration_instructions["items"].append(item)

    # if not found_a_conflict and repo.is_dirty():
    #     item = {
    #         "title": "Uncommitted changes",
    #         "level": "WARNING",
    #     }
    #     collaboration_instructions["items"].append(item)

    elif not found_a_conflict:
        if CONNECTED_REMOTE:
            if nr_commits_behind > 0:
                item = {
                    "title": "Remote changes available on the server",
                    "msg": "Once you have committed your changes, get the latest "
                    + "remote changes",
                    "cmd_after": "git add FILENAME \n git commit -m 'MSG' \n "
                    + "git pull --rebase",
                }
                collaboration_instructions["items"].append(item)

            if nr_commits_ahead > 0:
                # TODO: suggest detailed commands
                # (depending on the working directory/index)
                item = {
                    "title": "Local changes not yet on the server",
                    "msg": "Once you have committed your changes, upload them "
                    + "to the shared repository.",
                    "cmd_after": "git push",
                }
                collaboration_instructions["items"].append(item)

            if SHARE_STAT_REQ == "NONE":
                collaboration_instructions["status"] = {
                    "title": "Sharing: currently ready for sharing",
                    "level": "SUCCESS",
                    "msg": "",
                    # If consistency checks pass -
                    # if they didn't pass, the message wouldn't be displayed
                }

            # TODO all the following: should all search results be imported?!
            if SHARE_STAT_REQ == "PROCESSED":
                if 0 == stat["metadata_status"]["currently"]["non_processed"]:
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently ready for sharing",
                        "level": "SUCCESS",
                        "msg": "",
                        # If consistency checks pass -
                        # if they didn't pass, the message wouldn't be displayed
                    }

                else:
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently not ready for sharing",
                        "level": "WARNING",
                        "msg": "All records should be processed before sharing "
                        + "(see instructions above).",
                    }

            # Note: if we use all(...) in the following,
            # we do not need to distinguish whether
            # a PRE_SCREEN or INCLUSION_SCREEN is needed
            if SHARE_STAT_REQ == "SCREENED":
                if 0 == stat["review_status"]["currently"]["non_screened"]:
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently ready for sharing",
                        "level": "SUCCESS",
                        "msg": "",
                        # If consistency checks pass -
                        # if they didn't pass, the message wouldn't be displayed
                    }

                else:
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently not ready for sharing",
                        "level": "WARNING",
                        "msg": "All records should be screened before sharing "
                        + "(see instructions above).",
                    }

            if SHARE_STAT_REQ == "COMPLETED":
                if 0 == stat["review_status"]["currently"]["non_completed"]:
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently ready for sharing",
                        "level": "SUCCESS",
                        "msg": "",
                        # If consistency checks pass -
                        # if they didn't pass, the message wouldn't be displayed
                    }
                else:
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently not ready for sharing",
                        "level": "WARNING",
                        "msg": "All records should be completed before sharing "
                        + "(see instructions above).",
                    }

    else:
        if CONNECTED_REMOTE:
            collaboration_instructions["status"] = {
                "title": "Sharing: currently not ready for sharing",
                "level": "WARNING",
                "msg": "Merge conflicts need to be resolved first.",
            }

    if 0 == len(collaboration_instructions["items"]):
        item = {
            "title": "Up-to-date",
            "level": "SUCCESS",
            "msg": "No versioning/collaboration tasks required at the moment.",
        }
        collaboration_instructions["items"].append(item)

    instructions = {
        "review_instructions": review_instructions,
        "collaboration_instructions": collaboration_instructions,
    }
    return instructions


def stat_print(
    separate_category: bool,
    field1: str,
    val1: str,
    connector: str = None,
    field2: str = None,
    val2: str = None,
) -> None:
    if field2 is None:
        field2 = ""
    if val2 is None:
        val2 = ""
    if field1 != "":
        if separate_category:
            stat = "     |  - " + field1
        else:
            stat = " |  - " + field1
    else:
        if separate_category:
            stat = "     | "
        else:
            stat = " | "
    rjust_padd = 37 - len(stat)
    stat = stat + str(val1).rjust(rjust_padd, " ")
    if connector is not None:
        stat = stat + "  " + connector + "  "
    if val2 != "":
        rjust_padd = 47 - len(stat)
        stat = stat + str(val2).rjust(rjust_padd, " ") + " "
    if field2 != "":
        stat = stat + str(field2)
    print(stat)
    return


def print_review_status(REVIEW_MANAGER, stat: dict) -> None:

    # Principle: first column shows total records/PDFs in each stage
    # the second column shows
    # (blank call)  * the number of records requiring manual action
    #               -> the number of records excluded/merged

    print("\nStatus\n")

    if not os.path.exists(REVIEW_MANAGER.paths["MAIN_REFERENCES"]):
        print(" | Search")
        print(" |  - No records added yet")
    else:
        metadata, review, pdfs = (
            stat["metadata_status"],
            stat["review_status"],
            stat["pdf_status"],
        )

        print(" | Search")
        stat_print(False, "Records retrieved", metadata["overall"]["retrieved"])
        print(" |")
        print("     | Metadata preparation")
        if metadata["currently"]["retrieved"] > 0:
            stat_print(
                True,
                "",
                "",
                "*",
                "record(s) not yet imported",
                metadata["currently"]["retrieved"],
            )
        stat_print(True, "Records imported", metadata["overall"]["imported"])
        if metadata["currently"]["imported"] > 0:
            stat_print(
                True,
                "",
                "",
                "*",
                "record(s) need preparation",
                metadata["currently"]["imported"],
            )
        if metadata["currently"]["needs_manual_preparation"] > 0:
            stat_print(
                True,
                "",
                "",
                "*",
                "record(s) need manual preparation",
                metadata["currently"]["needs_manual_preparation"],
            )
        stat_print(True, "Records prepared", metadata["overall"]["prepared"])
        if metadata["currently"]["prepared"] > 0:
            stat_print(
                True,
                "",
                "",
                "*",
                "record(s) need merging",
                metadata["currently"]["prepared"],
            )
        if metadata["currently"]["needs_manual_merging"] > 0:
            stat_print(
                True,
                "",
                "",
                "*",
                "record(s) need manual merging",
                metadata["currently"]["needs_manual_merging"],
            )
        stat_print(
            True,
            "Records processed",
            metadata["overall"]["processed"],
            "->",
            "duplicates removed",
            metadata["currently"]["duplicates_removed"],
        )

        print(" |")
        print(" | Prescreen")
        if review["overall"]["prescreen"] == 0:
            stat_print(False, "Not initiated", "")
        else:
            stat_print(False, "Prescreen size", review["overall"]["prescreen"])
            if 0 != review["currently"]["needs_prescreen"]:
                stat_print(
                    False,
                    "",
                    "",
                    "*",
                    "records to prescreen",
                    review["currently"]["needs_prescreen"],
                )
            stat_print(
                False,
                "Included",
                review["overall"]["prescreen_included"],
                "->",
                "records excluded",
                review["currently"]["prescreen_excluded"],
            )

        print(" |")
        print("     | PDF preparation")
        stat_print(True, "PDFs to retrieve", pdfs["overall"]["needs_retrieval"])
        if 0 != pdfs["currently"]["needs_retrieval"]:
            stat_print(
                True,
                "",
                "",
                "*",
                "PDFs to retrieve",
                pdfs["currently"]["needs_retrieval"],
            )
        if 0 != pdfs["currently"]["needs_manual_retrieval"]:
            stat_print(
                True,
                "",
                "",
                "*",
                "PDFs to retrieve manually",
                pdfs["currently"]["needs_manual_retrieval"],
            )
        if pdfs["currently"]["not_available"] > 0:
            stat_print(
                True,
                "PDFs retrieved",
                pdfs["overall"]["retrieved"],
                "*",
                "PDFs not available",
                pdfs["currently"]["not_available"],
            )
        else:
            stat_print(True, "PDFs retrieved", pdfs["overall"]["retrieved"])
        if pdfs["currently"]["needs_manual_preparation"] > 0:
            stat_print(
                True,
                "",
                "",
                "*",
                "PDFs need manual preparation",
                pdfs["currently"]["needs_manual_preparation"],
            )
        if 0 != pdfs["currently"]["imported"]:
            stat_print(
                True, "", "", "*", "PDFs to prepare", pdfs["currently"]["imported"]
            )
        stat_print(True, "PDFs prepared", pdfs["overall"]["prepared"])

        print(" |")
        print(" | Screen")
        if review["overall"]["screen"] == 0:
            stat_print(False, "Not initiated", "")
        else:
            stat_print(False, "Screen size", review["overall"]["screen"])
            if 0 != review["currently"]["needs_screen"]:
                stat_print(
                    False,
                    "",
                    "",
                    "*",
                    "records to screen",
                    review["currently"]["needs_screen"],
                )
            stat_print(
                False,
                "Included",
                review["overall"]["included"],
                "->",
                "records excluded",
                review["currently"]["screen_excluded"],
            )
            if "exclusion" in review["currently"]:
                for crit, nr in review["currently"]["exclusion"].items():
                    stat_print(False, "", "", "->", f"reason: {crit}", nr)

        print(" |")
        print(" | Data and synthesis")
        if review["overall"]["synthesis"] == 0:
            stat_print(False, "Not initiated", "")
        else:
            stat_print(False, "Total", review["overall"]["synthesis"])
            if 0 != review["currently"]["needs_synthesis"]:
                stat_print(
                    False,
                    "Synthesized",
                    review["overall"]["synthesized"],
                    "*",
                    "need synthesis",
                    review["currently"]["needs_synthesis"],
                )
            else:
                stat_print(False, "Synthesized", review["overall"]["synthesized"])

    return
