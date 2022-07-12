#! /usr/bin/env python3
import io
import multiprocessing
import typing
from collections import Counter
from pathlib import Path

import git
from git.exc import InvalidGitRepositoryError
from git.exc import NoSuchPathError

from colrev_core.process import Process
from colrev_core.process import ProcessType
from colrev_core.review_manager import ReviewManager


class Status(Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER=REVIEW_MANAGER, type=ProcessType.explore)

    def __get_nr_in_bib(self, file_path: Path) -> int:

        number_in_bib = 0
        with open(file_path, encoding="utf8") as f:
            line = f.readline()
            while line:
                # Note: the '﻿' occured in some bibtex files
                # (e.g., Publish or Perish exports)
                if "@" in line[:3]:
                    if "@comment" not in line[:10].lower():
                        number_in_bib += 1
                line = f.readline()
        return number_in_bib

    def get_nr_search(self) -> int:

        search_dir = self.REVIEW_MANAGER.paths["SEARCHDIR"]
        if not search_dir.is_dir():
            return 0
        bib_files = search_dir.glob("*.bib")
        number_search = 0
        for search_file in bib_files:
            number_search += self.__get_nr_in_bib(search_file)
        return number_search

    def get_completeness_condition(self) -> bool:
        stat = self.get_status_freq()
        return stat["completeness_condition"]

    def get_exclusion_criteria(self, *, ec_string: str) -> list:
        return [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]

    def get_status_freq(self) -> dict:
        from colrev_core.record import RecordState
        from colrev_core.process import ProcessModel

        record_header_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()

        status_list = [x["colrev_status"] for x in record_header_list]
        exclusion_criteria = [
            x["exclusion_criteria"]
            for x in record_header_list
            if x["exclusion_criteria"] != ""
        ]
        md_duplicates_removed = sum(
            (x["colrev_origin"].count(";")) for x in record_header_list
        )

        origin_list = [x["colrev_origin"] for x in record_header_list]
        record_links = 0
        for origin in origin_list:
            nr_record_links = origin.count(";")
            record_links += nr_record_links + 1

        stat: dict = {"colrev_status": {}}

        exclusion_statistics = {}
        if exclusion_criteria:
            criteria = self.get_exclusion_criteria(ec_string=exclusion_criteria[0])
            exclusion_statistics = {crit: 0 for crit in criteria}
            for exclusion_case in exclusion_criteria:
                for crit in criteria:
                    if crit + "=yes" in exclusion_case:
                        exclusion_statistics[crit] += 1

        stat["colrev_status"]["currently"] = {str(rs): 0 for rs in list(RecordState)}
        stat["colrev_status"]["overall"] = {str(rs): 0 for rs in list(RecordState)}

        currently_stats = dict(Counter(status_list))
        for currently_stat, val in currently_stats.items():
            stat["colrev_status"]["currently"][currently_stat] = val
            stat["colrev_status"]["overall"][currently_stat] = val

        atomic_step_number = 0
        completed_atomic_steps = 0

        self.REVIEW_MANAGER.logger.debug(
            "Set overall colrev_status statistics (going backwards)"
        )
        st_o = stat["colrev_status"]["overall"]
        non_completed = 0
        current_state = RecordState.rev_synthesized  # start with the last
        visited_states = []
        nr_incomplete = 0
        while True:
            self.REVIEW_MANAGER.logger.debug(
                f"current_state: {current_state} with {st_o[str(current_state)]}"
            )
            if RecordState.md_prepared == current_state:
                st_o[str(current_state)] += md_duplicates_removed

            states_to_consider = [current_state]
            predecessors: typing.List[typing.Dict[str, typing.Any]] = [
                {
                    "trigger": "init",
                    "source": RecordState.md_imported,
                    "dest": RecordState.md_imported,
                }
            ]
            # Go backward through the process model
            while predecessors:
                predecessors = [
                    t
                    for t in ProcessModel.transitions
                    if t["source"] in states_to_consider
                    and t["dest"] not in visited_states
                ]
                for predecessor in predecessors:
                    self.REVIEW_MANAGER.logger.debug(
                        f' add {st_o[str(predecessor["dest"])]} '
                        f'from {str(predecessor["dest"])} '
                        f'(predecessor transition: {predecessor["trigger"]})'
                    )
                    st_o[str(current_state)] = (
                        st_o[str(current_state)] + st_o[str(predecessor["dest"])]
                    )
                    visited_states.append(predecessor["dest"])
                    if predecessor["dest"] not in states_to_consider:
                        states_to_consider.append(predecessor["dest"])
                if len(predecessors) > 0:
                    if predecessors[0]["trigger"] != "init":
                        completed_atomic_steps += st_o[str(predecessor["dest"])]
            atomic_step_number += 1
            # Note : the following does not consider multiple parallel steps.
            for trans_for_completeness in [
                t for t in ProcessModel.transitions if current_state == t["dest"]
            ]:
                nr_incomplete += stat["colrev_status"]["currently"][
                    str(trans_for_completeness["source"])
                ]

            t_list = [t for t in ProcessModel.transitions if current_state == t["dest"]]
            t: dict = t_list.pop()
            if current_state == RecordState.md_imported:
                break
            current_state = t["source"]  # go a step back
            non_completed += stat["colrev_status"]["currently"][str(current_state)]

        stat["colrev_status"]["currently"]["non_completed"] = non_completed

        stat["colrev_status"]["currently"]["non_processed"] = (
            stat["colrev_status"]["currently"]["md_imported"]
            + stat["colrev_status"]["currently"]["md_retrieved"]
            + stat["colrev_status"]["currently"]["md_needs_manual_preparation"]
            + stat["colrev_status"]["currently"]["md_prepared"]
        )

        stat["colrev_status"]["currently"][
            "md_duplicates_removed"
        ] = md_duplicates_removed
        stat["colrev_status"]["overall"]["md_retrieved"] = self.get_nr_search()
        stat["colrev_status"]["currently"]["md_retrieved"] = (
            stat["colrev_status"]["overall"]["md_retrieved"] - record_links
        )
        stat["completeness_condition"] = (0 == nr_incomplete) and (
            0 == stat["colrev_status"]["currently"]["md_retrieved"]
        )

        stat["colrev_status"]["currently"]["exclusion"] = exclusion_statistics

        stat["colrev_status"]["overall"]["rev_screen"] = stat["colrev_status"][
            "overall"
        ]["pdf_prepared"]
        stat["colrev_status"]["overall"]["rev_prescreen"] = stat["colrev_status"][
            "overall"
        ]["md_processed"]
        stat["colrev_status"]["currently"]["pdf_needs_retrieval"] = stat[
            "colrev_status"
        ]["currently"]["rev_prescreen_included"]

        colrev_masterdata_items = [
            x["colrev_masterdata_provenance"] for x in record_header_list
        ]
        stat["colrev_status"]["CURATED_records"] = len(
            [x for x in colrev_masterdata_items if "CURATED" in x]
        )
        # Note : 'title' in curated_fields: simple heuristic for masterdata curation
        if self.REVIEW_MANAGER.settings.project.curated_masterdata:
            stat["colrev_status"]["CURATED_records"] = stat["colrev_status"]["overall"][
                "md_processed"
            ]

        # note: 10 steps
        stat["atomic_steps"] = (
            10 * st_o[str(RecordState.md_imported)]
            - 8 * stat["colrev_status"]["currently"]["md_duplicates_removed"]
            - 7 * stat["colrev_status"]["currently"]["rev_prescreen_excluded"]
            - 6 * stat["colrev_status"]["currently"]["pdf_not_available"]
            - stat["colrev_status"]["currently"]["rev_excluded"]
            - stat["colrev_status"]["currently"]["rev_synthesized"]
        )
        stat["completed_atomic_steps"] = completed_atomic_steps
        self.REVIEW_MANAGER.logger.debug(
            f"stat: {self.REVIEW_MANAGER.pp.pformat(stat)}"
        )
        return stat

    def get_priority_transition(self, *, current_origin_states_dict: dict) -> list:
        from colrev_core.process import ProcessModel

        # get "earliest" states (going backward)
        earliest_state = []
        search_states = ["rev_synthesized"]
        while True:
            if any(
                search_state in current_origin_states_dict.values()
                for search_state in search_states
            ):
                earliest_state = [
                    search_state
                    for search_state in search_states
                    if search_state in current_origin_states_dict.values()
                ]
            search_states = [
                str(x["source"])
                for x in ProcessModel.transitions
                if str(x["dest"]) in search_states
            ]
            if [] == search_states:
                break
        # print(f'earliest_state: {earliest_state}')

        # next: get the priority transition for the earliest states
        priority_transitions = [
            x["trigger"]
            for x in ProcessModel.transitions
            if str(x["source"]) in earliest_state
        ]
        # print(f'priority_transitions: {priority_transitions}')
        return list(set(priority_transitions))

    def get_active_processing_functions(
        self, *, current_origin_states_dict: dict
    ) -> list:
        from colrev_core.process import ProcessModel

        active_processing_functions = []
        for state in current_origin_states_dict.values():
            srec = ProcessModel(state=state)
            t = srec.get_valid_transitions()
            active_processing_functions.extend(t)
        return active_processing_functions

    def get_remote_commit_differences(self, *, git_repo: git.Repo) -> list:
        from git.exc import GitCommandError

        nr_commits_behind, nr_commits_ahead = -1, -1

        origin = git_repo.remotes.origin
        if origin.exists():
            try:
                origin.fetch()
            except GitCommandError:
                pass  # probably not online
                return [-1, -1]

        if git_repo.active_branch.tracking_branch() is not None:

            branch_name = str(git_repo.active_branch)
            tracking_branch_name = str(git_repo.active_branch.tracking_branch())
            self.REVIEW_MANAGER.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

        return [nr_commits_behind, nr_commits_ahead]

    def get_environment_instructions(self, *, stat: dict) -> list:
        from colrev_core.environment import EnvironmentManager

        environment_instructions = []

        if stat["colrev_status"]["currently"]["md_imported"] > 10:
            with open(
                self.REVIEW_MANAGER.paths["MAIN_REFERENCES"], encoding="utf8"
            ) as r:
                outlets = []
                for line in r.readlines():

                    if "journal" == line.lstrip()[:7]:
                        journal = line[line.find("{") + 1 : line.rfind("}")]
                        outlets.append(journal)
                    if "booktitle" == line.lstrip()[:9]:
                        booktitle = line[line.find("{") + 1 : line.rfind("}")]
                        outlets.append(booktitle)
            outlet_counter: typing.List[typing.Tuple[str, int]] = [
                (j, x) for j, x in Counter(outlets).most_common(10) if x > 5
            ]
            selected = []
            cumulative = 0.0
            for candidate, freq in outlet_counter:
                selected.append((candidate, freq))
                cumulative += freq / len(outlets)
                if cumulative > 0.7:
                    break
            if len(selected) > 0:
                curated_outlets = EnvironmentManager.get_curated_outlets()
                selected_journals = [
                    (candidate, freq)
                    for candidate, freq in selected
                    if candidate not in curated_outlets
                ]

                journals = "\n   - " + "\n   - ".join(
                    [
                        f"{candidate} ({round((freq/len(outlets))*100, 2)}%)"
                        for candidate, freq in selected_journals
                    ]
                )

                if len(selected_journals) > 0:
                    instruction = {
                        "msg": "Search and download curated metadata for your "
                        "project (if available). \n  The most common journals in "
                        f"your project are {journals}.\n"
                        "  They may be available at "
                        "https://github.com/topics/colrev-curated",
                    }
                    environment_instructions.append(instruction)

        local_registry = EnvironmentManager.load_local_registry()
        registered_paths = [Path(x["source_url"]) for x in local_registry]
        # Note : we can use many parallel processes
        # because append_registered_repo_instructions mainly waits for the network
        # it does not use a lot of CPU capacity
        pool = multiprocessing.Pool(processes=30)
        add_instructions = pool.map(
            self.append_registered_repo_instructions, registered_paths
        )
        environment_instructions += list(filter(None, add_instructions))

        if len(list(self.REVIEW_MANAGER.paths["CORRECTIONS_PATH"].glob("*.json"))) > 0:
            instruction = {
                "msg": "Corrections to share with curated repositories.",
                "cmd": "colrev push -r",
            }
            environment_instructions.append(instruction)

        return environment_instructions

    @classmethod
    def append_registered_repo_instructions(cls, registered_path):
        # Note: do not use named arguments (multiprocessing)
        try:
            REPO_REVIEW_MANAGER = ReviewManager(path_str=str(registered_path))
        except (NoSuchPathError, InvalidGitRepositoryError):
            pass
            instruction = {
                "msg": "Locally registered repo no longer exists.",
                "cmd": f"colrev env --unregister {registered_path}",
            }
            return instruction
        except Exception as e:
            print(f"Error in {registered_path}: {e}")
            pass
            return {}
        if "curated_metadata" in str(registered_path):
            if (
                REPO_REVIEW_MANAGER.REVIEW_DATASET.behind_remote()
                and not REPO_REVIEW_MANAGER.REVIEW_DATASET.remote_ahead()
            ):
                instruction = {
                    "msg": "Updates available for curated repo "
                    f"({registered_path}).",
                    "cmd": "colrev env --update",
                }
                return instruction
            elif (
                REPO_REVIEW_MANAGER.REVIEW_DATASET.behind_remote()
                and REPO_REVIEW_MANAGER.REVIEW_DATASET.remote_ahead()
            ):
                instruction = {
                    "msg": "Local/remote branch diverged for curated repo "
                    f"({registered_path}).",
                    "cmd": f"cd '{registered_path}' && git pull --rebase",
                }
                return instruction

        return {}

    def get_review_instructions(self, *, stat) -> list:

        review_instructions = []

        # git_repo = REVIEW_MANAGER.get_repo()
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]

        missing_files = self.REVIEW_MANAGER.REVIEW_DATASET.get_missing_files()

        # Check pdf files
        if len(missing_files) > 0:
            review_instructions.append(
                {
                    "msg": "record with colrev_status requiring a PDF file but missing "
                    + f"the path (file = ...): {missing_files}"
                }
            )

        if len(missing_files) > 0:
            if len(missing_files) < 10:
                non_existent_pdfs = ",".join(missing_files)
            else:
                non_existent_pdfs = ",".join(missing_files[0:10] + ["..."])
            review_instructions.append(
                {
                    "msg": f"record with broken file link ({non_existent_pdfs})."
                    " Use\n    colrev pdf-get --relink_files"
                }
            )

        current_origin_states_dict = (
            self.REVIEW_MANAGER.REVIEW_DATASET.get_origin_state_dict()
        )

        # temporarily override for testing
        # current_states_set = {'pdf_imported', 'pdf_needs_retrieval'}
        # from colrev_core.process import ProcessModel
        # current_states_set = set([x['source'] for x in ProcessModel.transitions])

        MAIN_REFS_CHANGED = str(MAIN_REFERENCES_RELATIVE) in [
            item.a_path for item in git_repo.index.diff(None)
        ] + [x.a_path for x in git_repo.head.commit.diff()]

        try:
            revlist = (
                (
                    commit.hexsha,
                    (commit.tree / str(MAIN_REFERENCES_RELATIVE)).data_stream.read(),
                )
                for commit in git_repo.iter_commits(paths=str(MAIN_REFERENCES_RELATIVE))
            )
            filecontents = list(revlist)[0][1]
        except IndexError:
            pass
            MAIN_REFS_CHANGED = False

        # If changes in MAIN_REFERENCES are staged, we need to detect the process type
        if MAIN_REFS_CHANGED:
            # Detect and validate transitions

            from colrev_core.process import ProcessModel

            committed_origin_states_dict = (
                self.REVIEW_MANAGER.REVIEW_DATASET.get_origin_state_dict(
                    file_object=io.StringIO(filecontents.decode("utf-8"))
                )
            )

            transitioned_records = []
            for (
                committed_origin,
                committed_colrev_status,
            ) in committed_origin_states_dict.items():
                transitioned_record = {
                    "origin": committed_origin,
                    "source": committed_colrev_status,
                }

                if committed_origin not in current_origin_states_dict:
                    print(f"Error (no source_state): {transitioned_record}")
                    review_instructions.append(
                        {
                            "msg": "Resolve committed colrev_status "
                            + f"of {transitioned_record}",
                            "priority": "yes",
                        }
                    )
                    continue

                transitioned_record["dest"] = current_origin_states_dict[
                    committed_origin
                ]

                process_type = [
                    x["trigger"]
                    for x in ProcessModel.transitions
                    if str(x["source"]) == transitioned_record["source"]
                    and str(x["dest"]) == transitioned_record["dest"]
                ]
                if (
                    len(process_type) == 0
                    and transitioned_record["source"] != transitioned_record["dest"]
                ):
                    # + f"{transitioned_record['ID']} from "
                    msg = (
                        "Resolve invalid transition of "
                        + f"{transitioned_record['source']} to "
                        + f"{transitioned_record['dest']}"
                    )
                    if msg not in [ri["msg"] for ri in review_instructions]:
                        review_instructions.append(
                            {
                                "msg": msg,
                                "priority": "yes",
                            }
                        )
                    continue

                if len(process_type) > 0:
                    transitioned_record["process_type"] = process_type[0]
                    transitioned_records.append(transitioned_record)

            in_progress_processes = list(
                {x["process_type"] for x in transitioned_records}
            )
            self.REVIEW_MANAGER.logger.debug(
                f"in_progress_processes: {in_progress_processes}"
            )
            if len(in_progress_processes) == 1:
                instruction = {
                    "msg": f"Detected {in_progress_processes[0]} in progress. "
                    + "Complete this process",
                    "cmd": f"colrev {in_progress_processes[0]}",
                }
                instruction["priority"] = "yes"
                review_instructions.append(instruction)
            elif len(in_progress_processes) > 1:
                rec_str = ", ".join([x["ID"] for x in transitioned_records])
                instruction = {
                    "msg": "Detected multiple processes in progress "
                    + f"({', '.join(in_progress_processes)}). Complete one "
                    + "(save and revert the other) and commit before continuing!\n"
                    + f"  Records: {rec_str}",
                    # "cmd": f"colrev_core {in_progress_processes}",
                }
                instruction["priority"] = "yes"
                review_instructions.append(instruction)

        self.REVIEW_MANAGER.logger.debug(
            f"current_origin_states_dict: {current_origin_states_dict}"
        )
        active_processing_functions = self.get_active_processing_functions(
            current_origin_states_dict=current_origin_states_dict
        )
        self.REVIEW_MANAGER.logger.debug(
            f"active_processing_functions: {active_processing_functions}"
        )
        priority_processing_functions = self.get_priority_transition(
            current_origin_states_dict=current_origin_states_dict
        )
        self.REVIEW_MANAGER.logger.debug(
            f"priority_processing_function: {priority_processing_functions}"
        )
        delay_automated_processing = (
            self.REVIEW_MANAGER.settings.project.delay_automated_processing
        )
        msgs = {
            "load": "Next step: Import search results",
            "prep": "Next step: Prepare records",
            "prep_man": "Next step: Prepare records (manually)",
            "dedupe": "Next step: Deduplicate records",
            "prescreen": "Next step: Prescreen records",
            "pdf_get": "Next step: Retrieve PDFs",
            "pdf_get_man": "Next step: Retrieve PDFs (manually)",
            "pdf_prep": "Next step: Prepare PDFs",
            "pdf_prep_man": "Next step: Prepare PDFs (manually)",
            "screen": "Next step: Screen records",
            "data": "Next step: Extract data/synthesize records",
        }
        if stat["colrev_status"]["currently"]["md_retrieved"] > 0:
            instruction = {
                "msg": msgs["load"],
                "cmd": "colrev load",
                "priority": "yes",
                # "high_level_cmd": "colrev metadata",
            }
            review_instructions.append(instruction)

        else:
            for active_processing_function in active_processing_functions:
                instruction = {
                    "msg": msgs[active_processing_function],
                    "cmd": f"colrev {active_processing_function.replace('_', '-')}"
                    # "high_level_cmd": "colrev metadata",
                }
                if active_processing_function in priority_processing_functions:
                    # keylist = [list(x.keys()) for x in review_instructions]
                    # keys = [item for sublist in keylist for item in sublist]
                    # if "priority" not in keys:
                    instruction["priority"] = "yes"
                else:
                    if "True" == delay_automated_processing:
                        continue
                if instruction["cmd"] not in [
                    ri["cmd"] for ri in review_instructions if "cmd" in ri
                ]:
                    review_instructions.append(instruction)

        if not self.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
            instruction = {
                "msg": "To import, copy search results to the search directory.",
                "cmd": "colrev load",
            }
            if instruction["cmd"] not in [
                ri["cmd"] for ri in review_instructions if "cmd" in ri
            ]:
                review_instructions.append(instruction)

        if (
            stat["completeness_condition"]
            and stat["colrev_status"]["currently"]["md_retrieved"] > 0
        ):

            search_dir = str(self.REVIEW_MANAGER.paths["SEARCHDIR_RELATIVE"]) + "/"
            untracked_files = self.REVIEW_MANAGER.REVIEW_DATASET.get_untracked_files()
            if not any(
                search_dir in untracked_file for untracked_file in untracked_files
            ):
                instruction = {
                    "info": "Iterationed completed.",
                    "msg": "To start the next iteration of the review, "
                    + "add new search results to ./search directory",
                }
                review_instructions.append(instruction)
            else:
                instruction = {
                    "info": "Search results available for next iteration.",
                    "msg": "Next step: Import search results.",
                    "cmd": "colrev load",
                }
                review_instructions.append(instruction)

        if "MANUSCRIPT" in [
            s["endpoint"] for s in self.REVIEW_MANAGER.settings.data.scripts
        ]:
            instruction = {
                "msg": "Build the paper",
                "cmd": "colrev paper",
            }
            review_instructions.append(instruction)

        return review_instructions

    def get_collaboration_instructions(self, *, stat) -> dict:

        SHARE_STAT_REQ = self.REVIEW_MANAGER.settings.project.share_stat_req
        found_a_conflict = False
        # git_repo = REVIEW_MANAGER.get_repo()
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        unmerged_blobs = git_repo.index.unmerged_blobs()
        for path in unmerged_blobs:
            list_of_blobs = unmerged_blobs[path]
            for (stage, blob) in list_of_blobs:
                if stage != 0:
                    found_a_conflict = True

        nr_commits_behind, nr_commits_ahead = 0, 0

        collaboration_instructions: dict = {"items": []}
        CONNECTED_REMOTE = 0 != len(git_repo.remotes)
        if CONNECTED_REMOTE:
            origin = git_repo.remotes.origin
            if origin.exists():
                (
                    nr_commits_behind,
                    nr_commits_ahead,
                ) = self.get_remote_commit_differences(git_repo=git_repo)
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

        non_staged = [
            item.a_path
            for item in git_repo.index.diff(None)
            if ".bib" == item.a_path[-4:]
        ]
        if len(non_staged) > 0:
            item = {
                "title": f"Non-staged changes: {','.join(non_staged)}",
                "level": "WARNING",
            }
            collaboration_instructions["items"].append(item)

        elif not found_a_conflict:
            if CONNECTED_REMOTE:
                if nr_commits_behind > 0:
                    item = {
                        "title": "Remote changes available on the server",
                        "level": "WARNING",
                        "msg": "Once you have committed your changes, get the latest "
                        + "remote changes",
                        "cmd_after": "git add FILENAME \n  git commit -m 'MSG' \n  "
                        + "git pull --rebase",
                    }
                    collaboration_instructions["items"].append(item)

                if nr_commits_ahead > 0:
                    # TODO : suggest detailed commands
                    # (depending on the working directory/index)
                    item = {
                        "title": "Local changes not yet on the server",
                        "level": "WARNING",
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

                # TODO : all the following: should all search results be imported?!
                if SHARE_STAT_REQ == "PROCESSED":
                    if 0 == stat["colrev_status"]["currently"]["non_processed"]:
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
                    # TODO : the following condition is probably not sufficient
                    if 0 == stat["colrev_status"]["currently"]["pdf_prepared"]:
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
                    if 0 == stat["colrev_status"]["currently"]["non_completed"]:
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
            }
            collaboration_instructions["items"].append(item)

        return collaboration_instructions

    def get_instructions(self, *, stat: dict) -> dict:
        instructions = {
            "review_instructions": self.get_review_instructions(stat=stat),
            "environment_instructions": self.get_environment_instructions(stat=stat),
            "collaboration_instructions": self.get_collaboration_instructions(
                stat=stat
            ),
        }

        self.REVIEW_MANAGER.logger.debug(
            f"instructions: {self.REVIEW_MANAGER.pp.pformat(instructions)}"
        )
        return instructions

    def print_review_status(self, *, status_info: dict) -> None:
        class colors:
            RED = "\033[91m"
            GREEN = "\033[92m"
            ORANGE = "\033[93m"
            BLUE = "\033[94m"
            END = "\033[0m"

        print("")
        print("Status")
        print("")

        # NOTE: the first figure should always
        # refer to the nr of records that completed this step

        stat = status_info["colrev_status"]

        perc_curated = 0
        denominator = (
            stat["overall"]["md_prepared"]
            + stat["currently"]["md_needs_manual_preparation"]
            - stat["currently"]["md_duplicates_removed"]
        )
        if denominator > 0:

            perc_curated = (stat["CURATED_records"] / (denominator)) * 100

        rjust_padd = 7
        search_info = (
            "  Search        "
            + f'{str(stat["overall"]["md_retrieved"]).rjust(rjust_padd, " ")} retrieved'
        )
        search_add_info = []
        if stat["overall"]["md_prepared"] > 0:
            # search_add_info.append(f"{str(int(perc_curated))}% curated")
            # Note: do not print percentages becaus
            # - the other figures are all absolute numbers
            # - the denominator changes (particularly confusing in the prep when
            #   the number of curated records remains the same but the percentage
            #   decreases)
            if perc_curated < 30:
                search_add_info.append(
                    f"only {colors.RED}{str(stat['CURATED_records'])} "
                    f"curated{colors.END}"
                )
            elif perc_curated > 60:
                search_add_info.append(
                    f"{colors.GREEN}{str(stat['CURATED_records'])} curated{colors.END}"
                )
            else:
                search_add_info.append(f"{str(stat['CURATED_records'])} curated")
        if stat["currently"]["md_retrieved"] > 0:
            search_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["md_retrieved"]}'
                f" to load{colors.END}"
            )
        if len(search_add_info) > 0:
            search_info += f'    ({", ".join(search_add_info)})'
        print(search_info)

        metadata_info = (
            "  Metadata      "
            + f'{str(stat["overall"]["md_processed"]).rjust(rjust_padd, " ")} processed'
        )
        metadata_add_info = []
        if stat["currently"]["md_duplicates_removed"] > 0:
            metadata_add_info.append(
                f'{stat["currently"]["md_duplicates_removed"]} duplicates removed'
            )

        if stat["currently"]["md_imported"] > 0:
            metadata_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["md_imported"]}'
                f" to prepare{colors.END}"
            )

        if stat["currently"]["md_needs_manual_preparation"] > 0:
            metadata_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["md_needs_manual_preparation"]} '
                f"to prepare manually{colors.END}"
            )

        if stat["currently"]["md_prepared"] > 0:
            metadata_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["md_prepared"]}'
                f" to deduplicate{colors.END}"
            )

        if len(metadata_add_info) > 0:
            metadata_info += f"    ({', '.join(metadata_add_info)})"
        print(metadata_info)

        prescreen_info = (
            "  Prescreen     "
            + f'{str(stat["overall"]["rev_prescreen_included"]).rjust(rjust_padd, " ")}'
            " included"
        )
        prescreen_add_info = []
        if stat["currently"]["rev_prescreen_excluded"] > 0:
            prescreen_add_info.append(
                f'{stat["currently"]["rev_prescreen_excluded"]} excluded'
            )
        if stat["currently"]["md_processed"] > 0:
            prescreen_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["md_processed"]}'
                f" to prescreen{colors.END}"
            )
        if len(prescreen_add_info) > 0:
            prescreen_info += f"     ({', '.join(prescreen_add_info)})"
        print(prescreen_info)

        pdfs_info = (
            "  PDFs          "
            + f'{str(stat["overall"]["pdf_prepared"]).rjust(rjust_padd, " ")} prepared'
        )
        pdf_add_info = []
        if stat["currently"]["rev_prescreen_included"] > 0:
            pdf_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["rev_prescreen_included"]}'
                f" to retrieve{colors.END}"
            )
        if stat["currently"]["pdf_needs_manual_retrieval"] > 0:
            pdf_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["pdf_needs_manual_retrieval"]}'
                f" to retrieve manually{colors.END}"
            )
        if stat["currently"]["pdf_not_available"] > 0:
            pdf_add_info.append(
                f'{stat["currently"]["pdf_not_available"]} not available'
            )
        if stat["currently"]["pdf_imported"] > 0:
            pdf_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["pdf_imported"]}'
                f" to prepare{colors.END}"
            )
        if stat["currently"]["pdf_needs_manual_preparation"] > 0:
            pdf_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["pdf_needs_manual_preparation"]}'
                f" to prepare manually{colors.END}"
            )
        if len(pdf_add_info) > 0:
            pdfs_info += f"     ({', '.join(pdf_add_info)})"
        print(pdfs_info)

        screen_info = (
            "  Screen        "
            + f'{str(stat["overall"]["rev_included"]).rjust(rjust_padd, " ")} included'
        )
        screen_add_info = []
        if stat["currently"]["pdf_prepared"] > 0:
            screen_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["pdf_prepared"]}'
                f" to screen{colors.END}"
            )
        if stat["currently"]["rev_excluded"] > 0:
            screen_add_info.append(f'{stat["currently"]["rev_excluded"]} excluded')
        if len(screen_add_info) > 0:
            screen_info += f"     ({', '.join(screen_add_info)})"
        print(screen_info)

        data_info = (
            "  Data          "
            + f'{str(stat["overall"]["rev_synthesized"]).rjust(rjust_padd, " ")} '
            "synthesized"
        )
        data_add_info = []
        if stat["currently"]["rev_included"] > 0:
            data_add_info.append(
                f'{colors.ORANGE}{stat["currently"]["rev_included"]}'
                f" to synthesize{colors.END}"
            )
        if len(data_add_info) > 0:
            data_info += f'  ({", ".join(data_add_info)})'
        print(data_info)

        return

    def get_analytics(self) -> dict:
        import yaml

        analytics_dict = {}

        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))

        revlist = list(
            (
                commit.hexsha,
                commit.author.name,
                commit.committed_date,
                (commit.tree / "status.yaml").data_stream.read(),
            )
            for commit in git_repo.iter_commits(paths="status.yaml")
        )
        for ind, (commit_id, commit_author, committed_date, filecontents) in enumerate(
            revlist
        ):
            try:
                var_t = io.StringIO(filecontents.decode("utf-8"))

                # TODO : we should simply include the whole status.yaml
                # (to create a general-purpose status analyzer)
                # -> flatten nested structures (e.g., overall/currently)
                # -> integrate with get_status (current data) -
                # and get_prior? (levels: aggregated_statistics vs. record-level?)

                data_loaded = yaml.safe_load(var_t)
                analytics_dict[len(revlist) - ind] = {
                    "commit_id": commit_id,
                    "commit_author": commit_author,
                    "committed_date": committed_date,
                    "search": data_loaded["colrev_status"]["overall"]["md_retrieved"],
                    "included": data_loaded["colrev_status"]["overall"]["rev_included"],
                }
            except (IndexError, KeyError):
                pass

        import csv

        keys = list(analytics_dict.values())[0].keys()

        with open("analytics.csv", "w", newline="") as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(reversed(analytics_dict.values()))

        # TODO : the inclusion rate would be interesting
        # if it declines, we can justify terminating the search
        # TBD: do we need to determine "iterations" for that?
        # Should those iterations be based on "all-screened" or "all-synthesized"?
        # Illustrate with a simulation!?

        return analytics_dict


if __name__ == "__main__":
    pass
