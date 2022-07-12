#! /usr/bin/env python


class ImportException(Exception):
    def __init__(self, message):
        super().__init__(message)


class UnsupportedImportFormatError(Exception):
    def __init__(
        self,
        import_path,
    ):
        self.import_path = import_path
        self.message = (
            "Format of search result file not (yet) supported "
            + f"({self.import_path.name}) "
        )
        super().__init__(self.message)


class BibFileFormatError(Exception):
    def __init__(self, message):
        super().__init__(message)


class InvalidQueryException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(self.message)


class NoSearchFeedRegistered(Exception):
    """No search feed endpoints registered in settings.json"""

    def __init__(self):
        super().__init__("No search feed endpoints registered in settings.json")


class TEI_TimeoutException(Exception):
    pass


class TEI_Exception(Exception):
    pass


class RecordNotInIndexException(Exception):
    def __init__(self, id: str = None):
        if id is not None:
            self.message = f"Record not in index ({id})"
        else:
            self.message = "Record not in index"
        super().__init__(self.message)


class CuratedOutletNotUnique(Exception):
    def __init__(self, msg: str = None):
        self.message = msg
        super().__init__(self.message)


class ServiceNotAvailableException(Exception):
    def __init__(self, msg: str):
        self.message = msg
        super().__init__(f"Service not available: {self.message}")


class NonEmptyDirectoryError(Exception):
    def __init__(self):
        self.message = "please change to an empty directory to initialize a project"
        super().__init__(self.message)


class NoPaperEndpointRegistered(Exception):
    """No paper endpoint registered in settings.json"""

    def __init__(self):
        self.message = "No paper endpoint registered in settings.json"
        super().__init__(self.message)


class SearchDetailsError(Exception):
    def __init__(
        self,
        msg,
    ):
        self.message = f" {msg}"
        super().__init__(self.message)


class StatusTransitionError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class StatusFieldValueError(Exception):
    def __init__(self, record: str, status_type: str, status_value: str):
        self.message = f"{status_type} set to '{status_value}' in {record}."
        super().__init__(self.message)


class RecordFormatError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class CitationKeyPropagationError(Exception):
    pass


class DuplicatesError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class OriginError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class FieldError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class PropagatedIDChange(Exception):
    def __init__(self, notifications):
        self.message = "\n    ".join(notifications)
        super().__init__(self.message)


class ReviewManagerNotNofiedError(Exception):
    def __init__(self):
        self.message = (
            "create a process and inform the review manager in advance"
            + " to avoid conflicts."
        )
        super().__init__(self.message)


class RecordNotInRepoException(Exception):
    def __init__(self, id: str = None):
        if id is not None:
            self.message = f"Record not in index ({id})"
        else:
            self.message = "Record not in index"
        super().__init__(self.message)


class DedupeError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class NoRecordsError(Exception):
    def __init__(self):
        self.message = "no records imported yet"
        super().__init__(self.message)


class UnstagedGitChangesError(Exception):
    def __init__(self, changedFiles):
        self.message = (
            f"changes not yet staged: {changedFiles} (use git add . or stash)"
        )
        super().__init__(self.message)


class CleanRepoRequiredError(Exception):
    def __init__(self, changedFiles, ignore_pattern):
        self.message = (
            "clean repository required (use git commit, discard or stash "
            + f"{changedFiles}; ignore_pattern={ignore_pattern})."
        )
        super().__init__(self.message)


class ProcessOrderViolation(Exception):
    def __init__(self, process, required_state: str, violating_records: list):
        self.message = (
            f" {process.type.name}() requires all records to have at least "
            + f"'{required_state}', but there are records with {violating_records}."
        )
        super().__init__(self.message)


class SettingsError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class NotEnoughDataToIdentifyException(Exception):
    def __init__(self, msg: str = None):
        self.message = msg
        super().__init__(self.message)


class MissingDependencyError(Exception):
    def __init__(self, dep):
        self.message = f"{dep}"
        super().__init__(self.message)


class SoftwareUpgradeError(Exception):
    def __init__(self, old, new):
        self.message = (
            f"Detected upgrade from {old} to {new}. To upgrade use\n     "
            "colrev config --upgrade"
        )
        super().__init__(self.message)


class GitConflictError(Exception):
    def __init__(self, path):
        self.message = f"please resolve git conflict in {path}"
        super().__init__(self.message)


class DirtyRepoAfterProcessingError(Exception):
    pass


class ConsistencyError(Exception):
    pass


class RepoSetupError(Exception):
    def __init__(self, msg):
        self.message = f" {msg}"
        super().__init__(self.message)


class SearchDetailsMissingError(Exception):
    def __init__(
        self,
        search_results_path,
    ):
        self.message = (
            "Search results path "
            + f"({search_results_path.name}) "
            + "is not in sources.yaml"
        )
        super().__init__(self.message)
