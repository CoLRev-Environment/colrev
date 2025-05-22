#! /usr/bin/env python
"""Function to write bib files"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from colrev.constants import Fields


RECORDS_FIELD_ORDER = [
    Fields.ORIGIN,  # must be in second line
    Fields.STATUS,
    Fields.MD_PROV,
    Fields.D_PROV,
    Fields.PDF_ID,
    Fields.SCREENING_CRITERIA,
    Fields.FILE,  # Note : do not change this order (parsers rely on it)
    Fields.PRESCREEN_EXCLUSION,
    Fields.DOI,
    Fields.GROBID_VERSION,
    Fields.DBLP_KEY,
    Fields.SEMANTIC_SCHOLAR_ID,
    Fields.WEB_OF_SCIENCE_ID,
    Fields.AUTHOR,
    Fields.BOOKTITLE,
    Fields.JOURNAL,
    Fields.TITLE,
    Fields.YEAR,
    Fields.VOLUME,
    Fields.NUMBER,
    Fields.PAGES,
    Fields.EDITOR,
    Fields.PUBLISHER,
    Fields.URL,
    Fields.ABSTRACT,
]


def _sanitize_string_for_dict(input_string: str) -> str:
    """Sanitize a string for dict keys"""
    return (
        input_string.replace(";", "_")
        .replace("=", "_")
        .replace("{", "_")
        .replace("}", "_")
    )


def _save_field_dict(*, input_dict: dict, input_key: str) -> list:
    list_to_return = []
    assert input_key in [Fields.MD_PROV, Fields.D_PROV]
    if input_key == Fields.MD_PROV:
        for key, value in input_dict.items():
            if isinstance(value, dict):
                formated_note = ",".join(
                    sorted(e for e in value["note"].split(",") if "" != e)
                )
                formated_note = _sanitize_string_for_dict(formated_note)
                formatted_source = _sanitize_string_for_dict(value["source"])
                list_to_return.append(f"{key}:{formatted_source};{formated_note};")

    elif input_key == Fields.D_PROV:
        for key, value in input_dict.items():
            if isinstance(value, dict):
                formated_note = ",".join(
                    sorted(e for e in value["note"].split(",") if "" != e)
                )
                formated_note = _sanitize_string_for_dict(formated_note)
                formatted_source = _sanitize_string_for_dict(value["source"])
                list_to_return.append(f"{key}:{formatted_source};{formated_note};")

    return list_to_return


def _get_stringified_record(*, record_dict: dict) -> dict:
    data_copy = deepcopy(record_dict)

    def list_to_str(*, val: list) -> str:
        return ("\n" + " " * 36).join([f.rstrip() for f in val])

    for key in [Fields.ORIGIN]:
        if key in data_copy:
            if key in [Fields.ORIGIN]:
                data_copy[key] = sorted(list(set(data_copy[key])))
            for ind, val in enumerate(data_copy[key]):
                if len(val) > 0:
                    if val[-1] != ";":
                        data_copy[key][ind] = val + ";"
            data_copy[key] = list_to_str(val=data_copy[key])

    for key in [Fields.MD_PROV, Fields.D_PROV]:
        if key in data_copy:
            if isinstance(data_copy[key], dict):
                data_copy[key] = _save_field_dict(
                    input_dict=data_copy[key], input_key=key
                )
            if isinstance(data_copy[key], list):
                data_copy[key] = list_to_str(val=data_copy[key])

    return data_copy


def to_string(*, records_dict: dict) -> str:
    """Convert a records dict to a bibtex string"""
    # Note: we need a deepcopy because the parsing modifies dicts
    recs_dict = deepcopy(records_dict)

    def format_field(field: str, value: str) -> str:
        padd = " " * max(0, 28 - len(field))
        return f",\n   {field} {padd} = {{{value}}}"

    bibtex_str = ""
    first = True
    for record_id, record_dict in sorted(recs_dict.items()):
        if not first:
            bibtex_str += "\n"
        first = False

        bibtex_str += f"@{record_dict[Fields.ENTRYTYPE]}{{{record_id}"

        record_dict = _get_stringified_record(record_dict=record_dict)

        for ordered_field in RECORDS_FIELD_ORDER:
            if ordered_field in record_dict:
                if record_dict[ordered_field] == "":
                    continue
                bibtex_str += format_field(ordered_field, record_dict[ordered_field])

        for key in sorted(record_dict.keys()):
            if key in RECORDS_FIELD_ORDER + [Fields.ID, Fields.ENTRYTYPE]:
                continue

            bibtex_str += format_field(key, record_dict[key])

        bibtex_str += ",\n}\n"

    return bibtex_str


def write_file(*, records_dict: dict, filename: Path) -> None:
    """Write a bib file from a records dict"""
    bibtexstr = to_string(records_dict=records_dict)
    with open(filename, "w", encoding="utf-8") as file:
        file.write(bibtexstr)
