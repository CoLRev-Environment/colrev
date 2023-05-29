#! /usr/bin/env python
"""Generate colrev-ids."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nameparser import HumanName

import colrev.exceptions as colrev_exceptions
import colrev.record

if TYPE_CHECKING:
    import colrev.review_manager


def __format_author_field_for_cid(input_string: str) -> str:
    input_string = input_string.replace("\n", " ").replace("'", "")
    names = input_string.replace("; ", " and ").split(" and ")
    author_list = []
    for name in names:
        if name.rstrip()[-1:] == ",":
            # if last-names only (eg, "Webster, and Watson, ")
            if len(name[:-2]) > 1:
                author_list.append(str(name.rstrip()[:-1]))
        else:
            parsed_name = HumanName(name)

            if parsed_name.last == "" and parsed_name.first != "":
                author_list.append(parsed_name.first)
                continue

            # Note: do not set parsed_name.string_format as a global constant
            # to preserve consistent creation of identifiers
            parsed_name.string_format = "{last} "
            if len(parsed_name.middle) > 0:
                parsed_name.middle = parsed_name.middle[:1]
            if len(parsed_name.first) > 0:
                parsed_name.first = parsed_name.first[:1]
            if len(parsed_name.nickname) > 0:
                parsed_name.nickname = ""

            if len(str(parsed_name)) > 1:
                author_list.append(str(parsed_name))

    return " ".join(author_list)


def __get_container_title(*, record: colrev.record.Record) -> str:
    # Note: custom __get_container_title for the colrev_id

    # school as the container title for theses
    if record.data["ENTRYTYPE"] in ["phdthesis", "masterthesis"]:
        container_title = record.data["school"]
    # for technical reports
    elif record.data["ENTRYTYPE"] == "techreport":
        container_title = record.data["institution"]
    elif record.data["ENTRYTYPE"] == "inproceedings":
        container_title = record.data["booktitle"]
    elif record.data["ENTRYTYPE"] == "article":
        container_title = record.data["journal"]
    elif "series" in record.data:
        container_title = record.data["series"]
    elif "url" in record.data:
        container_title = record.data["url"]
    else:
        raise KeyError

    return container_title


def __robust_append(*, input_string: str, to_append: str) -> str:
    input_string = str(input_string)
    to_append = str(to_append).replace("\n", " ").replace("/", " ")
    to_append = to_append.rstrip().lstrip().replace("–", " ")
    to_append = to_append.replace("emph{", "")
    to_append = to_append.replace("&amp;", "and")
    to_append = to_append.replace(" & ", " and ")
    to_append = colrev.env.utils.remove_accents(input_str=to_append)
    to_append = re.sub("[^0-9a-zA-Z -]+", "", to_append)
    to_append = re.sub(r"\s+", "-", to_append)
    to_append = re.sub(r"-+", "-", to_append)
    to_append = to_append.lower()
    if len(to_append) > 1:
        to_append = to_append.rstrip("-")
    input_string = input_string + "|" + to_append
    return input_string


def __check_colrev_id_preconditions(
    *,
    record: colrev.record.Record,
    assume_complete: bool,
) -> None:
    if assume_complete:
        return
    if record.data.get("colrev_status", "NA") in [
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
    ]:
        raise colrev_exceptions.NotEnoughDataToIdentifyException(
            msg="cannot determine field requirements "
            "(e.g., volume/number for journal articles)",
            missing_fields=["colrev_status/field_requirements"],
        )
    # Make sure that colrev_ids are not generated when
    # identifying_field_keys are UNKNOWN but possibly required
    for identifying_field_key in colrev.record.Record.identifying_field_keys:
        if record.data.get(identifying_field_key, "") == "UNKNOWN":
            raise colrev_exceptions.NotEnoughDataToIdentifyException(
                msg=f"{identifying_field_key} unknown (maybe required)",
                missing_fields=[identifying_field_key],
            )


def __get_colrev_id_from_record(*, record: colrev.record.Record) -> str:
    try:
        # Including the version of the identifier prevents cases
        # in which almost all identifiers are identical
        # (and very few identifiers change)
        # when updating the identifier function function
        # (this may look like an anomaly and be hard to identify)
        srep = "colrev_id1:"
        if record.data["ENTRYTYPE"].lower() == "article":
            srep = __robust_append(input_string=srep, to_append="a")
        elif record.data["ENTRYTYPE"].lower() == "inproceedings":
            srep = __robust_append(input_string=srep, to_append="p")
        else:
            srep = __robust_append(
                input_string=srep, to_append=record.data["ENTRYTYPE"].lower()
            )
        srep = __robust_append(
            input_string=srep,
            to_append=__get_container_title(record=record),
        )
        if record.data["ENTRYTYPE"] == "article":
            # Note: volume/number may not be required.
            srep = __robust_append(
                input_string=srep, to_append=record.data.get("volume", "-")
            )
            srep = __robust_append(
                input_string=srep, to_append=record.data.get("number", "-")
            )
        srep = __robust_append(input_string=srep, to_append=record.data["year"])
        author = __format_author_field_for_cid(record.data["author"])
        if author.replace("-", "") == "":
            raise colrev_exceptions.NotEnoughDataToIdentifyException(
                msg="Missing field:", missing_fields=["author"]
            )
        srep = __robust_append(input_string=srep, to_append=author)
        srep = __robust_append(input_string=srep, to_append=record.data["title"])

        srep = srep.replace(";", "")  # ";" is the separator in colrev_id list
        # Note : pages not needed.
        # pages = record_dict.get("pages", "")
        # srep = __robust_append(srep, pages)
    except KeyError as exc:
        if "ENTRYTYPE" in str(exc):
            print(f"Missing ENTRYTYPE in {record.data['ID']}")
        raise colrev_exceptions.NotEnoughDataToIdentifyException(
            msg="Missing field:" + str(exc), missing_fields=["ENTRYTYPE"]
        )
    return srep


def create_colrev_id(*, record: colrev.record.Record, assume_complete: bool) -> str:
    """Create the colrev_id"""
    __check_colrev_id_preconditions(
        record=record,
        assume_complete=assume_complete,
    )

    srep = __get_colrev_id_from_record(record=record)

    # Safeguard against titles that are rarely distinct
    if any(x in srep for x in ["|minitrack-introduction|"]):
        raise colrev_exceptions.NotEnoughDataToIdentifyException(
            msg="Title typically non-distinct", missing_fields=["title"]
        )

    return srep
