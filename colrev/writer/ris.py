#! /usr/bin/env python
"""Function to write ris files"""
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
    "IS",
    "N2",
    "UR",
    "SN",
    "DO",
]

ENTRYTYPE_MAP = {
    ENTRYTYPES.ARTICLE: "JOUR",
    ENTRYTYPES.BOOK: "BOOK",
    ENTRYTYPES.INPROCEEDINGS: "CONF",
    ENTRYTYPES.PROCEEDINGS: "CONF",
    ENTRYTYPES.INCOLLECTION: "CONF",
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
    "IS": Fields.NUMBER,
    "N2": Fields.ABSTRACT,
    "UR": Fields.URL,
    "DO": Fields.DOI,
}


def _add_pages(record_dict: dict) -> str:
    """Add pages to the RIS string"""
    pages_str = ""
    if Fields.PAGES in record_dict:
        pages = str(record_dict[Fields.PAGES])
        if "--" in pages:
            start, end = pages.split("--")
            pages_str += f"SP  - {start}\n"
            pages_str += f"EP  - {end}\n"
        elif "-" in pages and pages.count("-") == 1:
            start, end = pages.split("-")
            pages_str += f"SP  - {start}\n"
            pages_str += f"EP  - {end}\n"
        else:
            pages_str += f"SP  - {pages}\n"
    return pages_str


def _add_sn(record_dict: dict) -> str:
    """Add SN (ISSN/ISBN) to the RIS string"""
    sn_list = []
    if Fields.ISSN in record_dict:
        sn_list.append(str(record_dict[Fields.ISSN]))
    if Fields.ISBN in record_dict:
        sn_list.append(str(record_dict[Fields.ISBN]))
    if sn_list:
        return f"SN  - {';'.join(sn_list)}\n"
    return ""


def to_string(*, records_dict: dict) -> str:
    """Convert a records dict to a RIS string"""
    ris_str = ""
    for record_id in sorted(records_dict.keys()):
        record_dict = records_dict[record_id]
        for field in RECORDS_FIELD_ORDER:
            if field == "TY":
                entrytype = ENTRYTYPE_MAP[record_dict[Fields.ENTRYTYPE]]
                ris_str += f"TY  - {entrytype}\n"

            elif field in RECORD_FIELD_MAP and str(
                record_dict.get(RECORD_FIELD_MAP[field], "")
            ) not in ["", "None", "UNKNOWN", "nan"]:
                ris_str += f"{field}  - {record_dict[RECORD_FIELD_MAP[field]]}\n"

            elif field == "AU":
                if record_dict[Fields.AUTHOR] and str(
                    record_dict[Fields.AUTHOR]
                ) not in ["None", "UNKNOWN", "nan"]:
                    for author in record_dict[Fields.AUTHOR].split(" and "):
                        ris_str += f"AU  - {author}\n"

        ris_str += _add_pages(record_dict)
        ris_str += _add_sn(record_dict)

        ris_str += "ER  -\n\n"

    return ris_str


def write_file(*, records_dict: dict, filename: str) -> None:
    """Write a RIS file from a records dict"""
    ris_str = to_string(records_dict=records_dict)
    with open(filename, "w", encoding="utf-8") as file:
        file.write(ris_str)
