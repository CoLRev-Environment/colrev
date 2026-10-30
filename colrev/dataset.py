#!/usr/bin/env python3
"""Dataset class providing functionality for data/records.bib and git repository."""

from __future__ import annotations

import typing
from functools import cached_property
from pathlib import Path

from bibliography_io import update
from bibliography_io import load_primary
from bibliography_io import loads_primary
from bibliography_io import to_string
from bibliography_io.exceptions import ParseError as BibliographyParseError

import colrev.exceptions as colrev_exceptions
import colrev.ops.check
import colrev.record.record_id_setter
import colrev.record.record_prep
from colrev.constants import ExitCodes
from colrev.constants import Fields
from colrev.constants import RecordState
from colrev.git_repo import GitRepo
from colrev.record.bibliography import adapt_bibliography_records

# pylint: disable=too-many-public-methods


def _load_primary_bibliography(
    *, path: Path | None = None, text: str | None = None
) -> dict[str, dict[str, typing.Any]]:
    """Load CoLRev BibTeX, decoding structured values and accepting legacy data."""
    options = {
        "mapping_fields": {Fields.MD_PROV, Fields.D_PROV},
        "list_fields": {Fields.ORIGIN},
    }
    try:
        if path is not None:
            records = load_primary(path, **options)
        elif text is not None:
            records = loads_primary(text, format="bib", **options)
        else:
            raise ValueError("Specify either path or text")
    except BibliographyParseError:
        # Older CoLRev files store provenance and origins as legacy strings.
        if path is not None:
            records = load_primary(path)
        elif text is not None:
            records = loads_primary(text, format="bib")
        else:  # pragma: no cover - validated above
            raise
    return adapt_bibliography_records(records)


class Dataset:
    """The CoLRev dataset (records and their history in git)."""

    def __init__(self, *, review_manager: colrev.review_manager.ReviewManager) -> None:
        """Initialize the instance."""
        self.review_manager = review_manager

    @cached_property
    def git_repo(self) -> GitRepo:
        """Get the GitRepo object for the review_manager path."""
        return GitRepo(path=self.review_manager.path)

    def get_origin_state_dict(self, records_string: str = "") -> dict:
        """Get the origin_state_dict (to determine state transitions efficiently).

        {'30_example_records.bib/Staehr2010': <RecordState.pdf_not_available: 10>,}
        """
        current_origin_states_dict = {}
        if records_string != "":
            records = _load_primary_bibliography(text=records_string)
        else:
            records = _load_primary_bibliography(path=self.review_manager.paths.records)
        for record_dict in records.values():
            for origin in record_dict.get(Fields.ORIGIN, []):
                current_origin_states_dict[origin] = record_dict[Fields.STATUS]
        return current_origin_states_dict

    def get_committed_origin_state_dict(self) -> dict:
        """Get the committed origin_state_dict."""
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
        """Iterates through Git history, yielding records file contents as dictionaries.

        Starts iteration from a provided commit SHA.
        Skips commits where the records file is unchanged.
        Useful for tracking dataset changes over time.

        Parameters
        ----------
            commit_sha (str, optional): Start iteration from this commit SHA.
            Defaults to beginning of Git history if not provided.

        Yields
        ------
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

            records_dict = _load_primary_bibliography(
                text=filecontents.decode("utf-8", "replace")
            )
            if records_dict:
                yield records_dict

    def load_records_dict(
        self,
        *,
        header_only: bool = False,
    ) -> dict[str, dict[str, typing.Any]]:
        """Load the records.

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
            # TODO: should the parsing of status also occur in bibliography-io???
            records = load_primary(
                self.review_manager.paths.records,
                header_only=True,
                list_fields=[Fields.ORIGIN],
                mapping_fields=[Fields.MD_PROV, Fields.D_PROV],
            )
            return adapt_bibliography_records(records)

        if self.review_manager.paths.records.is_file():

            records_dict = _load_primary_bibliography(
                path=self.review_manager.paths.records
            )

        else:
            records_dict = {}

        return records_dict

    def save_records_dict_to_file(self, records: dict) -> None:
        """Save the records dict."""
        # Note : this classmethod function can be called by CoLRev scripts
        # operating outside a CoLRev repo (e.g., sync)

        bibtex_str = to_string(
            records,
            format="bib",
            mapping_fields={Fields.MD_PROV, Fields.D_PROV},
            list_fields={Fields.ORIGIN},
        )

        with open(self.review_manager.paths.records, "w", encoding="utf-8") as out:
            out.write(bibtex_str + "\n")

        self.git_repo.add_changes(self.review_manager.paths.RECORDS_FILE)

    def _save_record_list_by_id(self, records: dict) -> None:

        update(
            self.review_manager.paths.records,
            records,
            mapping_fields={Fields.MD_PROV, Fields.D_PROV},
            list_fields={Fields.ORIGIN},
        )

        self.git_repo.add_changes(self.review_manager.paths.RECORDS_FILE)

    def save_records_dict(self, records: dict, *, partial: bool = False) -> None:
        """Save the records dict in RECORDS_FILE."""
        if not records:
            return
        if partial:
            self._save_record_list_by_id(records)
            return
        self.save_records_dict_to_file(records)

    def read_next_record(self, *, conditions: list) -> typing.Iterator[dict]:
        """Read records (Iterator) based on condition."""
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
        """Format the records file (Entrypoint for pre-commit hooks)."""
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
        """Reset the report log file if there are not changes."""
        if not self.git_repo.repo.is_dirty():
            self.review_manager.reset_report_logger()

    # ID creation, update and lookup ---------------------------------------

    def propagated_id(self, *, record_id: str) -> bool:
        """Check whether an ID is propagated (i.e., its record's status is beyond md_processed)."""
        for record in self.load_records_dict(header_only=True).values():
            if record[Fields.ID] == record_id:
                if record[Fields.STATUS] in RecordState.get_post_x_states(
                    state=RecordState.md_processed
                ):
                    return True

        return False

    def set_ids(self, selected_ids: typing.Optional[list] = None) -> dict:
        """Set the IDs of records according to predefined formats or
        according to the LocalIndex.
        """
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
