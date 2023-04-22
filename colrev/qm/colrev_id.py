#! /usr/bin/env python
"""Generate colrev-ids."""
from __future__ import annotations

import re

from nameparser import HumanName

import colrev.exceptions as colrev_exceptions
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

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


def __get_container_title(*, record_dict: dict) -> str:
    # Note: custom __get_container_title for the colrev_id

    # school as the container title for theses
    if record_dict["ENTRYTYPE"] in ["phdthesis", "masterthesis"]:
        container_title = record_dict["school"]
    # for technical reports
    elif record_dict["ENTRYTYPE"] == "techreport":
        container_title = record_dict["institution"]
    elif record_dict["ENTRYTYPE"] == "inproceedings":
        container_title = record_dict["booktitle"]
    elif record_dict["ENTRYTYPE"] == "article":
        container_title = record_dict["journal"]
    elif "series" in record_dict:
        container_title = record_dict["series"]
    elif "url" in record_dict:
        container_title = record_dict["url"]
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
    *, record: colrev.record.Record, assume_complete: bool, also_known_as_record: dict
) -> None:
    if assume_complete:
        return
    if record.data.get("colrev_status", "NA") in [
        colrev.record.RecordState.md_imported,
        colrev.record.RecordState.md_needs_manual_preparation,
    ]:
        if len(also_known_as_record) != 0:
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


def __get_colrev_id_from_record(*, record_dict: dict) -> str:
    try:
        # Including the version of the identifier prevents cases
        # in which almost all identifiers are identical
        # (and very few identifiers change)
        # when updating the identifier function function
        # (this may look like an anomaly and be hard to identify)
        srep = "colrev_id1:"
        if record_dict["ENTRYTYPE"].lower() == "article":
            srep = __robust_append(input_string=srep, to_append="a")
        elif record_dict["ENTRYTYPE"].lower() == "inproceedings":
            srep = __robust_append(input_string=srep, to_append="p")
        else:
            srep = __robust_append(
                input_string=srep, to_append=record_dict["ENTRYTYPE"].lower()
            )
        srep = __robust_append(
            input_string=srep,
            to_append=__get_container_title(record_dict=record_dict),
        )
        if record_dict["ENTRYTYPE"] == "article":
            # Note: volume/number may not be required.
            srep = __robust_append(
                input_string=srep, to_append=record_dict.get("volume", "-")
            )
            srep = __robust_append(
                input_string=srep, to_append=record_dict.get("number", "-")
            )
        srep = __robust_append(input_string=srep, to_append=record_dict["year"])
        author = __format_author_field_for_cid(record_dict["author"])
        if author.replace("-", "") == "":
            raise colrev_exceptions.NotEnoughDataToIdentifyException(
                msg="Missing field:", missing_fields=["author"]
            )
        srep = __robust_append(input_string=srep, to_append=author)
        srep = __robust_append(input_string=srep, to_append=record_dict["title"])

        srep = srep.replace(";", "")  # ";" is the separator in colrev_id list
        # Note : pages not needed.
        # pages = record_dict.get("pages", "")
        # srep = __robust_append(srep, pages)
    except KeyError as exc:
        if "ENTRYTYPE" in str(exc):
            print(f"Missing ENTRYTYPE in {record_dict['ID']}")
        raise colrev_exceptions.NotEnoughDataToIdentifyException(
            msg="Missing field:" + str(exc), missing_fields=["ENTRYTYPE"]
        )
    return srep


def __get_rec_dict_for_srep(
    *, record: colrev.record.Record, also_known_as_record: dict
) -> dict:
    if len(also_known_as_record) == 0:
        record_dict = record.data
    else:
        required_fields_keys = colrev.record.Record.record_field_requirements["other"]
        if record.data["ENTRYTYPE"] in colrev.record.Record.record_field_requirements:
            required_fields_keys = colrev.record.Record.record_field_requirements[
                record.data["ENTRYTYPE"]
            ]

        missing_field_keys = [
            f for f in required_fields_keys if f not in also_known_as_record
        ]
        if len(missing_field_keys) > 0:
            raise colrev_exceptions.NotEnoughDataToIdentifyException(
                msg="Missing fields:" + ",".join(missing_field_keys),
                missing_fields=missing_field_keys,
            )
        record_dict = also_known_as_record
    return record_dict


def create_colrev_id(
    *, record: colrev.record.Record, also_known_as_record: dict, assume_complete: bool
) -> str:
    """Create the colrev_id"""
    __check_colrev_id_preconditions(
        record=record,
        assume_complete=assume_complete,
        also_known_as_record=also_known_as_record,
    )

    record_dict = __get_rec_dict_for_srep(
        record=record, also_known_as_record=also_known_as_record
    )
    srep = __get_colrev_id_from_record(record_dict=record_dict)

    # Safeguard against titles that are rarely distinct
    if any(x in srep for x in ["|minitrack-introduction|"]):
        raise colrev_exceptions.NotEnoughDataToIdentifyException(
            msg="Title typically non-distinct", missing_fields=["title"]
        )

    return srep


if __name__ == "__main__":
    pass
