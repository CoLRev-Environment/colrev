#! /usr/bin/env python
"""Load conversion of reference sections (bibliographies) in md-documents based on GROBID"""
from __future__ import annotations

import logging
import typing
from pathlib import Path

import requests

import colrev.env.grobid_service
import colrev.loader.load_utils
import colrev.loader.loader
from colrev.constants import Fields

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code
# pylint: disable=too-many-arguments


class MarkdownLoader(colrev.loader.loader.Loader):
    """Loads reference strings from text (md) files (based on GROBID)"""

    def __init__(
        self,
        *,
        filename: Path,
        entrytype_setter: typing.Callable = lambda x: x,
        field_mapper: typing.Callable = lambda x: x,
        id_labeler: typing.Callable = lambda x: x,
        unique_id_field: str = "",
        logger: logging.Logger = logging.getLogger(__name__),
        format_names: bool = False,
    ):

        super().__init__(
            filename=filename,
            id_labeler=id_labeler,
            unique_id_field=unique_id_field,
            entrytype_setter=entrytype_setter,
            field_mapper=field_mapper,
            logger=logger,
            format_names=format_names,
        )

    @classmethod
    def get_nr_records(cls, filename: Path) -> int:
        """Get the number of records in the file"""

        count = 0
        with open(filename, encoding="utf8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#"):
                    count += 1
        return count

    def load_records_list(self) -> list:
        """Load records from the source"""

        self.logger.info("Running GROBID to parse structured reference data")

        grobid_service = colrev.env.grobid_service.GrobidService()

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

        return list(records_dict.values())
