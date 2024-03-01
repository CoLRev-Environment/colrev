#! /usr/bin/env python
"""Load conversion of reference sections (bibliographies) in md-documents based on GROBID

Usage::

    import colrev.ops.load_utils_md
    from colrev.constants import Fields

    load_operation.ensure_append_only(file=self.source.filename)

    md_loader = colrev.ops.load_utils_md.MarkdownLoader(
        source_file=self.search_source.filename,
        force_mode=False,
        logger=review_manager.logger,
    )

    # Note : fixes can be applied before each of the following steps

    records = md_loader.load()

Example markdown reference section::

    # References

    Guo, W. and Straub, D. W. and Zhang, P. and Cai, Z. (2021). How Trust Leads to Commitment
          on Microsourcing Platforms. MIS Quarterly, 45(3), 1309--1348.

"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

import requests

import colrev.exceptions as colrev_exceptions
import colrev.ops.load_utils_bib
import colrev.review_manager
from colrev.constants import Fields

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class MarkdownLoader:
    """Loads reference strings from text (md) files (based on GROBID)"""

    def __init__(
        self,
        *,
        source_file: Path,
        logger: logging.Logger,
        force_mode: bool = False,
    ):

        if not source_file.name.endswith(".md"):
            raise colrev_exceptions.ImportException(
                f"File not supported by MarkdownLoader: {source_file.name}"
            )
        if not source_file.exists():
            raise colrev_exceptions.ImportException(
                f"File not found: {source_file.name}"
            )
        self.source_file = source_file
        self.logger = logger
        self.force_mode = force_mode

    def load(self) -> dict:
        """Load records from the source"""

        self.logger.info("Running GROBID to parse structured reference data")

        grobid_service = colrev.review_manager.ReviewManager.get_grobid_service()

        grobid_service.check_grobid_availability()
        with open(self.source_file, encoding="utf8") as file:
            references = [line.rstrip() for line in file if "#" not in line[:2]]

        data = ""
        ind = 0
        for ref in references:
            options = {}
            options["consolidateCitations"] = "0"
            options["citations"] = ref
            ret = requests.post(
                grobid_service.GROBID_URL + "/api/processCitation",
                data=options,
                headers={"Accept": "application/x-bibtex"},
                timeout=30,
            )
            ind += 1
            data = data + "\n" + ret.text.replace("{-1,", "{" + str(ind) + ",")

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".bib"
        ) as temp_file:
            temp_file.write(data)
            temp_file_path = temp_file.name
            temp_file.flush()
            temp_file.seek(0)

            bib_loader = colrev.ops.load_utils_bib.BIBLoader(
                source_file=Path(temp_file_path),
                logger=self.logger,
                force_mode=self.force_mode,
            )
            records = bib_loader.load_bib_file(check_bib_file=True)

            for record in records.values():
                if record.get(Fields.YEAR, "a") == record.get("date", "b"):
                    del record["date"]

        os.remove(temp_file_path)
        return records
