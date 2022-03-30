#! /usr/bin/env python3
import io
import typing
from collections import Counter
from pathlib import Path

import git

from colrev_core.process import Process
from colrev_core.process import ProcessType


class Status(Process):
    def __init__(self, REVIEW_MANAGER):
        super().__init__(REVIEW_MANAGER, ProcessType.explore)

    def __get_nr_in_bib(self, file_path: Path) -> int:

        number_in_bib = 0
        with open(file_path) as f:
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

    def get_excl_criteria(self, ec_string: str) -> list:
        return [ec.split("=")[0] for ec in ec_string.split(";") if ec != "NA"]

    def get_status_freq(self) -> dict:
        from colrev_core.process import RecordState
        from colrev_core.process import ProcessModel

        record_header_list = self.REVIEW_MANAGER.REVIEW_DATASET.get_record_header_list()
        status_list = [x[2] for x in record_header_list]
        excl_criteria = [x[3] for x in record_header_list if x[3] != ""]
        md_duplicates_removed = sum((x[1].count(";")) for x in record_header_list)

        origin_list = [x[1] for x in record_header_list]
        record_links = 0
        for origin in origin_list:
            nr_record_links = origin.count(";")
            record_links += nr_record_links + 1

        stat: dict = {"status": {}}
        metadata_sources = [x[5] for x in record_header_list]
        stat["status"]["CURATED_records"] = len(
            [x for x in metadata_sources if "CURATED" == x]
        )

        exclusion_statistics = {}
        if excl_criteria:
            criteria = self.get_excl_criteria(excl_criteria[0])
            exclusion_statistics = {crit: 0 for crit in criteria}
            for exclusion_case in excl_criteria:
                for crit in criteria:
                    if crit + "=yes" in exclusion_case:
                        exclusion_statistics[crit] += 1

        stat["status"]["currently"] = {str(rs): 0 for rs in list(RecordState)}
        stat["status"]["overall"] = {str(rs): 0 for rs in list(RecordState)}

        currently_stats = dict(Counter(status_list))
        for currently_stat, val in currently_stats.items():
            stat["status"]["currently"][currently_stat] = val
            stat["status"]["overall"][currently_stat] = val

        atomic_step_number = 0
        completed_atomic_steps = 0

        self.REVIEW_MANAGER.logger.debug(
            "Set overall status statistics (going backwards)"
        )
        st_o = stat["status"]["overall"]
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
                nr_incomplete += stat["status"]["currently"][
                    str(trans_for_completeness["source"])
                ]

            t_list = [t for t in ProcessModel.transitions if current_state == t["dest"]]
            t: dict = t_list.pop()
            if current_state == RecordState.md_imported:
                break
            current_state = t["source"]  # go a step back
            non_completed += stat["status"]["currently"][str(current_state)]

        stat["status"]["currently"]["non_completed"] = non_completed

        stat["status"]["currently"]["non_processed"] = (
            stat["status"]["currently"]["md_imported"]
            + stat["status"]["currently"]["md_retrieved"]
            + stat["status"]["currently"]["md_needs_manual_preparation"]
            + stat["status"]["currently"]["md_prepared"]
        )

        stat["status"]["currently"]["md_duplicates_removed"] = md_duplicates_removed
        stat["status"]["overall"]["md_retrieved"] = self.get_nr_search()
        stat["status"]["currently"]["md_retrieved"] = (
            stat["status"]["overall"]["md_retrieved"] - record_links
        )
        stat["completeness_condition"] = (0 == nr_incomplete) and (
            0 == stat["status"]["currently"]["md_retrieved"]
        )

        stat["status"]["currently"]["exclusion"] = exclusion_statistics

        stat["status"]["overall"]["rev_screen"] = stat["status"]["overall"][
            "pdf_prepared"
        ]
        stat["status"]["overall"]["rev_prescreen"] = stat["status"]["overall"][
            "md_processed"
        ]
        stat["status"]["currently"]["pdf_needs_retrieval"] = stat["status"][
            "currently"
        ]["rev_prescreen_included"]

        # note: 10 steps
        stat["atomic_steps"] = (
            10 * st_o[str(RecordState.md_imported)]
            - stat["status"]["currently"]["md_duplicates_removed"] * 8
            - stat["status"]["currently"]["rev_prescreen_excluded"] * 7
            - stat["status"]["currently"]["pdf_not_available"] * 6
            - stat["status"]["currently"]["rev_excluded"]
        )
        stat["completed_atomic_steps"] = completed_atomic_steps
        self.REVIEW_MANAGER.logger.debug(
            f"stat: {self.REVIEW_MANAGER.pp.pformat(stat)}"
        )
        return stat

    def get_priority_transition(self, current_states: set) -> list:
        from colrev_core.process import ProcessModel

        # get "earliest" states (going backward)
        earliest_state = []
        search_states = ["rev_synthesized"]
        while True:
            if any(
                search_state in list(current_states) for search_state in search_states
            ):
                earliest_state = [
                    search_state
                    for search_state in search_states
                    if search_state in current_states
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

    def get_active_processing_functions(self, current_states_set) -> list:
        from colrev_core.process import ProcessModel

        active_processing_functions = []
        for state in current_states_set:
            srec = ProcessModel(state=state)
            t = srec.get_valid_transitions()
            active_processing_functions.extend(t)
        return active_processing_functions

    def get_remote_commit_differences(self, git_repo: git.Repo) -> list:
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

    def get_environment_instructions(self, stat: dict) -> list:
        from colrev_core.review_manager import ReviewManager
        from git.exc import NoSuchPathError
        from git.exc import InvalidGitRepositoryError
        from colrev_core.environment import EnvironmentManager

        environment_instructions = []

        if stat["status"]["currently"]["md_imported"] > 10:
            with open(self.REVIEW_MANAGER.paths["MAIN_REFERENCES"]) as r:
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
                journals = "\n   - " + "\n   - ".join(
                    [
                        f"{candidate} ({round((freq/len(outlets))*100, 2)}%)"
                        for candidate, freq in selected
                    ]
                )
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
        for registered_path in registered_paths:

            try:
                REPO_REVIEW_MANAGER = ReviewManager(str(registered_path))
            except (NoSuchPathError, InvalidGitRepositoryError):
                pass
                instruction = {
                    "msg": "Locally registered repo no longer exists.",
                    "cmd": f"colrev env --unregister {registered_path}",
                }
                environment_instructions.append(instruction)
                continue
            if "curated_metadata" in str(registered_path):
                if REPO_REVIEW_MANAGER.REVIEW_DATASET.behind_remote():
                    instruction = {
                        "msg": "Updates available for curated repo "
                        f"({registered_path}).",
                        "cmd": "colrev env --update",
                    }
                    environment_instructions.append(instruction)
        if len(list(self.REVIEW_MANAGER.paths["CORRECTIONS_PATH"].glob("*.json"))) > 0:
            instruction = {
                "msg": "Corrections to share with curated repositories.",
                "cmd": "colrev env --apply_corrections",
            }
            environment_instructions.append(instruction)

        return environment_instructions

    def get_review_instructions(self, stat) -> list:
        review_instructions = []

        # git_repo = REVIEW_MANAGER.get_repo()
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        MAIN_REFERENCES_RELATIVE = self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]

        non_staged = [
            item.a_path
            for item in git_repo.index.diff(None)
            if ".bib" == item.a_path[-4:]
        ]

        if len(non_staged) > 0:
            instruction = {
                "msg": "Add non-staged changes.",
                "cmd": f"git add {', '.join(non_staged)}",
            }
            if str(self.REVIEW_MANAGER.paths["MAIN_REFERENCES_RELATIVE"]) in non_staged:
                instruction["priority"] = "yes"
            review_instructions.append(instruction)

        current_record_state_list = (
            self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list()
        )
        current_states_set = self.REVIEW_MANAGER.REVIEW_DATASET.get_states_set(
            current_record_state_list
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

            committed_record_states_list = (
                self.REVIEW_MANAGER.REVIEW_DATASET.get_record_state_list_from_file_obj(
                    io.StringIO(filecontents.decode("utf-8"))
                )
            )

            record_state_items = [
                record_state
                for record_state in current_record_state_list
                if record_state not in committed_record_states_list
            ]
            transitioned_records = []
            for item in record_state_items:
                # TODO : we should match the current and committed records based
                # on their origins because IDs may change (e.g., in the preparation)
                transitioned_record = {"ID": item[0], "dest": item[1]}

                source_state = [
                    rec[1] for rec in committed_record_states_list if rec[0] == item[0]
                ]
                if len(source_state) != 1:

                    print(f"Error (no source_state): {transitioned_record}")
                    review_instructions.append(
                        {
                            "msg": f"Resolve committed status of {transitioned_record}",
                            "priority": "yes",
                        }
                    )
                    continue
                transitioned_record["source"] = source_state[0]

                process_type = [
                    x["trigger"]
                    for x in ProcessModel.transitions
                    if str(x["source"]) == transitioned_record["source"]
                    and str(x["dest"]) == transitioned_record["dest"]
                ]
                if len(process_type) == 0:
                    review_instructions.append(
                        {
                            "msg": "Resolve invalid transition of "
                            + f"{transitioned_record['ID']} from "
                            + f"{transitioned_record['source']} to "
                            + f" {transitioned_record['dest']}",
                            "priority": "yes",
                        }
                    )
                    continue
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

        self.REVIEW_MANAGER.logger.debug(f"current_states_set: {current_states_set}")
        active_processing_functions = self.get_active_processing_functions(
            current_states_set
        )
        self.REVIEW_MANAGER.logger.debug(
            f"active_processing_functions: {active_processing_functions}"
        )
        priority_processing_functions = self.get_priority_transition(current_states_set)
        self.REVIEW_MANAGER.logger.debug(
            f"priority_processing_function: {priority_processing_functions}"
        )

        msgs = {
            "load": "Import search results",
            "prep": "Prepare records",
            "prep_man": "Prepare records (manually)",
            "dedupe": "Deduplicate records",
            "prescreen": "Prescreen records",
            "pdf_get": "Retrieve pdfs",
            "pdf_get_man": "Retrieve pdfs (manually)",
            "pdf_prep": "Prepare pdfs",
            "pdf_prep_man": "Prepare pdfs (manually)",
            "screen": "Screen records",
            "data": "Extract data/synthesize records",
        }
        if stat["status"]["currently"]["md_retrieved"] > 0:
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
                    keylist = [list(x.keys()) for x in review_instructions]
                    keys = [item for sublist in keylist for item in sublist]
                    if "priority" not in keys:
                        instruction["priority"] = "yes"
                else:
                    if self.REVIEW_MANAGER.config["DELAY_AUTOMATED_PROCESSING"]:
                        continue
                review_instructions.append(instruction)

        if not self.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
            instruction = {
                "msg": "To import, copy search results to the search directory.",
                "cmd": "colrev load",
            }
            review_instructions.append(instruction)

        if stat["completeness_condition"]:
            instruction = {
                "info": "Iterationed completed.",
                "msg": "To start the next iteration of the review, "
                + "add records to search/ directory",
                "cmd_after": "colrev load",
            }
            review_instructions.append(instruction)

        if "MANUSCRIPT" == self.REVIEW_MANAGER.config["DATA_FORMAT"]:
            instruction = {
                "msg": "Build the paper",
                "cmd": "colrev paper",
            }
            review_instructions.append(instruction)

        return review_instructions

    def get_collaboration_instructions(self, stat) -> dict:

        SHARE_STAT_REQ = self.REVIEW_MANAGER.config["SHARE_STAT_REQ"]
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
                ) = self.get_remote_commit_differences(git_repo)
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
                "title": f"Non-staged files: {','.join(non_staged)}",
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
                        "cmd_after": "git add FILENAME \n git commit -m 'MSG' \n "
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
                    if 0 == stat["status"]["currently"]["non_processed"]:
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
                    if 0 == stat["review_status"]["currently"]["pdf_prepared"]:
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

        return collaboration_instructions

    def get_instructions(self, stat: dict) -> dict:
        instructions = {
            "review_instructions": self.get_review_instructions(stat),
            "environment_instructions": self.get_environment_instructions(stat),
            "collaboration_instructions": self.get_collaboration_instructions(stat),
        }
        self.REVIEW_MANAGER.logger.debug(
            f"instructions: {self.REVIEW_MANAGER.pp.pformat(instructions)}"
        )
        return instructions

    def stat_print(
        self,
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
                stat = " |  - " + field1
            else:
                stat = "   - " + field1
        else:
            if separate_category:
                stat = " | "
            else:
                stat = " "
        rjust_padd = 31 - len(stat)
        stat = stat + str(val1).rjust(rjust_padd, " ")
        if connector is not None:
            stat = stat + "  " + connector + "  "
        if val2 != "":
            rjust_padd = 41 - len(stat)
            stat = stat + str(val2).rjust(rjust_padd, " ") + " "
        if field2 != "":
            stat = stat + str(field2)
        # TBD: if we close it, the closing | does not align...
        # if separate_category:
        #     ljust_pad = (95 - len(stat))
        #     stat = stat.ljust(ljust_pad, "-") + "|"

        print(stat)
        return

    def print_review_status(self, statuts_info: dict) -> None:

        # Principle: first column shows total records/PDFs in each stage
        # the second column shows
        # (blank call)  * the number of records requiring manual action
        #               -> the number of records excluded/merged

        # print("\nStatus\n")
        print("\n")
        print("________________________ Status _______________________________")
        print("")
        if not self.REVIEW_MANAGER.paths["MAIN_REFERENCES"].is_file():
            print(" Search")
            print("  - No records added yet")
        else:

            stat = statuts_info["status"]

            print(" Search")
            perc_curated = 0
            denominator = (
                stat["overall"]["md_prepared"]
                + stat["currently"]["md_needs_manual_preparation"]
                - stat["currently"]["md_duplicates_removed"]
            )
            if denominator > 0:

                perc_curated = statuts_info["status"]["CURATED_records"] / (denominator)
            if stat["overall"]["md_prepared"] > 0:
                self.stat_print(
                    False,
                    "Records retrieved",
                    stat["overall"]["md_retrieved"],
                    "*",
                    f"curated ({round(perc_curated*100, 2)}%)",
                    str(statuts_info["status"]["CURATED_records"]),
                )
            else:
                self.stat_print(
                    False, "Records retrieved", stat["overall"]["md_retrieved"]
                )
            print(" ______________________________________________________________")
            print(" | Metadata preparation                                         ")
            if stat["currently"]["md_retrieved"] > 0:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "not yet imported",
                    stat["currently"]["md_retrieved"],
                )
            self.stat_print(True, "Records imported", stat["overall"]["md_imported"])
            if stat["currently"]["md_imported"] > 0:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "need preparation",
                    stat["currently"]["md_imported"],
                )
            if stat["currently"]["md_needs_manual_preparation"] > 0:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "to prepare (manually)",
                    stat["currently"]["md_needs_manual_preparation"],
                )
            self.stat_print(
                True,
                "Records prepared",
                stat["overall"]["md_prepared"],
            )
            if stat["currently"]["md_prepared"] > 0:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "to deduplicate",
                    stat["currently"]["md_prepared"],
                )
            self.stat_print(
                True,
                "Records processed",
                stat["overall"]["md_processed"],
                "->",
                "duplicates removed",
                stat["currently"]["md_duplicates_removed"],
            )
            print(" |_____________________________________________________________")
            print("")
            print(" Prescreen")
            if stat["overall"]["rev_prescreen"] == 0:
                self.stat_print(False, "Not initiated", "")
            else:
                self.stat_print(
                    False, "Prescreen size", stat["overall"]["rev_prescreen"]
                )
                if 0 != stat["currently"]["md_processed"]:
                    self.stat_print(
                        False,
                        "",
                        "",
                        "*",
                        "to prescreen",
                        stat["currently"]["md_processed"],
                    )
                self.stat_print(
                    False,
                    "Included",
                    stat["overall"]["rev_prescreen_included"],
                    "->",
                    "records excluded",
                    stat["currently"]["rev_prescreen_excluded"],
                )

            print(" ______________________________________________________________")
            print(" | PDF preparation                                             ")
            if 0 != stat["currently"]["rev_prescreen_included"]:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "to retrieve",
                    stat["currently"]["rev_prescreen_included"],
                )
            if 0 != stat["currently"]["pdf_needs_manual_retrieval"]:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "to retrieve manually",
                    stat["currently"]["pdf_needs_manual_retrieval"],
                )
            if stat["currently"]["pdf_not_available"] > 0:
                self.stat_print(
                    True,
                    "PDFs imported",
                    stat["overall"]["pdf_imported"],
                    "*",
                    "not available",
                    stat["currently"]["pdf_not_available"],
                )
            else:
                self.stat_print(True, "PDFs imported", stat["overall"]["pdf_imported"])
            if stat["currently"]["pdf_needs_manual_preparation"] > 0:
                self.stat_print(
                    True,
                    "",
                    "",
                    "*",
                    "to prepare (manually)",
                    stat["currently"]["pdf_needs_manual_preparation"],
                )
            if 0 != stat["currently"]["pdf_imported"]:
                self.stat_print(
                    True, "", "", "*", "to prepare", stat["currently"]["pdf_imported"]
                )
            self.stat_print(True, "PDFs prepared", stat["overall"]["pdf_prepared"])

            print(" |_____________________________________________________________")
            print("")
            print(" Screen")
            if stat["overall"]["rev_screen"] == 0:
                self.stat_print(False, "Not initiated", "")
            else:
                self.stat_print(False, "Screen size", stat["overall"]["rev_screen"])
                if 0 != stat["currently"]["pdf_prepared"]:
                    self.stat_print(
                        False,
                        "",
                        "",
                        "*",
                        "to screen",
                        stat["currently"]["pdf_prepared"],
                    )
                self.stat_print(
                    False,
                    "Included",
                    stat["overall"]["rev_included"],
                    "->",
                    "records excluded",
                    stat["currently"]["rev_excluded"],
                )
                if "exclusion" in stat["currently"]:
                    for crit, nr in stat["currently"]["exclusion"].items():
                        self.stat_print(False, "", "", "-", f": {crit}", nr)

            print("")
            print(" Data and synthesis")
            if stat["overall"]["rev_included"] == 0:
                self.stat_print(False, "Not initiated", "")
            else:
                self.stat_print(False, "Total", stat["overall"]["rev_included"])
                if 0 != stat["currently"]["rev_included"]:
                    self.stat_print(
                        False,
                        "Synthesized",
                        stat["overall"]["rev_synthesized"],
                        "*",
                        "to synthesize",
                        stat["currently"]["rev_included"],
                    )
                else:
                    self.stat_print(
                        False, "Synthesized", stat["overall"]["rev_synthesized"]
                    )

            print("_______________________________________________________________")

        return


if __name__ == "__main__":
    pass
