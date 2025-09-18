#!/usr/bin/env python3
"""Dataset class providing functionality for data/records.bib and git repository."""
from __future__ import annotations

import os
import tempfile
import typing
from pathlib import Path

import colrev.exceptions as colrev_exceptions
import colrev.loader.bib
import colrev.loader.load_utils
import colrev.ops.check
import colrev.record.record_id_setter
import colrev.record.record_prep
from colrev.constants import ExitCodes
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.git_repo import GitRepo
from colrev.writer.write_utils import to_string

# pylint: disable=too-many-public-methods


class Dataset:
    """The CoLRev dataset (records and their history in git)"""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        self.review_manager = review_manager
        self.git_repo = GitRepo(path=review_manager.path)

    def get_origin_state_dict(self, records_string: str = "") -> dict:
        """Get the origin_state_dict (to determine state transitions efficiently)

        {'30_example_records.bib/Staehr2010': <RecordState.pdf_not_available: 10>,}
        """

        current_origin_states_dict = {}
        if records_string != "":
            with tempfile.NamedTemporaryFile(
                mode="wb", delete=False, suffix=".bib"
            ) as temp_file:
                temp_file.write(records_string.encode("utf-8"))
                temp_file_path = Path(temp_file.name)
            bib_loader = colrev.loader.bib.BIBLoader(
                filename=temp_file_path,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
        else:
            bib_loader = colrev.loader.bib.BIBLoader(
                filename=self.review_manager.paths.records,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
        for record_header_item in bib_loader.get_record_header_items().values():
            for origin in record_header_item[Fields.ORIGIN]:
                current_origin_states_dict[origin] = record_header_item[Fields.STATUS]
        return current_origin_states_dict

    def get_committed_origin_state_dict(self) -> dict:
        """Get the committed origin_state_dict"""
        revlist = (
            (
                commit.hexsha,
                (
                    commit.tree / self.review_manager.paths.RECORDS_FILE_GIT
                ).data_stream.read(),
            )
            for commit in self.git_repo.repo.iter_commits(
                paths=self.review_manager.paths.RECORDS_FILE_GIT
            )
        )
        filecontents = list(revlist)[0][1]

        committed_origin_state_dict = self.get_origin_state_dict(
            filecontents.decode("utf-8")
        )
        return committed_origin_state_dict

    def load_records_from_history(self, commit_sha: str = "") -> typing.Iterator[dict]:
        """
        Iterates through Git history, yielding records file contents as dictionaries.

        Starts iteration from a provided commit SHA.
        Skips commits where the records file is unchanged.
        Useful for tracking dataset changes over time.

        Parameters:
            commit_sha (str, optional): Start iteration from this commit SHA.
            Defaults to beginning of Git history if not provided.

        Yields:
            dict: Records file contents at a specific Git history point, as a dictionary.
        """

        reached_target_commit = False  # if no commit_sha provided
        for current_commit in self.git_repo.repo.iter_commits(
            paths=self.review_manager.paths.RECORDS_FILE_GIT
        ):

            # Skip all commits before the specified commit_sha, if provided
            if commit_sha and not reached_target_commit:
                if commit_sha != current_commit.hexsha:
                    # Move to the next commit
                    continue
                reached_target_commit = True

            # Read and parse the records file from the current commit
            filecontents = (
                current_commit.tree / self.review_manager.paths.RECORDS_FILE_GIT
            ).data_stream.read()

            records_dict = colrev.loader.load_utils.loads(
                load_string=filecontents.decode("utf-8", "replace"),
                implementation="bib",
                logger=self.review_manager.logger,
            )
            if records_dict:
                yield records_dict

    def load_records_dict(
        self,
        *,
        header_only: bool = False,
    ) -> dict[str, dict[str, typing.Any]]:
        """Load the records

        header_only:

        {"Staehr2010": {'ID': 'Staehr2010',
        'colrev_origin': ['30_example_records.bib/Staehr2010'],
        'colrev_status': <RecordState.md_imported: 2>,
        'screening_criteria': 'criterion1=in;criterion2=out',
        'file': PosixPath('data/pdfs/Smith2000.pdf'),
        'colrev_data_provenance': {Fields.AUTHOR:{"source":"...", "note":"..."}}},
        }
        """

        if self.review_manager.notified_next_operation is None:
            raise colrev_exceptions.ReviewManagerNotNotifiedError()

        if header_only:
            # Note : currently not parsing screening_criteria to settings.ScreeningCriterion
            # to optimize performance
            bib_loader = colrev.loader.bib.BIBLoader(
                filename=self.review_manager.paths.records,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )
            return bib_loader.get_record_header_items()

        if self.review_manager.paths.records.is_file():

            records_dict = colrev.loader.load_utils.load(
                filename=self.review_manager.paths.records,
                logger=self.review_manager.logger,
                unique_id_field="ID",
            )

        else:
            records_dict = {}

        return records_dict

    def save_records_dict_to_file(self, records: dict) -> None:
        """Save the records dict"""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = to_string(records_dict=records, implementation="bib")

        with open(self.review_manager.paths.records, "w", encoding="utf-8") as out:
            out.write(bibtex_str + "\n")

        self.git_repo.add_changes(self.review_manager.paths.RECORDS_FILE)

    def _save_record_list_by_id(self, records: dict) -> None:

        parsed = to_string(records_dict=records, implementation="bib")
        record_list = [
            {
                Fields.ID: item[item.find("{") + 1 : item.find(",")],
                "record": "@" + item + "\n",
            }
            for item in parsed.split("\n@")
        ]
        # Correct the first item
        record_list[0]["record"] = "@" + record_list[0]["record"][2:]

        current_id_str = "NOTSET"
        if self.review_manager.paths.records.is_file():
            with open(self.review_manager.paths.records, "r+b") as file:
                seekpos = file.tell()
                line = file.readline()
                while line:
                    if b"@" in line[:3]:
                        current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                        current_id_str = current_id.decode("utf-8")
                    if current_id_str in [x[Fields.ID] for x in record_list]:
                        replacement = [
                            x["record"]
                            for x in record_list
                            if x[Fields.ID] == current_id_str
                        ][0]
                        record_list = [
                            x for x in record_list if x[Fields.ID] != current_id_str
                        ]
                        line = file.readline()
                        while (
                            b"@" not in line[:3] and line
                        ):  # replace: drop the current record
                            line = file.readline()
                        remaining = line + file.read()
                        file.seek(seekpos)
                        file.write(replacement.encode("utf-8"))
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)

                    seekpos = file.tell()
                    line = file.readline()

        if len(record_list) > 0:
            with open(
                self.review_manager.paths.records, "a", encoding="utf8"
            ) as m_refs:
                for item in record_list:
                    m_refs.write(item["record"])

        self.git_repo.add_changes(self.review_manager.paths.RECORDS_FILE)

    def save_records_dict(self, records: dict, *, partial: bool = False) -> None:
        """Save the records dict in RECORDS_FILE"""
        if not records:
            return
        if partial:
            self._save_record_list_by_id(records)
            return
        self.save_records_dict_to_file(records)

    def read_next_record(self, *, conditions: list) -> typing.Iterator[dict]:
        """Read records (Iterator) based on condition"""

        # Note : matches conditions connected with 'OR'
        records = self.load_records_dict()

        records_list = []
        for _, record in records.items():
            for condition in conditions:
                for key, value in condition.items():
                    if str(value) == str(record[key]):
                        records_list.append(record)
        yield from records_list

    def format_records_file(self) -> dict:
        """Format the records file (Entrypoint for pre-commit hooks)"""

        if (
            not self.review_manager.paths.records.is_file()
            or not self.git_repo.records_changed()
        ):
            return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

        colrev.ops.check.CheckOperation(self.review_manager)  # to notify
        quality_model = self.review_manager.get_qm()
        records = self.load_records_dict()
        for record_dict in records.values():
            if Fields.STATUS not in record_dict:
                return {
                    "status": ExitCodes.FAIL,
                    "msg": f" no status field in record ({record_dict[Fields.ID]})",
                }

            record = colrev.record.record_prep.PrepRecord(record_dict)
            if record_dict[Fields.STATUS] in [
                RecordState.md_needs_manual_preparation,
            ]:
                record.run_quality_model(quality_model, set_prepared=True)

            if record_dict[Fields.STATUS] == RecordState.pdf_prepared:
                record.reset_pdf_provenance_notes()

        self.save_records_dict(records)
        changed = self.review_manager.paths.RECORDS_FILE in [
            r.a_path for r in self.git_repo.repo.index.diff(None)
        ]
        self.review_manager.update_status_yaml()
        self.review_manager.load_settings()
        self.review_manager.save_settings()

        if changed:  # pragma: no cover
            return {"status": ExitCodes.FAIL, "msg": "Records formatted"}

        return {"status": ExitCodes.SUCCESS, "msg": "Everything ok."}

    def reset_log_if_no_changes(self) -> None:
        """Reset the report log file if there are not changes"""
        if not self.git_repo.repo.is_dirty():
            self.review_manager.reset_report_logger()

    # ID creation, update and lookup ---------------------------------------

    def propagated_id(self, *, record_id: str) -> bool:
        """Check whether an ID is propagated (i.e., its record's status is beyond md_processed)"""

        for record in self.load_records_dict(header_only=True).values():
            if record[Fields.ID] == record_id:
                if record[Fields.STATUS] in RecordState.get_post_x_states(
                    state=RecordState.md_processed
                ):
                    return True

        return False

    def set_ids(self, selected_ids: typing.Optional[list] = None) -> dict:
        """Set the IDs of records according to predefined formats or
        according to the LocalIndex"""
        id_setter = colrev.record.record_id_setter.IDSetter(
            id_pattern=self.review_manager.settings.project.id_pattern,
            skip_local_index=self.review_manager.settings.is_curated_masterdata_repo(),
        )
        records = self.load_records_dict()
        updated_records = id_setter.set_ids(
            records=records,
            selected_ids=selected_ids,
        )
        self.save_records_dict(records)
        self.git_repo.add_changes(self.review_manager.paths.RECORDS_FILE)
        return updated_records
