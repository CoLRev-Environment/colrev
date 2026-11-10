"""Utilities for working with bibliography records."""

from bibliography_io.exceptions import DuplicateRecordIDError, MissingRecordIDError

from colrev.constants import Fields


def index_records_by_id(records: list[dict]) -> dict[str, dict]:
    """Index raw bibliography records by ID without dropping duplicates."""
    indexed: dict[str, dict] = {}
    for record in records:
        record_id = record.get(Fields.ID)
        if not isinstance(record_id, str) or not record_id.strip():
            raise MissingRecordIDError("Records indexed by ID require a non-empty ID")
        if record_id in indexed:
            raise DuplicateRecordIDError(f"Duplicate record ID: {record_id}")
        indexed[record_id] = record
    return indexed
