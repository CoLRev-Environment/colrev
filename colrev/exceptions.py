#! /usr/bin/env python
"""Exceptions of CoLRev."""
from __future__ import annotations

from pathlib import Path

import colrev.ui_cli.cli_colors as colors


class CoLRevException(Exception):
    """
    Base class for all exceptions raised by this package
    """


class RepoSetupError(CoLRevException):
    """
    The project files are not properly set up as a CoLRev project.
    """

    def __init__(self, msg: str) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


class CoLRevUpgradeError(CoLRevException):
    """
    The version of the local CoLRev package does not match with the CoLRev version
    used to create the latest commit in the project.
    An explicit upgrade of the data structures is needed.
    """

    def __init__(self, old: str, new: str) -> None:
        self.message = (
            f"Detected upgrade from {old} to {new}. To upgrade use\n     "
            f"{colors.ORANGE}colrev settings --upgrade{colors.END}"
        )
        super().__init__(self.message)


class ReviewManagerNotNofiedError(CoLRevException):
    """
    The ReviewManager was not notified about the operation.
    """

    def __init__(self) -> None:
        self.message = (
            "create a process and inform the review manager in advance"
            + " to avoid conflicts."
        )
        super().__init__(self.message)


class ParameterError(CoLRevException):
    """
    An invalid parameter was passed to CoLRev.
    """

    def __init__(self, *, parameter: str, value: str, options: list) -> None:
        options_string = "\n  - ".join(sorted(options))
        self.message = (
            f"Invalid parameter {parameter}: {value}.\n Options:\n  - {options_string}"
        )
        super().__init__(self.message)


class InvalidSettingsError(CoLRevException):
    """
    Invalid value in settings.json.
    """

    def __init__(self, *, msg: str) -> None:
        msg = (
            f"Error in settings.json: {msg}\n"
            "To solve this, use\n  "
            f"{colors.ORANGE}colrev settings --upgrade{colors.END}"
        )
        self.message = msg
        super().__init__(self.message)


# Valid commits, data structures, and repo states


class UnstagedGitChangesError(CoLRevException):
    """
    Unstaged git changes were found although a clean repository is required.
    """

    def __init__(self, changedFiles: list) -> None:
        self.message = (
            f"changes not yet staged: {changedFiles} (use git add . or stash)"
        )
        super().__init__(self.message)


class CleanRepoRequiredError(CoLRevException):
    """
    A clean git repository would be required.
    """

    def __init__(self, changedFiles: list, ignore_pattern: str) -> None:
        self.message = (
            "clean repository required (use git commit, discard or stash "
            + f"{changedFiles}; ignore_pattern={ignore_pattern})."
        )
        super().__init__(self.message)


class GitConflictError(CoLRevException):
    """
    There are git conflicts to be resolved before resuming operations.
    """

    def __init__(self, path: Path) -> None:
        self.message = f"please resolve git conflict in {path}"
        super().__init__(self.message)


class DirtyRepoAfterProcessingError(CoLRevException):
    """
    The git repository was not clean after completing the operation.
    """

    def __init__(self, msg: str) -> None:
        self.message = msg
        super().__init__(self.message)


class ProcessOrderViolation(CoLRevException):
    """The process triggered dooes not have priority"""

    def __init__(
        self,
        operations_type: str,
        required_state: str,
        violating_records: list,
    ) -> None:
        self.message = (
            f" {operations_type}() requires all records to have at least "
            + f"'{required_state}', but there are records with {violating_records}."
        )
        super().__init__(self.message)


class StatusTransitionError(CoLRevException):
    """An invalid status transition was observed"""

    def __init__(self, msg: str) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


class NoRecordsError(CoLRevException):
    """The operation cannot be started because no records have been imported yet."""

    def __init__(self) -> None:
        self.message = "no records imported yet"
        super().__init__(self.message)


class FieldValueError(CoLRevException):
    """An error in field values was detected (in the main records)."""

    def __init__(self, msg: str) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


class StatusFieldValueError(CoLRevException):
    """An error in the status field values was detected."""

    def __init__(self, record: str, status_type: str, status_value: str) -> None:
        self.message = f"{status_type} set to '{status_value}' in {record}."
        super().__init__(self.message)


