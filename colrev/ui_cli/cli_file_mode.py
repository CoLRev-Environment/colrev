#!/usr/bin/env python3
"""File mode operations."""
from __future__ import annotations

from colrev.constants import Fields

from pathlib import Path
import colrev.env.local_index
import colrev.exceptions as colrev_exceptions

def pdf_get(file: Path) -> None:
    print(f"Download PDFs for: {file}")

    records = colrev.loader.load_utils.load(Path(file))
    local_index = colrev.env.local_index.LocalIndex(
        verbose_mode=True
    )

    for record in records.values():
        if Fields.FILE in record:
            continue
        print(f"Retrieve PDF for record {record[Fields.ID]}.")

        try:
            retrieved_record = local_index.retrieve(record, include_file=True)
        except colrev_exceptions.RecordNotInIndexException:
            continue

        if Fields.FILE in retrieved_record.data:
            input(retrieved_record.data[Fields.FILE])
        