#! /usr/bin/env python
"""Convenience functions to load enl files

%T How Trust Leads to Commitment on Microsourcing Platforms
%0 Journal Article
%A Guo, Wenbo
%A Straub, Detmar W.
%A Zhang, Pengzhu
%A Cai, Zhao
%B Management Information Systems Quarterly
%D 2021
%8 September  1, 2021
%V 45
%N 3
%P 1309-1348
%U https://aisel.aisnet.org/misq/vol45/iss3/13
%X IS research has extensively examined the role of trust in client-vendor relationships...
"""
from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import colrev.ops.load
    import colrev.settings.SearchSource

# pylint: disable=too-few-public-methods


class ENLLoader:

    """Loads enl files"""

    def __init__(
        self,
        *,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        unique_id_field: str = "",
    ):
        self.load_operation = load_operation
        self.source = source
        self.unique_id_field = unique_id_field

    def load_enl_entries(self) -> dict:
        """Loads enl entries"""

        # pylint: disable=too-many-branches

        if self.unique_id_field == "":
            self.load_operation.ensure_append_only(file=self.source.filename)

        # Note : REFERENCE_TYPES and KEY_MAP are hard-coded (standard)
        # This function intentionally fails when the input does not comply
        # with this standard

        records = {}
        with open(self.source.filename, encoding="utf-8") as file:
            record = {}
            ind = 1
            for line in file:
                if line.startswith("%0 "):
                    record["ENTRYTYPE"] = "article"
                elif line.startswith("%A "):
                    if "author" in record:
                        record["author"] += " and " + line[3:].rstrip()
                    else:
                        record["author"] = line[3:].rstrip()
                elif line.startswith("%D "):
                    record["year"] = line[3:].rstrip()
                elif line.startswith("%U "):
                    record["url"] = line[3:].rstrip()
                elif line.startswith("%X "):
                    record["abstract"] = line[3:].rstrip()
                elif line.startswith("%T "):
                    record["title"] = line[3:].rstrip()
                elif line.startswith("%V "):
                    record["volume"] = line[3:].rstrip()
                elif line.startswith("%N "):
                    record["number"] = line[3:].rstrip()
                elif line.startswith("%B "):
                    record["booktitle"] = line[3:].rstrip()
                elif line.startswith("%P "):
                    record["pages"] = line[3:].rstrip()

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

    def convert_to_records(self, *, entries: dict) -> dict:
        """Converts enl entries it to bib records"""

        records: dict = {}
        for counter, entry in enumerate(entries.values()):
            if self.unique_id_field == "":
                _id = str(counter + 1).zfill(5)
            else:
                _id = entry[self.unique_id_field].replace(" ", "").replace(";", "_")

            entry["ID"] = _id

            records[_id] = entry

        return records
