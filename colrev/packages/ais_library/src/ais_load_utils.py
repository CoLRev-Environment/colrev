#! /usr/bin/env python
"""Load utils for AIS"""
from __future__ import annotations

from colrev.constants import ENTRYTYPES
from colrev.constants import Fields


def enl_id_labeler(records: list) -> None:
    """Labeler for IDs in ENL files."""
    for record_dict in records:
        record_dict[Fields.ID] = record_dict["U"].replace(
            "https://aisel.aisnet.org/", ""
        )


def enl_entrytype_setter(record_dict: dict) -> None:
    """Set the entrytype for ENL files."""
    if "0" not in record_dict:
        keys_to_check = ["V", "N"]
        if any(k in record_dict for k in keys_to_check):
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
        else:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
    else:
        if record_dict["0"] == "Journal Article":
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.ARTICLE
        elif record_dict["0"] == "Inproceedings":
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.INPROCEEDINGS
        else:
            record_dict[Fields.ENTRYTYPE] = ENTRYTYPES.MISC


def enl_field_mapper(record_dict: dict) -> None:
    """Map the fields for ENL files."""
    key_maps = {
        ENTRYTYPES.ARTICLE: {
            "T": Fields.TITLE,
            "A": Fields.AUTHOR,
            "D": Fields.YEAR,
            "B": Fields.JOURNAL,
            "V": Fields.VOLUME,
            "N": Fields.NUMBER,
            "P": Fields.PAGES,
            "X": Fields.ABSTRACT,
            "U": Fields.URL,
            "8": "date",
            "0": "type",
        },
        ENTRYTYPES.INPROCEEDINGS: {
            "T": Fields.TITLE,
            "A": Fields.AUTHOR,
            "D": Fields.YEAR,
            "B": Fields.BOOKTITLE,
            "V": Fields.VOLUME,
            "N": Fields.NUMBER,
            "P": Fields.PAGES,
            "X": Fields.ABSTRACT,
            "U": Fields.URL,
            "8": "date",
            "0": "type",
        },
    }

    key_map = key_maps[record_dict[Fields.ENTRYTYPE]]
    for ris_key in list(record_dict.keys()):
        if ris_key in key_map:
            standard_key = key_map[ris_key]
            record_dict[standard_key] = record_dict.pop(ris_key)

    # Add secondary titles / fix cases where F and P fields start with a space:
    # these may be special cases:
    # https://aisel.aisnet.org/amcis2002/301/
    # https://aisel.aisnet.org/amcis2002/145/
    if " F" in record_dict:
        record_dict[Fields.TITLE] = (
            record_dict[Fields.TITLE] + " " + record_dict.pop(" F")
        )
    if " P" in record_dict:
        record_dict[Fields.TITLE] = (
            record_dict[Fields.TITLE] + " " + record_dict.pop(" P")
        )

    if Fields.AUTHOR in record_dict and isinstance(record_dict[Fields.AUTHOR], list):
        record_dict[Fields.AUTHOR] = " and ".join(record_dict[Fields.AUTHOR])
    if Fields.EDITOR in record_dict and isinstance(record_dict[Fields.EDITOR], list):
        record_dict[Fields.EDITOR] = " and ".join(record_dict[Fields.EDITOR])
    if Fields.KEYWORDS in record_dict and isinstance(
        record_dict[Fields.KEYWORDS], list
    ):
        record_dict[Fields.KEYWORDS] = ", ".join(record_dict[Fields.KEYWORDS])

    record_dict.pop("type", None)

    for key, value in record_dict.items():
        record_dict[key] = str(value)
