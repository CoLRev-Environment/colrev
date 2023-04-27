#! /usr/bin/env python
"""Checkers for CoLRev repositories"""
from __future__ import annotations

import os
import re
import sys
import typing
from importlib.metadata import version
from pathlib import Path

import yaml
from git.exc import InvalidGitRepositoryError

import colrev.exceptions as colrev_exceptions
import colrev.operation
from colrev.exit_codes import ExitCodes


if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.review_manager


class Checker:
    """The CoLRev checker makes sure the project setup is ok"""

    records: typing.Dict[str, typing.Any] = {}

    def __init__(
        self,
        *,
        review_manager: colrev.review_manager.ReviewManager,
    ) -> None:
        self.review_manager = review_manager

        self.review_manager.notified_next_operation = (
            colrev.operation.OperationsType.check
        )

    def get_colrev_versions(self) -> list[str]:
        """Get the colrev version as a list: (last_version, current_version)"""
        current_colrev_version = version("colrev")
        last_colrev_version = current_colrev_version
        last_colrev_version = self.review_manager.settings.project.colrev_version
        if last_colrev_version.endswith("."):
            last_colrev_version += "0"
        return [last_colrev_version, current_colrev_version]

    def __check_software(self) -> None:
        last_version, current_version = self.get_colrev_versions()
        if last_version != current_version:
            raise colrev_exceptions.CoLRevUpgradeError(last_version, current_version)
        if not sys.version_info > (2, 7):
            raise colrev_exceptions.CoLRevException("CoLRev does not support Python 2.")
        if sys.version_info < (3, 5):
            self.review_manager.logger.warning(
                "CoLRev uses Python 3.8 features (currently, %s is installed). Please upgrade.",
                sys.version_info,
            )

    def check_repository_setup(self) -> None:
        """Check the repository setup"""

        # 1. git repository?
        if not self.__is_git_repo():
            raise colrev_exceptions.RepoSetupError()

        # 2. colrev project?
        if not self.__is_colrev_project():
            raise colrev_exceptions.RepoSetupError(
                "No colrev repository."
                + "To retrieve a shared repository, use colrev init."
                + "To initalize a new repository, "
                + "execute the command in an empty directory."
            )

        # 3. Pre-commit hooks installed?
        self.__require_colrev_hooks_installed()

    @classmethod
    def in_virtualenv(cls) -> bool:
        """Check whether CoLRev operates in a virtual environment"""

        def get_base_prefix_compat() -> str:
            return (
                getattr(sys, "base_prefix", None)
                or getattr(sys, "real_prefix", None)
                or sys.prefix
            )

        return get_base_prefix_compat() != sys.prefix

    def __check_git_conflicts(self) -> None:
        # Note: when check is called directly from the command line.
        # pre-commit hooks automatically notify on merge conflicts

        git_repo = self.review_manager.dataset.get_repo()
        unmerged_blobs = git_repo.index.unmerged_blobs()

        for path, list_of_blobs in unmerged_blobs.items():
            for stage, _ in list_of_blobs:
                if stage != 0:
                    raise colrev_exceptions.GitConflictError(Path(path))

    def __is_git_repo(self) -> bool:
        try:
            if not (self.review_manager.path / Path(".git")).is_dir():
                return False
            _ = self.review_manager.dataset.get_repo().git_dir
            return True
        except InvalidGitRepositoryError:
            return False

    def __is_colrev_project(self) -> bool:
        required_paths = [
            Path(".pre-commit-config.yaml"),
            Path(".gitignore"),
            Path("settings.json"),
        ]
        if not all((self.review_manager.path / x).is_file() for x in required_paths):
            return False
        return True

    def __get_installed_hooks(self) -> list:
        installed_hooks = []
        with open(".pre-commit-config.yaml", encoding="utf8") as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.SafeLoader)
        for repository in pre_commit_config["repos"]:
            installed_hooks.extend([hook["id"] for hook in repository["hooks"]])
        return installed_hooks

    def __require_colrev_hooks_installed(self) -> bool:
        required_hooks = [
            "colrev-hooks-check",
            "colrev-hooks-format",
            "colrev-hooks-report",
            "colrev-hooks-share",
        ]
        installed_hooks = self.__get_installed_hooks()
        hooks_activated = set(required_hooks).issubset(set(installed_hooks))
        if not hooks_activated:
            missing_hooks = [x for x in required_hooks if x not in installed_hooks]
            raise colrev_exceptions.RepoSetupError(
                f"missing hooks in .pre-commit-config.yaml ({', '.join(missing_hooks)})"
            )

        if not self.review_manager.in_ci_environment():
            pch_file = Path(".git/hooks/pre-commit")
            if pch_file.is_file():
                with open(pch_file, encoding="utf8") as file:
                    if "File generated by pre-commit" not in file.read(4096):
                        raise colrev_exceptions.RepoSetupError(
                            "pre-commit hooks not installed (use pre-commit install)"
                        )
            else:
                raise colrev_exceptions.RepoSetupError(
                    "pre-commit hooks not installed (use pre-commit install)"
                )

            psh_file = Path(".git/hooks/pre-push")
            if psh_file.is_file():
                with open(psh_file, encoding="utf8") as file:
                    if "File generated by pre-commit" not in file.read(4096):
                        raise colrev_exceptions.RepoSetupError(
                            "pre-commit push hooks not installed "
                            "(use pre-commit install --hook-type pre-push)"
                        )
            else:
                raise colrev_exceptions.RepoSetupError(
                    "pre-commit push hooks not installed "
                    "(use pre-commit install --hook-type pre-push)"
                )

            pcmh_file = Path(".git/hooks/prepare-commit-msg")
            if pcmh_file.is_file():
                with open(pcmh_file, encoding="utf8") as file:
                    if "File generated by pre-commit" not in file.read(4096):
                        raise colrev_exceptions.RepoSetupError(
                            "pre-commit prepare-commit-msg hooks not installed "
                            "(use pre-commit install --hook-type prepare-commit-msg)"
                        )
            else:
                raise colrev_exceptions.RepoSetupError(
                    "pre-commit prepare-commit-msg hooks not installed "
                    "(use pre-commit install --hook-type prepare-commit-msg)"
                )

        return True

    def __retrieve_ids_from_bib(self, *, file_path: Path) -> list:
        assert file_path.suffix == ".bib"
        record_ids = []
        with open(file_path, encoding="utf8") as file:
            line = file.readline()
            while line:
                if "@" in line[:5]:
                    record_id = line[line.find("{") + 1 : line.rfind(",")]
                    record_ids.append(record_id.lstrip())
                line = file.readline()
        return record_ids

    def __check_colrev_origins(self, *, status_data: dict) -> None:
        """Check colrev_origins"""

        # Check whether each record has an origin
        if not len(status_data["entries_without_origin"]) == 0:
            raise colrev_exceptions.OriginError(
                f"Entries without origin: {', '.join(status_data['entries_without_origin'])}"
            )

        if (
            self.review_manager.dataset.records_changed()
            or self.review_manager.verbose_mode
        ):
            # Check for broken origins
            all_record_links = []
            for bib_file in self.review_manager.search_dir.glob("*.bib"):
                self.review_manager.logger.debug(bib_file)
                search_ids = self.__retrieve_ids_from_bib(file_path=bib_file)
                for search_id in search_ids:
                    all_record_links.append(bib_file.name + "/" + search_id)
            delta = set(status_data["record_links_in_bib"]) - set(all_record_links)
            if len(delta) > 0:
                raise colrev_exceptions.OriginError(f"broken origins: {delta}")

        # Check for non-unique origins
        non_unique_origins = []
        for origin, record_ids in status_data["origin_ID_list"].items():
            if len(record_ids) > 1:
                if not origin.startswith("md_"):
                    non_unique_origins.append(f"{origin} - {','.join(record_ids)}")
        if non_unique_origins:
            raise colrev_exceptions.OriginError(
                f'Non-unique origins: {" , ".join(set(non_unique_origins))}'
            )

    def check_fields(self, *, status_data: dict) -> None:
        """Check field values"""

        # Check status fields
        status_schema = colrev.record.RecordState
        stat_diff = set(status_data["status_fields"]).difference(status_schema)
        if stat_diff:
            raise colrev_exceptions.FieldValueError(
                f"status field(s) {stat_diff} not in {status_schema}"
            )

    def check_status_transitions(self, *, status_data: dict) -> None:
        """Check for invalid state transitions"""
        # Note : currently, we do not prevent particular transitions.
        # We may decide to provide settings parameters to apply
        # more restrictive rules related to valid transitions.

        # We allow particular combinations of multiple transitions
        # if len(set(status_data["start_states"])) > 1:
        #     raise colrev_exceptions.StatusTransitionError(
        #         "multiple transitions from different "
        #         f'start states ({set(status_data["start_states"])})'
        #     )

        # We may apply more restrictive criteria to prevent invalid_state_transitions
        # E.g., setting a record from rev_synthesized to rev_included should be ok.
        # if len(set(status_data["invalid_state_transitions"])) > 0:
        #     raise colrev_exceptions.StatusTransitionError(
        #         "invalid state transitions: \n    "
        #         + "\n    ".join(status_data["invalid_state_transitions"])
        #     )

    def __check_records_screen(self, *, status_data: dict) -> None:
        """Check consistency of screening criteria and status"""

        # pylint: disable=too-many-branches

        # Check screen
        # Note: consistency of inclusion_2=yes -> inclusion_1=yes
        # is implicitly ensured through status
        # (screen2-included/excluded implies prescreen included!)

        field_errors = []

        if status_data["screening_criteria_list"]:
            screening_criteria = self.review_manager.settings.screen.criteria
            if not screening_criteria:
                criteria = ["NA"]
                pattern = "^NA$"
                pattern_inclusion = "^NA$"
            else:
                pattern = "=(in|out);".join(screening_criteria.keys()) + "=(in|out)"
                pattern_inclusion = "=in;".join(screening_criteria.keys()) + "=in"

            for [record_id, status, screen_crit] in status_data[
                "screening_criteria_list"
            ]:
                if status not in colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.rev_included
                ):
                    assert "NA" == screen_crit
                    continue

                # print([record_id, status, screen_crit])
                if not re.match(pattern, screen_crit):
                    # Note: this should also catch cases of missing
                    # screening criteria
                    field_errors.append(
                        "Screening criteria field not matching "
                        f"pattern: {screen_crit} ({record_id}; criteria: {criteria})"
                    )

                elif str(colrev.record.RecordState.rev_excluded) == status:
                    if ["NA"] == criteria:
                        if screen_crit == "NA":
                            continue
                        field_errors.append(f"screen_crit field not NA: {screen_crit}")

                    if "=out" not in screen_crit:
                        self.review_manager.logger.error("criteria: %s", criteria)
                        field_errors.append(
                            "Excluded record with no screening_criterion violated: "
                            f"{record_id}, {status}, {screen_crit}"
                        )

                # Note: we don't have to consider the cases of
                # status=retrieved/prescreen_included/prescreen_excluded
                # because they would not have screening_criteria.
                elif status in [
                    str(colrev.record.RecordState.rev_included),
                    str(colrev.record.RecordState.rev_synthesized),
                ]:
                    if not re.match(pattern_inclusion, screen_crit):
                        field_errors.append(
                            "Included record with screening_criterion satisfied: "
                            f"{record_id}, {status}, {screen_crit}"
                        )
                else:
                    if status == colrev.record.RecordState.rev_excluded:
                        continue
                    if not re.match(pattern_inclusion, screen_crit):
                        field_errors.append(
                            "Record with screening_criterion but before "
                            f"screen: {record_id}, {status}"
                        )
        if field_errors:
            raise colrev_exceptions.FieldValueError(
                "\n    " + "\n    ".join(field_errors)
            )

    def __check_change_in_propagated_id_in_file(
        self,
        *,
        notifications: list,
        root: str,
        filename: str,
        prior_id: str,
        new_id: str,
    ) -> None:
        if prior_id == str(Path(filename).name):
            msg = (
                f"Old ID ({prior_id}, changed to {new_id} in the "
                + f"RECORDS_FILE) found in filepath: {filename}"
            )
            if msg not in notifications:
                notifications.append(msg)

        # self.review_manager.logger.debug("Checking %s", name)
        if filename.endswith(".bib"):
            retrieved_ids = self.__retrieve_ids_from_bib(
                file_path=Path(os.path.join(root, filename))
            )
            if prior_id in retrieved_ids:
                msg = (
                    f"Old ID ({prior_id}, changed to {new_id} in "
                    + f"the RECORDS_FILE) found in file: {filename}"
                )
                if msg not in notifications:
                    notifications.append(msg)
        else:
            with open(os.path.join(root, filename), encoding="utf8") as file:
                line = file.readline()
                while line:
                    if filename.endswith(".bib") and "@" in line[:5]:
                        line = file.readline()
                    if prior_id in line:
                        msg = (
                            f"Old ID ({prior_id}, to {new_id} in "
                            + f"the RECORDS_FILE) found in file: {filename}"
                        )
                        if msg not in notifications:
                            notifications.append(msg)
                    line = file.readline()

    def check_change_in_propagated_id(
        self, *, prior_id: str, new_id: str = "TBD", project_context: Path
    ) -> list:
        """Check whether propagated IDs were changed

        A propagated ID is a record ID that is stored outside the records.bib.
        Propagated IDs should not be changed in the records.bib
        because this would break the link between the propagated ID and its metadata.
        """

        ignore_patterns = [
            ".git",
            ".report.log",
            ".pre-commit-config.yaml",
            "data/search",
        ]

        text_formats = [".txt", ".csv", ".md", ".bib", ".yaml"]
        notifications: typing.List[str] = []
        for root, dirs, files in os.walk(project_context, topdown=False):
            for filename in files:
                if any(
                    (x in filename) or (x in root) for x in ignore_patterns
                ) or not any(filename.endswith(x) for x in text_formats):
                    # self.review_manager.logger.debug("Skipping %s", name)
                    continue
                self.__check_change_in_propagated_id_in_file(
                    notifications=notifications,
                    root=root,
                    filename=filename,
                    prior_id=prior_id,
                    new_id=new_id,
                )

            for dir_name in dirs:
                if any((x in dir_name) or (x in root) for x in ignore_patterns):
                    continue
                if prior_id in dir_name:
                    notifications.append(
                        f"Old ID ({prior_id}, changed to {new_id} in the "
                        f"RECORDS_FILE) found in filepath: {dir_name}"
                    )
        return notifications

    def __check_change_in_propagated_ids(
        self, *, prior: dict, status_data: dict
    ) -> None:
        """Check for changes in propagated IDs"""

        if "persisted_IDs" not in prior:
            return
        for prior_origin, prior_id in prior["persisted_IDs"]:
            if prior_origin not in status_data["origin_ID_list"]:
                # Note: this does not catch origins removed before md_processed
                raise colrev_exceptions.OriginError(f"origin removed: {prior_origin}")
            new_ids = status_data["origin_ID_list"][prior_origin]
            if prior_id not in new_ids:
                notifications = self.check_change_in_propagated_id(
                    prior_id=prior_id,
                    new_id=",".join(new_ids),
                    project_context=self.review_manager.path,
                )
                notifications.append(
                    "ID of processed record changed from "
                    f"{prior_id} to {','.join(new_ids)}"
                )
                raise colrev_exceptions.PropagatedIDChange(notifications)

    def check_sources(self) -> None:
        """Check the sources"""
        for source in self.review_manager.settings.sources:
            if not source.filename.is_file():
                self.review_manager.logger.debug(
                    f"Search details without file: {source.filename}"
                )

    def __retrieve_prior(self) -> dict:
        prior: dict = {"colrev_status": [], "persisted_IDs": []}
        prior_records = next(self.review_manager.dataset.load_records_from_history())
        for prior_record in prior_records.values():
            for orig in prior_record["colrev_origin"]:
                prior["colrev_status"].append([orig, prior_record["colrev_status"]])
                if prior_record[
                    "colrev_status"
                ] in colrev.record.RecordState.get_post_x_states(
                    state=colrev.record.RecordState.md_processed
                ):
                    prior["persisted_IDs"].append([orig, prior_record["ID"]])
        return prior

    def __get_status_transitions(
        self,
        *,
        record_id: str,
        origin: list,
        prior: dict,
        status: colrev.record.RecordState,
        status_data: dict,
    ) -> dict:
        prior_status = []
        if "colrev_status" in prior:
            prior_status = [
                stat for (org, stat) in prior["colrev_status"] if org in origin
            ]

        status_transition = {}
        if len(prior_status) == 0:
            status_transition[record_id] = "load"
        else:
            proc_transition_list: list = [
                x["trigger"]
                for x in colrev.record.RecordStateModel.transitions
                if str(x["source"]) == prior_status[0] and str(x["dest"]) == status
            ]
            if len(proc_transition_list) == 0 and prior_status[0] != status:
                status_data["start_states"].append(prior_status[0])
                if prior_status[0] not in colrev.record.RecordState:
                    raise colrev_exceptions.StatusFieldValueError(
                        record_id, "colrev_status", prior_status[0]
                    )
                if status not in colrev.record.RecordState:
                    raise colrev_exceptions.StatusFieldValueError(
                        record_id, "colrev_status", str(status)
                    )

                status_data["invalid_state_transitions"].append(
                    f"{record_id}: {prior_status[0]} to {status}"
                )
            if 0 == len(proc_transition_list):
                status_transition[record_id] = "load"
            else:
                proc_transition = proc_transition_list.pop()
                status_transition[record_id] = proc_transition
        return status_transition

    def __retrieve_status_data(self, *, prior: dict, records: dict) -> dict:
        status_data: dict = {
            "pdf_not_exists": [],
            "status_fields": [],
            "status_transitions": [],
            "start_states": [],
            "screening_criteria_list": [],
            "IDs": [],
            "entries_without_origin": [],
            "record_links_in_bib": [],
            "persisted_IDs": [],
            "origin_ID_list": {},
            "invalid_state_transitions": [],
        }

        for record_dict in records.values():
            status_data["IDs"].append(record_dict["ID"])

            for org in record_dict["colrev_origin"]:
                if org in status_data["origin_ID_list"]:
                    status_data["origin_ID_list"][org].append(record_dict["ID"])
                else:
                    status_data["origin_ID_list"][org] = [record_dict["ID"]]

            post_md_processed_states = colrev.record.RecordState.get_post_x_states(
                state=colrev.record.RecordState.md_processed
            )
            if record_dict["colrev_status"] in post_md_processed_states:
                for origin_part in record_dict["colrev_origin"]:
                    status_data["persisted_IDs"].append(
                        [origin_part, record_dict["ID"]]
                    )

            if "file" in record_dict:
                if Path(record_dict["file"]).is_file():
                    status_data["pdf_not_exists"].append(record_dict["ID"])

            if [] != record_dict.get("colrev_origin", []):
                for org in record_dict["colrev_origin"]:
                    status_data["record_links_in_bib"].append(org)
            else:
                status_data["entries_without_origin"].append(record_dict["ID"])

            status_data["status_fields"].append(record_dict["colrev_status"])

            if "screening_criteria" in record_dict:
                ec_case = [
                    record_dict["ID"],
                    record_dict["colrev_status"],
                    record_dict["screening_criteria"],
                ]
                status_data["screening_criteria_list"].append(ec_case)

            status_transition = self.__get_status_transitions(
                record_id=record_dict["ID"],
                origin=record_dict["colrev_origin"],
                prior=prior,
                status=record_dict["colrev_status"],
                status_data=status_data,
            )

            status_data["status_transitions"].append(status_transition)

        return status_data

    def check_repo_basics(self) -> list:
        """Calls data.main() to update the stats"""

        data_operation = self.review_manager.get_data_operation(
            notify_state_transition_operation=False
        )

        if self.review_manager.dataset.records_file.is_file():
            self.records = self.review_manager.dataset.load_records_dict()

        check_scripts: list[dict[str, typing.Any]] = []
        data_checks = [
            {
                "script": data_operation.main,
                "params": {"records": self.records, "silent_mode": True},
            },
            {
                "script": self.review_manager.update_status_yaml,
                "params": {"records": self.records},
            },
        ]

        check_scripts.extend(data_checks)

        failure_items = []
        for check_script in check_scripts:
            try:
                # self.review_manager.logger.info(check_script["script"])
                if not check_script["params"]:
                    # self.review_manager.logger.debug(
                    #     "%s() called", check_script["script"].__name__
                    # )
                    check_script["script"]()
                else:
                    # self.review_manager.logger.debug(
                    #     "%s(params) called", check_script["script"].__name__
                    # )
                    if isinstance(check_script["params"], list):
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](**check_script["params"])
                # self.review_manager.logger.debug(
                #     "%s: passed\n", check_script["script"].__name__
                # )
            except (
                colrev_exceptions.MissingDependencyError,
                colrev_exceptions.GitConflictError,
                colrev_exceptions.PropagatedIDChange,
                colrev_exceptions.DuplicateIDsError,
                colrev_exceptions.OriginError,
                colrev_exceptions.FieldValueError,
                colrev_exceptions.StatusTransitionError,
                colrev_exceptions.UnstagedGitChangesError,
                colrev_exceptions.StatusFieldValueError,
            ) as exc:
                failure_items.append(f"{type(exc).__name__}: {exc}")
        return failure_items

    def check_repo_extended(self) -> list:
        """Calls all checks that require prior data (take longer)"""

        # pylint: disable=not-a-mapping

        self.records: typing.Dict[str, typing.Any] = {}
        if self.review_manager.dataset.records_file.is_file():
            self.records = self.review_manager.dataset.load_records_dict()

        # We work with exceptions because each issue may be raised in different checks.
        # Currently, linting is limited for the scripts.

        environment_manager = self.review_manager.get_environment_manager()
        check_scripts: list[dict[str, typing.Any]] = [
            {
                "script": environment_manager.check_git_installed,
                "params": [],
            },
            {
                "script": environment_manager.check_docker_installed,
                "params": [],
            },
            {"script": self.__check_git_conflicts, "params": []},
            {"script": self.check_repository_setup, "params": []},
            {"script": self.__check_software, "params": []},
        ]

        if self.review_manager.dataset.records_file.is_file():
            if self.review_manager.dataset.file_in_history(
                filepath=self.review_manager.dataset.RECORDS_FILE_RELATIVE
            ):
                prior = self.__retrieve_prior()
                self.review_manager.logger.debug("prior")
                self.review_manager.logger.debug(
                    self.review_manager.p_printer.pformat(prior)
                )
            else:  # if RECORDS_FILE not yet in git history
                prior = {}

            status_data = self.__retrieve_status_data(prior=prior, records=self.records)

            main_refs_checks = [
                {"script": self.check_sources, "params": []},
            ]
            # Note : duplicate record IDs are already prevented by pybtex...

            if prior:  # if RECORDS_FILE in git history
                main_refs_checks.extend(
                    [
                        {
                            "script": self.__check_colrev_origins,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.__check_change_in_propagated_ids,
                            "params": {"prior": prior, "status_data": status_data},
                        },
                        {
                            "script": self.check_status_transitions,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.__check_records_screen,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self.check_fields,
                            "params": {"status_data": status_data},
                        },
                    ]
                )

            check_scripts.extend(main_refs_checks)

        failure_items = []
        for check_script in check_scripts:
            try:
                # self.review_manager.logger.info(check_script["script"])
                if not check_script["params"]:
                    # self.review_manager.logger.debug(
                    #     "%s() called", check_script["script"].__name__
                    # )
                    check_script["script"]()
                else:
                    # self.review_manager.logger.debug(
                    #     "%s(params) called", check_script["script"].__name__
                    # )
                    if isinstance(check_script["params"], list):
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](**check_script["params"])
                # self.review_manager.logger.debug(
                #     "%s: passed\n", check_script["script"].__name__
                # )
            except (
                colrev_exceptions.MissingDependencyError,
                colrev_exceptions.GitConflictError,
                colrev_exceptions.PropagatedIDChange,
                colrev_exceptions.DuplicateIDsError,
                colrev_exceptions.OriginError,
                colrev_exceptions.FieldValueError,
                colrev_exceptions.StatusTransitionError,
                colrev_exceptions.UnstagedGitChangesError,
                colrev_exceptions.StatusFieldValueError,
            ) as exc:
                failure_items.append(f"{type(exc).__name__}: {exc}")
        return failure_items

    def check_repo(self) -> dict:
        """Check whether the repository is in a consistent state
        Entrypoint for pre-commit hooks
        """

        failure_items = []
        failure_items.extend(self.check_repo_extended())
        failure_items.extend(self.check_repo_basics())

        if failure_items:
            return {"status": ExitCodes.FAIL, "msg": "  " + "\n  ".join(failure_items)}
        return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}


if __name__ == "__main__":
    pass
