#!/usr/bin/env python3
"""Advises users on the workflow (operations and collaboration)."""
from __future__ import annotations

import typing
from collections import Counter
from multiprocessing.dummy import Pool as ThreadPool
from pathlib import Path
from typing import Optional

import git
from git.exc import InvalidGitRepositoryError
from git.exc import NoSuchPathError

import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager.ReviewManager


class Advisor:
    """The CoLRev advisor guides users through the review process"""

    _next_step_description = {
        "retrieve": "Next step: retrieve metadata",
        "load": "Next step: Import search results",
        "prep": "Next step: Prepare records",
        "prep_man": "Next step: Prepare records (manually)",
        "dedupe": "Next step: Deduplicate records",
        "prescreen": "Next step: Prescreen records",
        "pdfs": "Next step: retrieve pdfs",
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

    def __append_merge_conflict_warning(
        self, *, collaboration_instructions: dict, git_repo: git.Repo
    ) -> None:
        found_a_conflict = False
        unmerged_blobs = git_repo.index.unmerged_blobs()
        for _, list_of_blobs in unmerged_blobs.items():
            for stage, _ in list_of_blobs:
                if stage != 0:
                    found_a_conflict = True
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

    def __notify_non_staged_files(
        self, *, collaboration_instructions: dict, git_repo: git.Repo
    ) -> None:
        # Notify when changes in bib files are not staged
        # (this may raise unexpected errors)

        non_staged = [
            item.a_path
            for item in git_repo.index.diff(None)
            if item.a_path[-4:] == ".bib"
        ]
        if len(non_staged) > 0:
            item = {
                "title": f"Non-staged changes: {','.join(non_staged)}",
                "level": "WARNING",
            }
            collaboration_instructions["items"].append(item)

    def __add_sharing_notifications(
        self,
        *,
        collaboration_instructions: dict,
        status_stats: colrev.ops.status.StatusStats,
    ) -> None:
        # pylint: disable=too-many-branches

        share_stat_req = self.review_manager.settings.project.share_stat_req
        collaboration_instructions["SHARE_STAT_REQ"] = share_stat_req

        if self.review_manager.dataset.behind_remote():
            item = {
                "title": "Remote changes available on the server",
                "level": "WARNING",
                "msg": "Once you have committed your changes, get the latest "
                + "remote changes",
                "cmd_after": "git add FILENAME \n  git commit -m 'MSG' \n  "
                + "git pull --rebase",
            }
            collaboration_instructions["items"].append(item)

        if self.review_manager.dataset.remote_ahead():
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

        if share_stat_req == "PROCESSED":
            if (
                0 == status_stats.currently.md_retrieved
                and 0 == status_stats.currently.md_imported
                and 0 == status_stats.currently.md_needs_manual_preparation
                and 0 == status_stats.currently.md_prepared
            ):
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
        # pylint: disable=too-many-boolean-expressions
        if share_stat_req == "SCREENED":
            if (
                0 == status_stats.currently.md_retrieved
                and 0 == status_stats.currently.md_imported
                and 0 == status_stats.currently.md_needs_manual_preparation
                and 0 == status_stats.currently.md_prepared
                and 0 == status_stats.currently.md_processed
                and 0 == status_stats.currently.rev_prescreen_included
                and 0 == status_stats.currently.pdf_needs_manual_retrieval
                and 0 == status_stats.currently.pdf_imported
                and 0 == status_stats.currently.pdf_needs_manual_preparation
                and 0 == status_stats.currently.pdf_prepared
            ):
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

    def __get_collaboration_instructions(
        self, *, status_stats: Optional[colrev.ops.status.StatusStats] = None
    ) -> dict:
        """Get instructions related to collaboration"""

        if status_stats is None:
            status_stats = self.review_manager.get_status_stats()

        collaboration_instructions: dict = {"items": []}
        git_repo = self.review_manager.dataset.get_repo()

        remote_connected = 0 != len(git_repo.remotes)
        if remote_connected:
            collaboration_instructions["title"] = "Versioning and collaboration"
        else:
            collaboration_instructions[
                "title"
            ] = "Versioning (not connected to shared repository)"
            item = {
                "title": "Project not yet shared",
                "level": "WARNING",
                "msg": "Please visit  https://github.com/new\n  "
                + "create an empty repository called  "
                + f"<USERNAME>/{self.review_manager.settings.project.title}\n  "
                + "and run git remote add origin  <REMOTE_URL>\n  git push origin main",
            }
            collaboration_instructions["items"].append(item)

        self.__append_merge_conflict_warning(
            collaboration_instructions=collaboration_instructions, git_repo=git_repo
        )
        if len(collaboration_instructions["items"]) > 0:
            # Don't append any other instructions.
            # Resolving the merge conflict is always prio 1
            return collaboration_instructions

        self.__notify_non_staged_files(
            collaboration_instructions=collaboration_instructions, git_repo=git_repo
        )

        if remote_connected:
            self.__add_sharing_notifications(
                collaboration_instructions=collaboration_instructions,
                status_stats=status_stats,
            )

        if 0 == len(collaboration_instructions["items"]):
            item = {
                "title": "Up-to-date",
                "level": "SUCCESS",
            }
            collaboration_instructions["items"].append(item)

        return collaboration_instructions

    def __append_initial_load_instruction(self, *, review_instructions: list) -> None:
        if not self.review_manager.dataset.records_file.is_file():
            instruction = {
                "msg": "To import, copy search results to the search directory.",
                "cmd": "colrev load",
            }
            if instruction["cmd"] not in [
                ri["cmd"] for ri in review_instructions if "cmd" in ri
            ]:
                review_instructions.append(instruction)

    def __append_operation_in_progress_instructions(
        self,
        *,
        review_instructions: list,
        status_stats: colrev.ops.status.StatusStats,
        current_origin_states_dict: dict,
    ) -> None:
        # If changes in RECORDS_FILE are staged, we need to detect the process type
        if self.review_manager.dataset.records_changed():
            # Detect and validate transitions
            transitioned_records = status_stats.get_transitioned_records(
                current_origin_states_dict=current_origin_states_dict
            )

            for transitioned_record in transitioned_records:
                if transitioned_record["dest"] == "no_source_state":
                    print(f"Error (no source_state): {transitioned_record}")
                    review_instructions.append(
                        {
                            "msg": "Resolve committed colrev_status "
                            + f"of {transitioned_record}",
                            "priority": "yes",
                        }
                    )
                if transitioned_record["operations_type"] == "invalid_transition":
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

            in_progress_processes = status_stats.get_operation_in_progress(
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
                rec_str = ", ".join([x["origin"] for x in transitioned_records])
                instruction = {
                    "msg": "Detected multiple processes in progress "
                    + f"({', '.join(in_progress_processes)}). Complete one "
                    + "(save and revert the other) and commit before continuing!\n"
                    + f"  Records: {rec_str}",
                    # "cmd": f"colrev {in_progress_processes}",
                    "priority": "yes",
                }
                review_instructions.append(instruction)

    def __append_initial_operations(
        self, *, review_instructions: list, status_stats: colrev.ops.status.StatusStats
    ) -> bool:
        if not Path(self.review_manager.search_dir).iterdir():
            instruction = {
                "msg": "Add search results to data/search",
                "priority": "yes",
            }
            review_instructions.append(instruction)
            return True

        if status_stats.overall.md_retrieved == 0:
            instruction = {
                "msg": self._next_step_description["retrieve"],
                "cmd": "colrev retrieve",
                "priority": "yes",
            }
            review_instructions.append(instruction)
            return True

        if status_stats.currently.md_retrieved > 0:
            instruction = {
                "msg": self._next_step_description["retrieve"],
                "cmd": "colrev retrieve",
                "priority": "yes",
            }
            review_instructions.append(instruction)

            if not self.review_manager.verbose_mode:
                return True
        return False

    def __append_active_operations(
        self,
        *,
        status_stats: colrev.ops.status.StatusStats,
        current_origin_states_dict: dict,
        review_instructions: list,
    ) -> None:
        active_operations = status_stats.get_active_operations(
            current_origin_states_dict=current_origin_states_dict
        )

        priority_processing_operations = status_stats.get_priority_operations(
            current_origin_states_dict=current_origin_states_dict
        )

        for active_operation in active_operations:
            if active_operation in ["load", "prep", "dedupe"]:
                instruction = {
                    "msg": self._next_step_description["retrieve"],
                    "cmd": "colrev retrieve",
                }
            if active_operation in ["pdf_get", "pdf_prep"]:
                instruction = {
                    "msg": self._next_step_description["pdfs"],
                    "cmd": "colrev pdfs",
                }
            else:
                instruction = {
                    "msg": self._next_step_description[active_operation],
                    "cmd": f"colrev {active_operation.replace('_', '-')}",
                }
            if active_operation in priority_processing_operations:
                # keylist = [list(x.keys()) for x in review_instructions]
                # keys = [item for sublist in keylist for item in sublist]
                # if "priority" not in keys:
                instruction["priority"] = "yes"
            else:
                if (
                    self.review_manager.settings.project.delay_automated_processing
                    and not self.review_manager.verbose_mode
                ):
                    continue
            if instruction["cmd"] not in [
                ri["cmd"] for ri in review_instructions if "cmd" in ri
            ]:
                review_instructions.append(instruction)

    def __append_data_operation_advice(self, *, review_instructions: list) -> None:
        if (
            len(review_instructions) == 1
            or self.review_manager.verbose_mode
            or self.review_manager.settings.is_curated_masterdata_repo()
        ):
            if (
                "colrev data" in [ri["cmd"] for ri in review_instructions]
                or self.review_manager.settings.is_curated_masterdata_repo()
            ):
                for item in review_instructions.copy():
                    if item.get("cmd") == "colrev data":
                        review_instructions.remove(item)
                        break

                # review_instructions.pop(0)

                package_manager = self.review_manager.get_package_manager()
                check_operation = colrev.operation.CheckOperation(
                    review_manager=self.review_manager
                )
                for (
                    data_package_endpoint
                ) in self.review_manager.settings.data.data_package_endpoints:
                    endpoint_dict = package_manager.load_packages(
                        package_type=colrev.env.package_manager.PackageEndpointType.data,
                        selected_packages=[data_package_endpoint],
                        operation=check_operation,
                    )
                    endpoint = endpoint_dict[data_package_endpoint["endpoint"]]

                    advice = endpoint.get_advice(self.review_manager)  # type: ignore
                    if advice:
                        review_instructions.append(advice)

    def __append_next_operation_instructions(
        self,
        *,
        review_instructions: list,
        status_stats: colrev.ops.status.StatusStats,
        current_origin_states_dict: dict,
    ) -> None:
        if self.__append_initial_operations(
            review_instructions=review_instructions, status_stats=status_stats
        ):
            return

        self.__append_active_operations(
            status_stats=status_stats,
            current_origin_states_dict=current_origin_states_dict,
            review_instructions=review_instructions,
        )

        self.__append_data_operation_advice(review_instructions=review_instructions)

    def __get_missing_files(
        self, *, status_stats: colrev.ops.status.StatusStats
    ) -> list:
        # excluding pdf_not_available
        file_required_status = [
            colrev.record.RecordState.pdf_imported,
            colrev.record.RecordState.pdf_needs_manual_preparation,
            colrev.record.RecordState.pdf_prepared,
            colrev.record.RecordState.rev_excluded,
            colrev.record.RecordState.rev_included,
            colrev.record.RecordState.rev_synthesized,
        ]
        missing_files = []
        for record_dict in status_stats.records.values():
            if (
                record_dict["colrev_status"] in file_required_status
                and "file" not in record_dict
            ):
                missing_files.append(record_dict["ID"])

        return missing_files

    def __append_pdf_issue_instructions(
        self, *, status_stats: colrev.ops.status.StatusStats, review_instructions: list
    ) -> None:
        # Check pdf files
        if self.review_manager.settings.pdf_get.pdf_required_for_screen_and_synthesis:
            missing_files = self.__get_missing_files(status_stats=status_stats)
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

        pdfs_no_longer_available = []
        for record_dict in status_stats.records.values():
            if "file" in record_dict:
                if not (self.review_manager.path / Path(record_dict["file"])).is_file():
                    pdfs_no_longer_available.append(record_dict["file"])
        if pdfs_no_longer_available:
            review_instructions.append(
                {
                    "level": "WARNING",
                    "msg": f"PDF no longer available: {','.join(pdfs_no_longer_available)}",
                    "cmd": "colrev repare",
                }
            )

    def __append_iteration_completed_instructions(
        self, *, review_instructions: list, status_stats: colrev.ops.status.StatusStats
    ) -> None:
        if (
            status_stats.completeness_condition
            and status_stats.currently.md_retrieved > 0
        ):
            if not self.review_manager.dataset.has_untracked_search_records():
                instruction = {
                    "info": "Review iteration completed.",
                    "msg": "To start the next iteration of the review, "
                    + "add new search results (to data/search)",
                }
                review_instructions.append(instruction)
            else:
                instruction = {
                    "info": "Search results available for next iteration.",
                    "msg": "Next step: Import search results.",
                    "cmd": "colrev load",
                }
                review_instructions.append(instruction)

    def get_review_instructions(
        self, *, status_stats: Optional[colrev.ops.status.StatusStats] = None
    ) -> list:
        """Get instructions related to the review (operations)"""

        if status_stats is None:
            status_stats = self.review_manager.get_status_stats()

        review_instructions: typing.List[typing.Dict] = []
        current_origin_states_dict = self.review_manager.dataset.get_origin_state_dict()

        self.__append_initial_load_instruction(review_instructions=review_instructions)

        self.__append_operation_in_progress_instructions(
            review_instructions=review_instructions,
            status_stats=status_stats,
            current_origin_states_dict=current_origin_states_dict,
        )

        self.__append_next_operation_instructions(
            review_instructions=review_instructions,
            status_stats=status_stats,
            current_origin_states_dict=current_origin_states_dict,
        )

        self.__append_pdf_issue_instructions(
            status_stats=status_stats, review_instructions=review_instructions
        )

        self.__append_iteration_completed_instructions(
            review_instructions=review_instructions, status_stats=status_stats
        )

        return review_instructions

    # Note : no named arguments for multiprocessing
    def __append_registered_repo_instructions(self, registered_path: Path) -> dict:
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
            # self.review_manager.logger.debug(f"{branch_name} - {tracking_branch_name}")

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
                        "cmd": "colrev env --pull",
                    }

                elif pull_rebase_condition():
                    instruction = {
                        "msg": "Local/remote branch diverged for curated repo "
                        f"({registered_path}).",
                        "cmd": f"cd '{registered_path}' && git pull --rebase",
                    }

        except (AttributeError, NoSuchPathError, InvalidGitRepositoryError):
            pass
        return instruction

    def __append_download_outlets_instruction(
        self,
        environment_manager: colrev.env.environment_manager.EnvironmentManager,
        environment_instructions: list,
    ) -> None:
        """Get instructions related to downloading outlets (resources)"""

        # pylint: disable=too-many-locals

        with open(self.review_manager.dataset.records_file, encoding="utf8") as file:
            outlets = []
            for line in file.readlines():
                if line.lstrip()[:7] == "journal":
                    journal = line[line.find("{") + 1 : line.rfind("}")]
                    outlets.append(journal)
                if line.lstrip()[:9] == "booktitle":
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
                    "https://github.com/CoLRev-curations",
                }
                environment_instructions.append(instruction)

    def __get_environment_instructions(
        self, *, status_stats: colrev.ops.status.StatusStats
    ) -> list:
        """Get instructions related to the CoLRev environment"""

        environment_manager = self.review_manager.get_environment_manager()

        environment_instructions: list[dict] = []

        if status_stats.currently.md_imported > 10:
            self.__append_download_outlets_instruction(
                environment_manager=environment_manager,
                environment_instructions=environment_instructions,
            )

        environment_registry = environment_manager.load_environment_registry()
        registered_paths = [Path(x["repo_source_path"]) for x in environment_registry]
        # Note : we can use many parallel processes
        # because __append_registered_repo_instructions mainly waits for the network
        # it does not use a lot of CPU capacity
        pool = ThreadPool(50)
        add_instructions = pool.map(
            self.__append_registered_repo_instructions, registered_paths
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
        self, *, status_stats: Optional[colrev.ops.status.StatusStats] = None
    ) -> dict:
        """Get all instructions on the project"""

        if status_stats is None:
            status_stats = self.review_manager.get_status_stats()

        instructions = {
            "review_instructions": self.get_review_instructions(
                status_stats=status_stats
            ),
            "environment_instructions": self.__get_environment_instructions(
                status_stats=status_stats
            ),
            "collaboration_instructions": self.__get_collaboration_instructions(
                status_stats=status_stats
            ),
        }
        # self.review_manager.logger.debug(
        #     f"instructions: {self.review_manager.p_printer.pformat(instructions)}"
        # )
        return instructions

    def get_sharing_instructions(self) -> dict:
        """Get instructions related to sharing the project"""

        collaboration_instructions = self.__get_collaboration_instructions()

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
