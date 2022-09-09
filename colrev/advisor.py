#!/usr/bin/env python3
from __future__ import annotations

import typing
from collections import Counter
from multiprocessing.dummy import Pool as ThreadPool
from pathlib import Path
from typing import TYPE_CHECKING

import git
from git.exc import NoSuchPathError

if TYPE_CHECKING:
    import colrev.review_manager.ReviewManager


class Advisor:

    _next_step_description = {
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

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:

        self.review_manager = review_manager

    def get_collaboration_instructions(
        self, *, status_stats: colrev.ops.status.StatusStats = None
    ) -> dict:

        if status_stats is None:
            status_stats = self.review_manager.get_status_stats()

        share_stat_req = self.review_manager.settings.project.share_stat_req
        found_a_conflict = False

        git_repo = self.review_manager.dataset.get_repo()
        unmerged_blobs = git_repo.index.unmerged_blobs()
        for _, list_of_blobs in unmerged_blobs.items():
            for (stage, _) in list_of_blobs:
                if stage != 0:
                    found_a_conflict = True

        nr_commits_behind, nr_commits_ahead = 0, 0

        collaboration_instructions: dict = {"items": []}
        connected_remote = 0 != len(git_repo.remotes)
        if connected_remote:
            origin = git_repo.remotes.origin
            if origin.exists():
                (
                    nr_commits_behind,
                    nr_commits_ahead,
                ) = self.review_manager.dataset.get_remote_commit_differences()
        if connected_remote:
            collaboration_instructions["title"] = "Versioning and collaboration"
            collaboration_instructions["SHARE_STAT_REQ"] = share_stat_req
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
            if connected_remote:
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

                if share_stat_req == "NONE":
                    collaboration_instructions["status"] = {
                        "title": "Sharing: currently ready for sharing",
                        "level": "SUCCESS",
                        "msg": "",
                        # If consistency checks pass -
                        # if they didn't pass, the message wouldn't be displayed
                    }

                # TODO : all the following: should all search results be imported?!
                if share_stat_req == "PROCESSED":
                    if 0 == status_stats.currently.non_processed:
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
                if share_stat_req == "SCREENED":
                    # TODO : the following condition is probably not sufficient
                    if 0 == status_stats.currently.pdf_prepared:
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

                if share_stat_req == "COMPLETED":
                    if 0 == status_stats.currently.non_completed:
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
            if connected_remote:
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

    def get_review_instructions(
        self, *, status_stats: colrev.ops.status.StatusStats = None
    ) -> list:

        if status_stats is None:
            status_stats = self.review_manager.get_status_stats()

        review_instructions = []
        missing_files = self.review_manager.dataset.get_missing_files()
        current_origin_states_dict = self.review_manager.dataset.get_origin_state_dict()

        # If changes in RECORDS_FILE are staged, we need to detect the process type
        if self.review_manager.dataset.records_changed():
            # Detect and validate transitions
            transitioned_records = status_stats.get_transitioned_records(
                current_origin_states_dict=current_origin_states_dict
            )

            for transitioned_record in transitioned_records:
                if "no_source_state" == transitioned_record["dest"]:
                    print(f"Error (no source_state): {transitioned_record}")
                    review_instructions.append(
                        {
                            "msg": "Resolve committed colrev_status "
                            + f"of {transitioned_record}",
                            "priority": "yes",
                        }
                    )
                if "invalid_transition" == transitioned_record["process_type"]:
                    msg = (
                        f"Resolve invalid transition ({transitioned_record['ID']}): "
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

            in_progress_processes = status_stats.get_processes_in_progress(
                transitioned_records=transitioned_records
            )

            if len(in_progress_processes) == 1:
                instruction = {
                    "msg": f"Detected {in_progress_processes[0]} in progress. "
                    + "Complete this process",
                    "cmd": f"colrev {in_progress_processes[0]}",
                    "priority": "yes",
                }
                review_instructions.append(instruction)
            elif len(in_progress_processes) > 1:
                rec_str = ", ".join([x["ID"] for x in transitioned_records])
                instruction = {
                    "msg": "Detected multiple processes in progress "
                    + f"({', '.join(in_progress_processes)}). Complete one "
                    + "(save and revert the other) and commit before continuing!\n"
                    + f"  Records: {rec_str}",
                    # "cmd": f"colrev {in_progress_processes}",
                    "priority": "yes",
                }
                review_instructions.append(instruction)

        active_processing_functions = status_stats.get_active_processing_functions(
            current_origin_states_dict=current_origin_states_dict
        )

        priority_processing_functions = status_stats.get_priority_transition(
            current_origin_states_dict=current_origin_states_dict
        )

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

        if status_stats.currently.md_retrieved > 0:
            instruction = {
                "msg": self._next_step_description["load"],
                "cmd": "colrev load",
                "priority": "yes",
                # "high_level_cmd": "colrev metadata",
            }
            review_instructions.append(instruction)

        else:
            for active_processing_function in active_processing_functions:
                instruction = {
                    "msg": self._next_step_description[active_processing_function],
                    "cmd": f"colrev {active_processing_function.replace('_', '-')}"
                    # "high_level_cmd": "colrev metadata",
                }
                if active_processing_function in priority_processing_functions:
                    # keylist = [list(x.keys()) for x in review_instructions]
                    # keys = [item for sublist in keylist for item in sublist]
                    # if "priority" not in keys:
                    instruction["priority"] = "yes"
                else:
                    if self.review_manager.settings.project.delay_automated_processing:
                        continue
                if instruction["cmd"] not in [
                    ri["cmd"] for ri in review_instructions if "cmd" in ri
                ]:
                    review_instructions.append(instruction)

        if not self.review_manager.dataset.records_file.is_file():
            instruction = {
                "msg": "To import, copy search results to the search directory.",
                "cmd": "colrev load",
            }
            if instruction["cmd"] not in [
                ri["cmd"] for ri in review_instructions if "cmd" in ri
            ]:
                review_instructions.append(instruction)

        if (
            status_stats.completeness_condition
            and status_stats.currently.md_retrieved > 0
        ):
            if not self.review_manager.dataset.has_untracked_search_records():
                instruction = {
                    "info": "Iteration completed.",
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

        return review_instructions

    # Note : no named arguments for multiprocessing
    def append_registered_repo_instructions(self, registered_path: Path) -> dict:

        instruction = {}

        try:
            # Note : registered_path are other repositories (don't load from dataset.get_repo())
            git_repo = git.Repo(registered_path)

            # https://github.com/gitpython-developers/GitPython/issues/652#issuecomment-610511311
            origin = git_repo.remotes.origin

            if not origin.exists():
                raise AttributeError

            if git_repo.active_branch.tracking_branch() is None:
                raise AttributeError

            branch_name = str(git_repo.active_branch)
            tracking_branch_name = str(git_repo.active_branch.tracking_branch())
            self.review_manager.logger.debug(f"{branch_name} - {tracking_branch_name}")

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

            def pull_condition() -> bool:
                # behind_remote and not remote_ahead
                return nr_commits_behind > 0 and not nr_commits_ahead > 0

            def pull_rebase_condition() -> bool:
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

        except (AttributeError, NoSuchPathError):
            pass
        return instruction

    def get_environment_instructions(
        self, *, status_stats: colrev.ops.status.StatusStats
    ) -> list:

        environment_manager = self.review_manager.get_environment_manager()

        environment_instructions = []

        if status_stats.currently.md_imported > 10:
            with open(
                self.review_manager.dataset.records_file, encoding="utf8"
            ) as file:
                outlets = []
                for line in file.readlines():

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
                curated_outlets = environment_manager.get_curated_outlets()
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

        local_registry = environment_manager.load_local_registry()
        registered_paths = [Path(x["repo_source_path"]) for x in local_registry]
        # Note : we can use many parallel processes
        # because append_registered_repo_instructions mainly waits for the network
        # it does not use a lot of CPU capacity
        pool = ThreadPool(50)
        add_instructions = pool.map(
            self.append_registered_repo_instructions, registered_paths
        )

        environment_instructions += list(filter(None, add_instructions))

        if len(list(self.review_manager.corrections_path.glob("*.json"))) > 0:
            instruction = {
                "msg": "Corrections to share with curated repositories.",
                "cmd": "colrev push -r",
            }
            environment_instructions.append(instruction)

        return environment_instructions

    def get_instructions(
        self, *, status_stats: colrev.ops.status.StatusStats = None
    ) -> dict:

        if status_stats is None:
            status_stats = self.review_manager.get_status_stats()

        instructions = {
            "review_instructions": self.get_review_instructions(
                status_stats=status_stats
            ),
            "environment_instructions": self.get_environment_instructions(
                status_stats=status_stats
            ),
            "collaboration_instructions": self.get_collaboration_instructions(
                status_stats=status_stats
            ),
        }

        self.review_manager.logger.debug(
            f"instructions: {self.review_manager.p_printer.pformat(instructions)}"
        )
        return instructions

    def get_sharing_instructions(self) -> dict:

        collaboration_instructions = self.get_collaboration_instructions()

        status_code = not all(
            x["level"] in ["SUCCESS", "WARNING"]
            for x in collaboration_instructions["items"]
        )

        msgs = "\n ".join(
            [
                x["level"] + x["title"] + x.get("msg", "")
                for x in collaboration_instructions["items"]
            ]
        )
        return {"msg": msgs, "status": status_code}


if __name__ == "__main__":
    pass
