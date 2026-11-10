"""Bibliography record compatibility helpers."""

from __future__ import annotations

from colrev.constants import Fields, RecordState


def adapt_bibliography_records(records: dict) -> dict:
    """Restore CoLRev field shapes after generic bibliography-io parsing."""
    for record in records.values():

        origin = record.get(Fields.ORIGIN)
        if isinstance(origin, str):
            record[Fields.ORIGIN] = [
                value.strip() for value in origin.strip().split(";") if value.strip()
            ]

        for field in (Fields.MD_PROV, Fields.D_PROV):
            value = record.get(field)
            if isinstance(value, str):
                record[field] = _parse_provenance(value)

        status = record.get(Fields.STATUS)
        if isinstance(status, str):
            record[Fields.STATUS] = RecordState[status]
    return records


def _parse_provenance(value: str) -> dict:
    """Parse legacy CoLRev provenance strings."""
    parsed_dict = {}
    items = [item.strip() for item in value.split("; ") if item.strip()]
    for item in items:
        if ":" not in item:
            continue
        key, source = item.split(":", 1)
        source_parts = source.split(";")
        parsed_dict[key.strip()] = {
            "source": source_parts[0].strip(),
            "note": source_parts[1].strip() if len(source_parts) > 1 else "",
        }
    return parsed_dict
