#!/usr/bin/env python3
"""Advises users on the workflow (operations and collaboration)."""
from __future__ import annotations

import typing
from collections import Counter
from multiprocessing.dummy import Pool as ThreadPool
from pathlib import Path

import git
from git.exc import InvalidGitRepositoryError
from git.exc import NoSuchPathError

import colrev.ops.check
import colrev.process.operation
from colrev.constants import EndpointType
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager


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
        self.status_stats = review_manager.get_status_stats()
        self.environment_manager = self.review_manager.get_environment_manager()

    def _append_merge_conflict_warning(
        self, collaboration_instructions: dict, *, git_repo: git.Repo
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

    def _notify_non_staged_files(
        self, collaboration_instructions: dict, *, git_repo: git.Repo
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

    def _add_sharing_notifications(
        self,
        collaboration_instructions: dict,
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
                0 == self.status_stats.currently.md_retrieved
                and 0 == self.status_stats.currently.md_imported
                and 0 == self.status_stats.currently.md_needs_manual_preparation
                and 0 == self.status_stats.currently.md_prepared
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
            if self.status_stats.completeness_condition:
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
            if 0 == self.status_stats.currently.non_completed:
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

    # pylint: disable=colrev-missed-constant-usage
    def _get_collaboration_instructions(self) -> dict:
        """Get instructions related to collaboration"""

        collaboration_instructions: dict = {"items": []}
        git_repo = self.review_manager.dataset.get_repo()

        remote_connected = 0 != len(git_repo.remotes)
        if remote_connected:
            collaboration_instructions["title"] = "Versioning and collaboration"
        else:
            collaboration_instructions["title"] = (
                "Versioning (not connected to shared repository)"
            )
            item = {
                "title": "Project not yet shared",
                "level": "WARNING",
                "msg": "Please visit  https://github.com/new\n  "
                + "create an empty repository called  "
                + f"<USERNAME>/{self.review_manager.settings.project.title}\n  "
                + "and run git remote add origin  <REMOTE_URL>\n  git push origin main",
            }
            collaboration_instructions["items"].append(item)

        self._append_merge_conflict_warning(
            collaboration_instructions, git_repo=git_repo
        )
        if len(collaboration_instructions["items"]) > 0:
            # Don't append any other instructions.
            # Resolving the merge conflict is always prio 1
            return collaboration_instructions

        self._notify_non_staged_files(collaboration_instructions, git_repo=git_repo)

        if remote_connected:
            self._add_sharing_notifications(collaboration_instructions)

        if 0 == len(collaboration_instructions["items"]):
            item = {
                "title": "Up-to-date",
                "level": "SUCCESS",
            }
            collaboration_instructions["items"].append(item)

        return collaboration_instructions

    def _append_initial_load_instruction(self, review_instructions: list) -> None:
        current_origin_states_dict = self.review_manager.dataset.get_origin_state_dict()
        if len(current_origin_states_dict) == 0:
            instruction = {
                "msg": "To import, copy search results to the search directory.",
                "cmd": "colrev load",
            }
            if instruction["cmd"] not in [
                ri["cmd"] for ri in review_instructions if "cmd" in ri
            ]:
                review_instructions.append(instruction)

    def _append_operation_in_progress_instructions(
        self, review_instructions: list
    ) -> None:
        # If changes in RECORDS_FILE are staged, we need to detect the process type
        if self.review_manager.dataset.records_changed():
            # Detect and validate transitions
            transitioned_records = self.status_stats.get_transitioned_records()

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
                if transitioned_record["type"] == "invalid_transition":
                    msg = (
                        f"Resolve invalid transition ({transitioned_record['origin']}): "
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

            in_progress_processes = self.status_stats.get_operation_in_progress(
                transitioned_records=transitioned_records
            )

            if len(in_progress_processes) == 1:
                instruction = {
                    "msg": f"Detected {list(in_progress_processes)[0]} in progress. "
                    + "Complete this process",
                    "cmd": f"colrev {list(in_progress_processes)[0]}",
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
                    "priority": "yes",
                }
                review_instructions.append(instruction)

    def _append_initial_operations(self, review_instructions: list) -> bool:
        search_dir = self.review_manager.paths.search
        if not Path(search_dir).iterdir():
            instruction = {
                "msg": "Add search results to data/search",
                "priority": "yes",
            }
            review_instructions.append(instruction)
            return True

        if self.status_stats.overall.md_retrieved == 0:
            instruction = {
                "msg": self._next_step_description["retrieve"],
                "cmd": "colrev retrieve",
                "priority": "yes",
            }
            review_instructions.append(instruction)
            return True

        if self.status_stats.currently.md_retrieved > 0:
            instruction = {
                "msg": self._next_step_description["retrieve"],
                "cmd": "colrev retrieve",
                "priority": "yes",
            }
            review_instructions.append(instruction)

            if not self.review_manager.verbose_mode:
                return True
        return False

    def _append_active_operations(self, review_instructions: list) -> None:

        active_operations = self.status_stats.get_active_operations()
        priority_processing_operations = self.status_stats.get_priority_operations()

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
                    "msg": self._next_step_description[str(active_operation)],
                    "cmd": f"colrev {str(active_operation).replace('_', '-')}",
                }
            if active_operation in priority_processing_operations:
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

    def _append_data_operation_advice(self, review_instructions: list) -> None:
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

                package_manager = self.review_manager.get_package_manager()
                check_operation = colrev.ops.check.CheckOperation(self.review_manager)
                for (
                    data_package_endpoint
                ) in self.review_manager.settings.data.data_package_endpoints:

                    data_class = package_manager.get_package_endpoint_class(
                        package_type=EndpointType.data,
                        package_identifier=data_package_endpoint["endpoint"],
                    )

                    endpoint = data_class(
                        data_operation=check_operation, settings=data_package_endpoint
                    )

                    advice = endpoint.get_advice()  # type: ignore
                    if advice:
                        review_instructions.append(advice)

    def _append_next_operation_instructions(
        self,
        review_instructions: list,
    ) -> None:
        if self._append_initial_operations(review_instructions):
            return

        self._append_active_operations(review_instructions)
        self._append_data_operation_advice(review_instructions)

    def _get_missing_files(self) -> list:
        return [
            record_dict[Fields.ID]
            for record_dict in self.status_stats.records.values()
            if (
                record_dict[Fields.STATUS] in RecordState.get_states_requiring_file()
                and Fields.FILE not in record_dict
            )
        ]

    def _append_pdf_issue_instructions(self, review_instructions: list) -> None:
        # Check pdf files
        if self.review_manager.settings.pdf_get.pdf_required_for_screen_and_synthesis:
            missing_files = self._get_missing_files()
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
                        " Use\n    colrev pdf-get --relink_pdfs"
                    }
                )

        pdfs_no_longer_available = []
        for record_dict in self.status_stats.records.values():
            if Fields.FILE in record_dict:
                if not (
                    self.review_manager.path / Path(record_dict[Fields.FILE])
                ).is_file():
                    pdfs_no_longer_available.append(record_dict[Fields.FILE])
        if pdfs_no_longer_available:
            review_instructions.append(
                {
                    "level": "WARNING",
                    "msg": f"PDF no longer available: {','.join(pdfs_no_longer_available)}",
                    "cmd": "colrev repare",
                }
            )

    def _append_iteration_completed_instructions(
        self,
        review_instructions: list,
    ) -> None:
        if (
            self.status_stats.completeness_condition
            and self.status_stats.currently.md_retrieved > 0
        ):
            if not self.review_manager.dataset.has_untracked_search_records():
                instruction = {
                    "info": "Review iteration completed.",
                    "msg": "To start the next iteration of the review, run the search",
                    "cmd": "colrev search",
                }
                review_instructions.append(instruction)
            else:
                instruction = {
                    "info": "Search results available for next iteration.",
                    "msg": "Next step: Import search results.",
                    "cmd": "colrev load",
                }
                review_instructions.append(instruction)

    # Note : no named arguments for multiprocessing
    def _append_registered_repo_instructions(self, registered_path: Path) -> dict:
        instruction = {}

        def pull_condition(nr_commits_behind: int, nr_commits_ahead: int) -> bool:
            # behind_remote and not remote_ahead
            return nr_commits_behind > 0 and not nr_commits_ahead > 0

        def pull_rebase_condition(
            nr_commits_behind: int, nr_commits_ahead: int
        ) -> bool:
            # behind_remote and remote_ahead
            return nr_commits_behind > 0 and nr_commits_ahead > 0

        try:
            # Note : registered_path are other repositories (don't load from dataset.get_repo())
            git_repo = git.Repo(registered_path)
            # https://github.com/gitpython-developers/GitPython/issues/652#issuecomment-610511311
            origin = git_repo.remotes.origin

            if not origin.exists() or git_repo.active_branch.tracking_branch() is None:
                raise AttributeError

            branch_name = str(git_repo.active_branch)
            tracking_branch_name = str(git_repo.active_branch.tracking_branch())

            behind_operation = branch_name + ".." + tracking_branch_name
            commits_behind = git_repo.iter_commits(behind_operation)
            nr_commits_behind = sum(1 for c in commits_behind)

            ahead_operation = tracking_branch_name + ".." + branch_name
            commits_ahead = git_repo.iter_commits(ahead_operation)
            nr_commits_ahead = sum(1 for c in commits_ahead)

            # Note: do not use named arguments (multiprocessing)
            if not Path(registered_path).is_dir():
                instruction = {
                    "msg": "Locally registered repo no longer exists.",
                    "cmd": f"colrev env --unregister {registered_path}",
                }

            elif "curated_metadata" in str(registered_path):
                if pull_condition(nr_commits_behind, nr_commits_ahead):
                    instruction = {
                        "msg": "Updates available for curated repo "
                        f"({registered_path}).",
                        "cmd": "colrev env --pull",
                    }

                elif pull_rebase_condition(nr_commits_behind, nr_commits_ahead):
                    instruction = {
                        "msg": "Local/remote branch diverged for curated repo "
                        f"({registered_path}).",
                        "cmd": f"cd '{registered_path}' && git pull --rebase",
                    }

        except (AttributeError, NoSuchPathError, InvalidGitRepositoryError):
            pass
        return instruction

    def _extract_outlet_count(self) -> typing.Tuple[list, list]:
        with open(self.review_manager.paths.records, encoding="utf8") as file:
            outlets = []
            for line in file.readlines():
                if line.lstrip()[:8] == "journal ":
                    journal = line[line.find("{") + 1 : line.rfind("}")]
                    outlets.append(journal)
                if line.lstrip()[:10] == "booktitle ":
                    booktitle = line[line.find("{") + 1 : line.rfind("}")]
                    outlets.append(booktitle)

        outlet_counter: typing.List[typing.Tuple[str, int]] = [
            (j, x) for j, x in Counter(outlets).most_common(10) if x > 5
        ]

        return outlets, outlet_counter

    def _append_download_outlets_instruction(
        self,
        environment_instructions: list,
    ) -> None:
        """Get instructions related to downloading outlets (resources)"""

        outlets, outlet_counter = self._extract_outlet_count()

        selected = []
        cumulative = 0.0
        for candidate, freq in outlet_counter:
            selected.append((candidate, freq))
            cumulative += freq / len(outlets)
            if cumulative > 0.7:
                break
        if len(selected) > 0:
            curated_outlets = self.environment_manager.get_curated_outlets()
            selected_journals = [
                (candidate, freq)
                for candidate, freq in selected
                if candidate not in curated_outlets + ["", FieldValues.UNKNOWN]
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

    def _get_environment_instructions(self) -> list:
        """Get instructions related to the CoLRev environment"""

        environment_instructions: list[dict] = []
        if self.status_stats.currently.md_imported > 10:
            self._append_download_outlets_instruction(environment_instructions)

        local_repos = self.environment_manager.local_repos()
        registered_paths = [Path(x["repo_source_path"]) for x in local_repos]
        # Note : we can use many parallel processes
        # because __append_registered_repo_instructions mainly waits for the network
        # it does not use a lot of CPU capacity
        pool = ThreadPool(50)
        add_instructions = pool.map(
            self._append_registered_repo_instructions, registered_paths
        )

        environment_instructions += list(filter(None, add_instructions))

        corrections_path = self.review_manager.paths.corrections
        if len(list(corrections_path.glob("*.json"))) > 0:
            instruction = {
                "msg": "Corrections to share with curated repositories.",
                "cmd": "colrev push -r",
            }
            environment_instructions.append(instruction)

        return environment_instructions

    def get_review_instructions(self) -> list:
        """Get instructions related to the review (operations)"""
        review_instructions: typing.List[typing.Dict] = []
        self._append_initial_load_instruction(review_instructions)
        self._append_operation_in_progress_instructions(review_instructions)
        self._append_next_operation_instructions(review_instructions)
        self._append_pdf_issue_instructions(review_instructions)
        self._append_iteration_completed_instructions(review_instructions)
        return review_instructions

    def get_sharing_instructions(self) -> dict:
        """Get instructions related to sharing the project"""

        collaboration_instructions = self._get_collaboration_instructions()
        return {
            "msg": "\n ".join(
                [
                    x["level"] + x["title"] + x.get("msg", "")
                    for x in collaboration_instructions["items"]
                ]
            ),
            "status": not all(
                x["level"] in ["SUCCESS", "WARNING"]
                for x in collaboration_instructions["items"]
            ),
        }

    def get_instructions(self) -> dict:
        """Get all instructions on the project"""

        instructions = {
            "review_instructions": self.get_review_instructions(),
            "environment_instructions": self._get_environment_instructions(),
            "collaboration_instructions": self._get_collaboration_instructions(),
        }
        if self.review_manager.shell_mode:
            for category in instructions.values():
                for item in category:
                    if "cmd" in item:
                        item["cmd"] = item["cmd"].replace("colrev ", "")
        return instructions
