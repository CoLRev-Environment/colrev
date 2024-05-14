#! /usr/bin/env python
"""Convenience functions to write ris files"""
from __future__ import annotations

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields

RECORDS_FIELD_ORDER = [
    "TY",  # Must be the first field
    "TI",
    "AU",
    "PY",
    "SP",
    "EP",
    "JO",
    "VL",
    "ER",  # Must be the last field
]

ENTRYTYPE_MAP = {
    ENTRYTYPES.ARTICLE: "JOUR",
    ENTRYTYPES.BOOK: "BOOK",
    ENTRYTYPES.INPROCEEDINGS: "CONF",
    ENTRYTYPES.MISC: "GEN",
    ENTRYTYPES.PHDTHESIS: "THES",
    ENTRYTYPES.TECHREPORT: "RPRT",
    ENTRYTYPES.UNPUBLISHED: "UNPB",
}


RECORD_FIELD_MAP = {
    "TI": Fields.TITLE,
    "PY": Fields.YEAR,
    "JO": Fields.JOURNAL,
    "VL": Fields.VOLUME,
}


def to_string(*, records_dict: dict) -> str:
    """Convert a records dict to a RIS string"""
    ris_str = ""
    for record_id in sorted(records_dict.keys()):
        record_dict = records_dict[record_id]
        for field in RECORDS_FIELD_ORDER:
            if field == "TY":
                entrytype = ENTRYTYPE_MAP[record_dict[Fields.ENTRYTYPE]]
                ris_str += f"TY  - {entrytype}\n"

            elif field in RECORD_FIELD_MAP:
                ris_str += f"{field}  - {record_dict[RECORD_FIELD_MAP[field]]}\n"
            elif field == Fields.PAGES:
                if Fields.PAGES in record_dict:
                    pages = record_dict[Fields.PAGES]
                    if "-" in pages:
                        start, end = pages.split("-")
                        ris_str += f"SP  - {start}\n"
                        ris_str += f"EP  - {end}\n"
                    else:
                        ris_str += f"SP  - {pages}\n"

            elif field == "AU":
                for author in record_dict[Fields.AUTHOR].split(" and "):
                    ris_str += f"AU  - {author}\n"

            elif field == "ER":
                ris_str += "ER  -\n\n"
                break  # must be last field

            else:
                pass  # field not (yet) supported

    return ris_str


def write_file(*, records_dict: dict, filename: str) -> None:
    """Write a RIS file from a records dict"""
    ris_str = to_string(records_dict=records_dict)
    with open(filename, "w", encoding="utf-8") as file:
        file.write(ris_str)
