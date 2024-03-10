#! /usr/bin/env python
"""Load conversion of reference sections (bibliographies) in md-documents based on GROBID

Example markdown reference section::

    # References

    Guo, W. and Straub, D. W. and Zhang, P. and Cai, Z. (2021). How Trust Leads to Commitment
          on Microsourcing Platforms. MIS Quarterly, 45(3), 1309--1348.

"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

import requests

import colrev.loader.load_utils_bib
import colrev.review_manager
from colrev.constants import Fields

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


class MarkdownLoader:
    """Loads reference strings from text (md) files (based on GROBID)"""

    def __init__(
        self,
        *,
        filename: Path,
        logger: typing.Optional[logging.Logger] = None,
    ):

        self.filename = filename

        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger

    def load(self) -> dict:
        """Load records from the source"""

        self.logger.info("Running GROBID to parse structured reference data")

        grobid_service = colrev.review_manager.ReviewManager.get_grobid_service()

        grobid_service.check_grobid_availability()
        with open(self.filename, encoding="utf8") as file:
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

        records_dict = colrev.loader.load_utils.loads(
            load_string=data,
            implementation="bib",
            logger=self.logger,
        )

        for record in records_dict.values():
            if record.get(Fields.YEAR, "a") == record.get("date", "b"):
                del record["date"]

        return records_dict
