#! /usr/bin/env python
"""Convenience functions to load bib files"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import colrev.ops.load

# pylint: disable=too-few-public-methods


class NBIBLoader:

    """Loads nbib files"""

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
    ):
        self.load_operation = load_operation
        self.source = source

    def load(
        self,
        *,
        source: colrev.settings.SearchSource,
    ) -> dict:
        """Converts ris entries it to bib records"""

        # pylint: disable=too-many-branches

        # Note : REFERENCE_TYPES and KEY_MAP are hard-coded (standard)
        # This function intentionally fails when the input does not comply
        # with this standard

        self.load_operation.ensure_append_only(file=self.source.filename)

        records = {}
        with open(source.filename, encoding="utf-8") as file:
            record = {}
            ind = 1
            for line in file:
                if line.startswith("TI "):
                    record["title"] = line[line.find(" - ") + 3 :].rstrip()

                elif line.startswith("JT "):
                    record["journal"] = line[line.find(" - ") + 3 :].rstrip()
                elif line.startswith("AB "):
                    record["abstract"] = line[line.find(" - ") + 3 :].rstrip()
                elif line.startswith("DP "):
                    record["year"] = line[line.find(" - ") + 3 :].rstrip()
                elif line.startswith("VI "):
                    record["volume"] = line[line.find(" - ") + 3 :].rstrip()
                elif line.startswith("IP "):
                    record["number"] = line[line.find(" - ") + 3 :].rstrip()

                elif line.startswith("PG "):
                    record["pages"] = line[line.find(" - ") + 3 :].rstrip()
                elif line.startswith("PT "):
                    if "Journal Articles" in line:
                        record["ENTRYTYPE"] = "article"
                elif line.startswith("AU "):
                    if "author" in record:
                        record["author"] += (
                            " and " + line[line.find(" - ") + 3 :].rstrip()
                        )
                    else:
                        record["author"] = line[line.find(" - ") + 3 :].rstrip()

                elif line.startswith("OT "):
                    if "keywords" in record:
                        record["keywords"] += (
                            ", " + line[line.find(" - ") + 3 :].rstrip()
                        )
                    else:
                        record["keywords"] = line[line.find(" - ") + 3 :].rstrip()

                elif line.rstrip() == "":
                    if not record:
                        continue
                    record["ID"] = str(ind).rjust(6, "0")
                    ind += 1
                    if "ENTRYTYPE" not in record:
                        if "booktitle" in record:
                            record["ENTRYTYPE"] = "inproceedings"
                        else:
                            record["ENTRYTYPE"] = "misc"
                    records[record["ID"]] = deepcopy(record)
                    record = {}
                # else:
                #     print(line)

        return records
