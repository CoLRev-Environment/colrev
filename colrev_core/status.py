#! /usr/bin/env python3
import csv
import io
import typing
from collections import Counter
from pathlib import Path

import git
import yaml

import colrev_core.process
import colrev_core.record


class Status(colrev_core.process.Process):
    def __init__(self, *, REVIEW_MANAGER):
        super().__init__(
            REVIEW_MANAGER=REVIEW_MANAGER,
            process_type=colrev_core.process.ProcessType.explore,
        )

    def get_priority_transition(self, *, current_origin_states_dict: dict) -> list:

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
                for x in colrev_core.process.ProcessModel.transitions
                if str(x["dest"]) in search_states
            ]
            if [] == search_states:
                break
        # print(f'earliest_state: {earliest_state}')

        # next: get the priority transition for the earliest states
        priority_transitions = [
            x["trigger"]
            for x in colrev_core.process.ProcessModel.transitions
            if str(x["source"]) in earliest_state
        ]
        # print(f'priority_transitions: {priority_transitions}')
        return list(set(priority_transitions))

    def get_active_processing_functions(
        self, *, current_origin_states_dict: dict
    ) -> list:

        active_processing_functions = []
        for state in current_origin_states_dict.values():
            srec = colrev_core.process.ProcessModel(state=state)
            t = srec.get_valid_transitions()
            active_processing_functions.extend(t)
        return active_processing_functions

    def get_environment_instructions(self, *, stat: dict) -> list:
        from multiprocessing.dummy import Pool as ThreadPool
        from colrev_core.environment import EnvironmentManager

        environment_instructions = []

        if stat["colrev_status"]["currently"]["md_imported"] > 10:
            with open(self.REVIEW_MANAGER.paths["RECORDS_FILE"], encoding="utf8") as r:
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
        registered_paths = [Path(x["repo_source_path"]) for x in local_registry]
        # Note : we can use many parallel processes
        # because append_registered_repo_instructions mainly waits for the network
        # it does not use a lot of CPU capacity
        pool = ThreadPool(50)
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

    def append_registered_repo_instructions(self, registered_path):

        instruction = {}

        try:
            git_repo = git.Repo(registered_path)

            # https://github.com/gitpython-developers/GitPython/issues/652#issuecomment-610511311
            origin = git_repo.remotes.origin

            if not origin.exists():
                raise AttributeError

            if git_repo.active_branch.tracking_branch() is None:
                raise AttributeError

            branch_name = str(git_repo.active_branch)
            tracking_branch_name = str(git_repo.active_branch.tracking_branch())
            self.REVIEW_MANAGER.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

            def pull_condition():
                # behind_remote and not remote_ahead
                return nr_commits_behind > 0 and not nr_commits_ahead > 0

            def pull_rebase_condition():
                # behind_remote and remote_ahead
                return nr_commits_behind > 0 and nr_commits_ahead > 0

            # Note: do not use named arguments (multiprocessing)
            if not Path(registered_path).is_dir():
                instruction = {
                    "msg": "Locally registered repo no longer exists.",
                    "cmd": f"colrev env --unregister {registered_path}",
                }

            elif "curated_metadata" in str(registered_path):
                if pull_condition():
                    instruction = {
                        "msg": "Updates available for curated repo "
                        f"({registered_path}).",
                        "cmd": "colrev env --update",
                    }

                elif pull_rebase_condition():
                    instruction = {
                        "msg": "Local/remote branch diverged for curated repo "
                        f"({registered_path}).",
                        "cmd": f"cd '{registered_path}' && git pull --rebase",
                    }

        except AttributeError:
            pass
        return instruction

    def get_review_instructions(self, *, stat) -> list:

        review_instructions = []

        # git_repo = REVIEW_MANAGER.get_repo()
        git_repo = git.Repo(str(self.REVIEW_MANAGER.paths["REPO_DIR"]))
        RECORDS_FILE_RELATIVE = self.REVIEW_MANAGER.paths["RECORDS_FILE_RELATIVE"]

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

        MAIN_RECS_CHANGED = str(RECORDS_FILE_RELATIVE) in [
            item.a_path for item in git_repo.index.diff(None)
        ] + [x.a_path for x in git_repo.head.commit.diff()]

        try:
            revlist = (
                (
                    commit.hexsha,
                    (commit.tree / str(RECORDS_FILE_RELATIVE)).data_stream.read(),
                )
                for commit in git_repo.iter_commits(paths=str(RECORDS_FILE_RELATIVE))
            )
            filecontents = list(revlist)[0][1]
        except IndexError:
            MAIN_RECS_CHANGED = False

        # If changes in RECORDS_FILE are staged, we need to detect the process type
        if MAIN_RECS_CHANGED:
            # Detect and validate transitions

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
                    for x in colrev_core.process.ProcessModel.transitions
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

        if not self.REVIEW_MANAGER.paths["RECORDS_FILE"].is_file():
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

    def get_instructions(self, *, stat: dict) -> dict:
        instructions = {
            "review_instructions": self.get_review_instructions(stat=stat),
            "environment_instructions": self.get_environment_instructions(stat=stat),
            "collaboration_instructions": self.REVIEW_MANAGER.get_collaboration_instructions(
                stat=stat
            ),
        }

        self.REVIEW_MANAGER.logger.debug(
            f"instructions: {self.REVIEW_MANAGER.pp.pformat(instructions)}"
        )
        return instructions

    def get_analytics(self) -> dict:

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

        keys = list(analytics_dict.values())[0].keys()

        with open("analytics.csv", "w", newline="", encoding="utf8") as output_file:
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
