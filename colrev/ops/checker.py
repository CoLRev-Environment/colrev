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
from colrev.constants import ExitCodes
from colrev.constants import Fields
from colrev.constants import OperationsType
from colrev.constants import RecordState
from colrev.process.model import ProcessModel

if typing.TYPE_CHECKING:  # pragma: no cover
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
        self.review_manager.notified_next_operation = OperationsType.check

    def get_colrev_versions(self) -> list[str]:
        """Get the colrev version as a list: (last_version, current_version)"""
        current_colrev_version = version("colrev")
        last_colrev_version = current_colrev_version
        last_colrev_version = self.review_manager.settings.project.colrev_version
        if last_colrev_version.endswith("."):
            last_colrev_version += "0"
        return [last_colrev_version, current_colrev_version]

    def _check_software(self) -> None:
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
        if not self._is_git_repo():
            raise colrev_exceptions.RepoSetupError()

        # 2. colrev project?
        if not self._is_colrev_project():
            raise colrev_exceptions.RepoSetupError(
                "No colrev repository."
                + "To retrieve a shared repository, use colrev init."
                + "To initalize a new repository, "
                + "execute the command in an empty directory."
            )

        # 3. Pre-commit hooks installed?
        self._require_colrev_hooks_installed()

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

    def _check_git_conflicts(self) -> None:
        # Note: when check is called directly from the command line.
        # pre-commit hooks automatically notify on merge conflicts

        git_repo = self.review_manager.dataset.get_repo()
        unmerged_blobs = git_repo.index.unmerged_blobs()

        for path, list_of_blobs in unmerged_blobs.items():
            for stage, _ in list_of_blobs:
                if stage != 0:
                    raise colrev_exceptions.GitConflictError(Path(path))

    def _is_git_repo(self) -> bool:
        try:
            if not (self.review_manager.path / Path(".git")).is_dir():
                return False
            _ = self.review_manager.dataset.get_repo().git_dir
            return True
        except InvalidGitRepositoryError:
            return False

    def _is_colrev_project(self) -> bool:
        required_paths = [
            self.review_manager.paths.pre_commit_config,
            self.review_manager.paths.git_ignore,
            self.review_manager.paths.settings,
        ]
        if not all(x.is_file() for x in required_paths):
            return False
        return True

    def _get_installed_hooks(self) -> list:
        installed_hooks = []
        with open(
            self.review_manager.paths.pre_commit_config, encoding="utf8"
        ) as pre_commit_y:
            pre_commit_config = yaml.load(pre_commit_y, Loader=yaml.SafeLoader)
        for repository in pre_commit_config["repos"]:
            installed_hooks.extend([hook["id"] for hook in repository["hooks"]])
        return installed_hooks

    def _require_colrev_hooks_installed(self) -> bool:
        required_hooks = [
            "colrev-hooks-check",
            "colrev-hooks-format",
            "colrev-hooks-report",
            "colrev-hooks-share",
        ]
        installed_hooks = self._get_installed_hooks()
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

    def _retrieve_ids_from_bib(self, *, file_path: Path) -> list:
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

    def _check_colrev_origins(self, *, status_data: dict) -> None:
        """Check colrev_origins"""

        # Check whether each record has an origin
        if not len(status_data["entries_without_origin"]) == 0:
            raise colrev_exceptions.OriginError(
                f"Entries without origin: {', '.join(status_data['entries_without_origin'])}"
            )

        # if (
        #     self.review_manager.dataset.records_changed()
        #     or self.review_manager.verbose_mode
        # ):
        #     # Check for broken origins
        #     all_record_links = []
        #     for bib_file in self.review_manager.search_dir.glob("*.bib"):
        #         self.review_manager.logger.debug(bib_file)
        #         search_ids = self._retrieve_ids_from_bib(file_path=bib_file)
        #         for search_id in search_ids:
        #             all_record_links.append(bib_file.name + "/" + search_id)
        #     delta = set(status_data["record_links_in_bib"]) - set(all_record_links)
        #     if len(delta) > 0:
        #         raise colrev_exceptions.OriginError(f"broken origins: {delta}")

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
        status_schema = RecordState
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

    # pylint: disable=too-many-arguments
    def _check_individual_record_screen(
        self,
        *,
        record_id: str,
        status: RecordState,
        screen_crit: str,
        field_errors: typing.List[str],
        pattern: str,
        pattern_inclusion: str,
        criteria: typing.List[str],
    ) -> None:
        # No screening criteria allowed before screen
        if (
            status not in RecordState.get_post_x_states(state=RecordState.rev_included)
            and status != RecordState.md_needs_manual_preparation
        ):
            if "NA" != screen_crit:
                raise colrev_exceptions.FieldValueError(
                    f"{record_id}: screen_crit != NA ({screen_crit})"
                )
            return

        # All screening criteria must match pattern
        if not re.match(pattern, screen_crit):
            # Note: this should also catch cases of missing
            # screening criteria
            field_errors.append(
                "Screening criteria field not matching "
                f"pattern: {screen_crit} ({record_id}; criteria: {criteria})"
            )
            return

        # Included papers must match inclusion pattern
        if status in [
            RecordState.rev_included,
            RecordState.rev_synthesized,
        ]:
            if not re.match(pattern_inclusion, screen_crit):
                field_errors.append(
                    "Included record with screening_criterion satisfied: "
                    f"{record_id}, {status}, {screen_crit}"
                )
            return

        # Excluded papers must match exclusion pattern
        if status == RecordState.rev_excluded:
            if ["NA"] == criteria:
                if screen_crit == "NA":
                    return
                field_errors.append(f"screen_crit field not NA: {screen_crit}")

            if "=out" not in screen_crit:
                self.review_manager.logger.error("criteria: %s", criteria)
                field_errors.append(
                    "Excluded record with no screening_criterion violated: "
                    f"{record_id}, {status}, {screen_crit}"
                )

    def _check_records_screen(self, *, status_data: dict) -> None:
        """Check consistency of screening criteria and status"""

        if not status_data["screening_criteria_list"]:
            return

        field_errors: typing.List[str] = []

        screening_criteria = self.review_manager.settings.screen.criteria
        if not screening_criteria:
            criteria = ["NA"]
            pattern = "^NA$"
            pattern_inclusion = "^NA$"
        else:
            pattern = (
                "=(in|out|TODO);".join(screening_criteria.keys()) + "=(in|out|TODO)"
            )
            pattern_inclusion = "=in;".join(screening_criteria.keys()) + "=in"
            criteria = list(screening_criteria.keys())

        for [record_id, status, screen_crit] in status_data["screening_criteria_list"]:
            self._check_individual_record_screen(
                record_id=record_id,
                status=status,
                screen_crit=screen_crit,
                field_errors=field_errors,
                pattern=pattern,
                pattern_inclusion=pattern_inclusion,
                criteria=criteria,
            )

        if field_errors:
            raise colrev_exceptions.FieldValueError(
                "\n    " + "\n    ".join(field_errors)
            )

    # pylint: disable=too-many-arguments
    def _check_change_in_propagated_id_in_file(
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

        if filename.endswith(".bib"):
            retrieved_ids = self._retrieve_ids_from_bib(
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
            "records.bib",
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
                self._check_change_in_propagated_id_in_file(
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

    def _check_change_in_propagated_ids(
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

    def _retrieve_prior(self) -> dict:
        prior: dict = {Fields.STATUS: [], "persisted_IDs": []}
        prior_records = next(
            self.review_manager.dataset.load_records_from_history(), {}
        )
        for prior_record in prior_records.values():
            for orig in prior_record[Fields.ORIGIN]:
                prior[Fields.STATUS].append([orig, prior_record[Fields.STATUS]])
                if prior_record[Fields.STATUS] in RecordState.get_post_x_states(
                    state=RecordState.md_processed
                ):
                    prior["persisted_IDs"].append([orig, prior_record[Fields.ID]])
        return prior

    # pylint: disable=too-many-arguments
    def _get_status_transitions(
        self,
        *,
        record_id: str,
        origin: list,
        prior: dict,
        status: RecordState,
        status_data: dict,
    ) -> dict:
        prior_status = []
        if Fields.STATUS in prior:
            prior_status = [
                stat for (org, stat) in prior[Fields.STATUS] if org in origin
            ]

        status_transition = {}
        if len(prior_status) == 0:
            # pylint: disable=colrev-missed-constant-usage
            status_transition[record_id] = "load"
        else:
            proc_transition_list: list = [
                x["trigger"]
                for x in ProcessModel.transitions
                if str(x["source"]) == prior_status[0] and str(x["dest"]) == status
            ]
            if len(proc_transition_list) == 0 and prior_status[0] != status:
                status_data["start_states"].append(prior_status[0])
                if prior_status[0] not in RecordState:
                    raise colrev_exceptions.StatusFieldValueError(
                        record_id, Fields.STATUS, prior_status[0]
                    )
                if status not in RecordState:
                    raise colrev_exceptions.StatusFieldValueError(
                        record_id, Fields.STATUS, str(status)
                    )

                status_data["invalid_state_transitions"].append(
                    f"{record_id}: {prior_status[0]} to {status}"
                )
            if 0 == len(proc_transition_list):
                # pylint: disable=colrev-missed-constant-usage
                status_transition[record_id] = "load"
            else:
                proc_transition = proc_transition_list.pop()
                status_transition[record_id] = proc_transition
        return status_transition

    def _retrieve_status_data(self, *, prior: dict, records: dict) -> dict:
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
            status_data["IDs"].append(record_dict[Fields.ID])

            for org in record_dict[Fields.ORIGIN]:
                if org in status_data["origin_ID_list"]:
                    status_data["origin_ID_list"][org].append(record_dict[Fields.ID])
                else:
                    status_data["origin_ID_list"][org] = [record_dict[Fields.ID]]

            post_md_processed_states = RecordState.get_post_x_states(
                state=RecordState.md_processed
            )
            if record_dict[Fields.STATUS] in post_md_processed_states:
                for origin_part in record_dict[Fields.ORIGIN]:
                    status_data["persisted_IDs"].append(
                        [origin_part, record_dict[Fields.ID]]
                    )

            if Fields.FILE in record_dict:
                if Path(record_dict[Fields.FILE]).is_file():
                    status_data["pdf_not_exists"].append(record_dict[Fields.ID])

            if [] != record_dict.get(Fields.ORIGIN, []):
                for org in record_dict[Fields.ORIGIN]:
                    status_data["record_links_in_bib"].append(org)
            else:
                status_data["entries_without_origin"].append(record_dict[Fields.ID])

            status_data["status_fields"].append(record_dict[Fields.STATUS])

            if Fields.SCREENING_CRITERIA in record_dict:
                ec_case = [
                    record_dict[Fields.ID],
                    record_dict[Fields.STATUS],
                    record_dict[Fields.SCREENING_CRITERIA],
                ]
                status_data["screening_criteria_list"].append(ec_case)

            status_transition = self._get_status_transitions(
                record_id=record_dict[Fields.ID],
                origin=record_dict[Fields.ORIGIN],
                prior=prior,
                status=record_dict[Fields.STATUS],
                status_data=status_data,
            )

            status_data["status_transitions"].append(status_transition)

        return status_data

    def check_repo_basics(self) -> list:
        """Calls data.main() to update the stats"""

        data_operation = self.review_manager.get_data_operation(
            notify_state_transition_operation=False
        )
        records_file = self.review_manager.paths.records
        if records_file.is_file():
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
                if not check_script["params"]:
                    check_script["script"]()
                else:
                    if isinstance(check_script["params"], list):
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](**check_script["params"])
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
        if self.review_manager.paths.records.is_file():
            self.records = self.review_manager.dataset.load_records_dict()

        # We work with exceptions because each issue may be raised in different checks.
        # Currently, linting is limited for the scripts.

        environment_manager = self.review_manager.get_environment_manager()
        check_scripts: list[dict[str, typing.Any]] = [
            {
                "script": environment_manager.check_git_installed,
                "params": [],
            },
            {"script": self._check_git_conflicts, "params": []},
            {"script": self.check_repository_setup, "params": []},
            {"script": self._check_software, "params": []},
        ]

        if self.review_manager.paths.records.is_file():
            if self.review_manager.dataset.file_in_history(
                self.review_manager.paths.RECORDS_FILE
            ):
                prior = self._retrieve_prior()
                self.review_manager.logger.debug("prior")
                self.review_manager.logger.debug(
                    self.review_manager.p_printer.pformat(prior)
                )
            else:  # if RECORDS_FILE not yet in git history
                prior = {}

            status_data = self._retrieve_status_data(prior=prior, records=self.records)

            main_refs_checks = [
                {"script": self.check_sources, "params": []},
            ]
            # Note : duplicate record IDs are already prevented by pybtex...

            if prior:  # if RECORDS_FILE in git history
                main_refs_checks.extend(
                    [
                        {
                            "script": self._check_colrev_origins,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self._check_change_in_propagated_ids,
                            "params": {"prior": prior, "status_data": status_data},
                        },
                        {
                            "script": self.check_status_transitions,
                            "params": {"status_data": status_data},
                        },
                        {
                            "script": self._check_records_screen,
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
                if not check_script["params"]:
                    check_script["script"]()
                else:
                    if isinstance(check_script["params"], list):
                        check_script["script"](*check_script["params"])
                    else:
                        check_script["script"](**check_script["params"])
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