class OriginError(CoLRevException):
    """An error in the colrev_origin field values was detected."""

    def __init__(self, msg: str) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


class DuplicateIDsError(CoLRevException):
    """Duplicate IDs were detected."""

    def __init__(self, msg: str) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


class NotEnoughDataToIdentifyException(CoLRevException):
    """The meta-data is not sufficiently complete to identify the record."""

    def __init__(self, msg: str = None) -> None:
        self.message = msg
        super().__init__(self.message)


class PropagatedIDChange(CoLRevException):
    """Changes in propagated records ID detected."""

    def __init__(self, notifications: list) -> None:
        self.message = "\n    ".join(notifications)
        super().__init__(self.message)


# Init


class NonEmptyDirectoryError(CoLRevException):
    """Trying to initialize CoLRev in a non-empty directory."""

    def __init__(self) -> None:
        self.message = "please change to an empty directory to initialize a project"
        super().__init__(self.message)


# Search


class InvalidQueryException(CoLRevException):
    """The query format is not valid."""

    def __init__(self, msg: str) -> None:
        self.message = msg
        super().__init__(self.message)


class SearchSettingsError(CoLRevException):
    """The search settings format is not valid."""

    def __init__(
        self,
        msg: str,
    ) -> None:
        self.message = f" {msg}"
        super().__init__(self.message)


class NoSearchFeedRegistered(CoLRevException):
    """No search feed endpoints registered in settings.json"""

    def __init__(self) -> None:
        super().__init__("No search feed endpoints registered in settings.json")


# Load


class ImportException(CoLRevException):
    """An error occured in the import functions."""


class UnsupportedImportFormatError(CoLRevException):
    """The file format is not supported."""

    def __init__(
        self,
        import_path: Path,
    ) -> None:
        self.import_path = import_path
        self.message = (
            "Format of search result file not (yet) supported "
            + f"({self.import_path.name}) "
        )
        super().__init__(self.message)


class BibFileFormatError(CoLRevException):
    """An error in the bib-file format was detected."""


# Dedupe


class DedupeError(Exception):
    """An exception in the dedupe operation"""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


# Data


class NoPaperEndpointRegistered(CoLRevException):
    """No paper endpoint registered in settings.json"""

    def __init__(self) -> None:
        self.message = "No paper endpoint registered in settings.json"
        super().__init__(self.message)


# Push


class RecordNotInRepoException(CoLRevException):
    """The record was not found in the main records."""

    def __init__(self, record_id: str = None) -> None:
        if id is not None:
            self.message = f"Record not in index ({record_id})"
        else:
            self.message = "Record not in index"
        super().__init__(self.message)


# PDF Hash service


class InvalidPDFException(CoLRevException):
    """The PDF is invalid (empty or broken)."""

    def __init__(self, path: Path) -> None:
        self.message = f"Invalid PDF (empty/broken): {path}"
        super().__init__(self.message)


# Environment services


class MissingDependencyError(CoLRevException):
    """The required dependency is not available."""

    def __init__(self, dep: str) -> None:
        self.message = f"{dep}"
        super().__init__(self.message)


class ServiceNotAvailableException(CoLRevException):
    """An environment service is not available."""

    def __init__(self, msg: str) -> None:
        self.message = msg
        super().__init__(f"Service not available: {self.message}")


class TEITimeoutException(CoLRevException):
    """A timeout occurred during TEI generation"""


class TEIException(CoLRevException):
    """An exception related to the TEI format"""


class RecordNotInIndexException(CoLRevException):
    """The requested record was not found in the LocalIndex."""

    def __init__(self, record_id: str = None) -> None:
        if id is not None:
            self.message = f"Record not in index ({record_id})"
        else:
            self.message = "Record not in index"
        super().__init__(self.message)


class RecordNotIndexedException(CoLRevException):
    """The requested record could not be added to the LocalIndex."""

    def __init__(self, record_id: str = None) -> None:
        if id is not None:
            self.message = f"Record not indexed ({record_id})"
        else:
            self.message = "Record not indexed"
        super().__init__(self.message)


class CuratedOutletNotUnique(CoLRevException):
    """The outlets (journals or conferences) with curated metadata are not unique."""

    def __init__(self, msg: str = None) -> None:
        self.message = msg
        super().__init__(self.message)
