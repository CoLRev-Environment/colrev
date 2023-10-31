#! /usr/bin/env python
"""Load conversion of reference sections (bibliographies) in md-documents based on GROBID

Example reference section::

    # References

    Guo, W. and Straub, D. W. and Zhang, P. and Cai, Z. (2021). How Trust Leads to Commitment
          on Microsourcing Platforms. MIS Quarterly, 45(3), 1309--1348.

"""
from __future__ import annotations

from typing import TYPE_CHECKING

import requests

import colrev.env.package_manager
from colrev.constants import Fields

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods
# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class MarkdownLoader:

    """Loads reference strings from text (md) files (based on GROBID)"""

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
    ):
        self.source = source
        self.load_operation = load_operation

    def load(self) -> dict:
        """Load records from the source"""
        self.load_operation.ensure_append_only(file=self.source.filename)

        self.load_operation.review_manager.logger.info(
            "Running GROBID to parse structured reference data"
        )

        grobid_service = self.load_operation.review_manager.get_grobid_service()

        grobid_service.check_grobid_availability()
        with open(self.source.filename, encoding="utf8") as file:
            if self.source.filename.suffix == ".md":
                references = [line.rstrip() for line in file if "#" not in line[:2]]
            else:
                references = [line.rstrip() for line in file]

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

        records = self.load_operation.review_manager.dataset.load_records_dict(
            load_str=data
        )
        for record in records.values():
            if record.get(Fields.YEAR, "a") == record.get("date", "b"):
                del record["date"]

        return records
