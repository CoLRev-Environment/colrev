#! /usr/bin/env python
"""Functionality to determine similarity betwen records."""
from __future__ import annotations

import typing

from rapidfuzz import fuzz

from colrev.constants import Fields
from colrev.constants import FieldValues

if typing.TYPE_CHECKING:  # pragma: no cover
    import colrev.record.record


def get_record_change_score(
    record_a: colrev.record.record.Record, record_b: colrev.record.record.Record
) -> float:
    """Determine how much records changed"""

    # At some point, this may become more sensitive to major changes
    str_a = (
        f"{record_a.data.get(Fields.AUTHOR, '')} ({record_a.data.get(Fields.YEAR, '')}) "
        + f"{record_a.data.get(Fields.TITLE, '')}. "
        + f"{record_a.data.get(Fields.JOURNAL, '')}{record_a.data.get(Fields.BOOKTITLE, '')}, "
        + f"{record_a.data.get(Fields.VOLUME, '')} ({record_a.data.get(Fields.NUMBER, '')})"
    )
    str_b = (
        f"{record_b.data.get(Fields.AUTHOR, '')} ({record_b.data.get(Fields.YEAR, '')}) "
        + f"{record_b.data.get(Fields.TITLE, '')}. "
        + f"{record_b.data.get(Fields.JOURNAL, '')}{record_b.data.get(Fields.BOOKTITLE, '')}, "
        + f"{record_b.data.get(Fields.VOLUME, '')} ({record_b.data.get(Fields.NUMBER, '')})"
    )
    return 1 - fuzz.ratio(str_a.lower(), str_b.lower()) / 100


def get_record_similarity(
    record_a: colrev.record.record.Record, record_b: colrev.record.record.Record
) -> float:
    """Determine the similarity between two records (their masterdata)"""

    record_a_dict = record_a.copy().get_data()
    record_b_dict = record_b.copy().get_data()

    mandatory_fields = [
        Fields.TITLE,
        Fields.AUTHOR,
        Fields.YEAR,
        Fields.JOURNAL,
        Fields.VOLUME,
        Fields.NUMBER,
        Fields.PAGES,
        Fields.BOOKTITLE,
    ]

    for mandatory_field in mandatory_fields:
        if (
            record_a_dict.get(mandatory_field, FieldValues.UNKNOWN)
            == FieldValues.UNKNOWN
        ):
            record_a_dict[mandatory_field] = ""
        if (
            record_b_dict.get(mandatory_field, FieldValues.UNKNOWN)
            == FieldValues.UNKNOWN
        ):
            record_b_dict[mandatory_field] = ""

    if Fields.CONTAINER_TITLE not in record_a_dict:
        record_a_dict[Fields.CONTAINER_TITLE] = (
            record_a_dict.get(Fields.JOURNAL, "")
            + record_a_dict.get(Fields.BOOKTITLE, "")
            + record_a_dict.get(Fields.SERIES, "")
        )

    if Fields.CONTAINER_TITLE not in record_b_dict:
        record_b_dict[Fields.CONTAINER_TITLE] = (
            record_b_dict.get(Fields.JOURNAL, "")
            + record_b_dict.get(Fields.BOOKTITLE, "")
            + record_b_dict.get(Fields.SERIES, "")
        )

    return _get_similarity_detailed(record_a_dict, record_b_dict)


def _get_similarity_detailed(record_a: dict, record_b: dict) -> float:
    """Determine the detailed similarities between records"""
    author_similarity = (
        fuzz.ratio(record_a.get(Fields.AUTHOR, ""), record_b.get(Fields.AUTHOR, ""))
        / 100
    )

    title_similarity = (
        fuzz.ratio(
            record_a.get(Fields.TITLE, "").lower().replace(":", "").replace("-", ""),
            record_b.get(Fields.TITLE, "").lower().replace(":", "").replace("-", ""),
        )
        / 100
    )

    # partial ratio (catching 2010-10 or 2001-2002)
    year_similarity = (
        fuzz.ratio(
            str(record_a.get(Fields.YEAR, "")), str(record_b.get(Fields.YEAR, ""))
        )
        / 100
    )

    outlet_similarity = 0.0
    if record_b.get(Fields.CONTAINER_TITLE, "") and record_a.get(
        Fields.CONTAINER_TITLE, ""
    ):
        outlet_similarity = (
            fuzz.ratio(
                record_a.get(Fields.CONTAINER_TITLE, ""),
                record_b.get(Fields.CONTAINER_TITLE, ""),
            )
            / 100
        )

    if record_a.get(Fields.JOURNAL, "") not in [
        "",
        FieldValues.UNKNOWN,
    ] and record_b.get(Fields.JOURNAL, "") not in ["", FieldValues.UNKNOWN]:
        # Note: for journals papers, we expect more details
        volume_similarity = (
            1
            if (record_a.get(Fields.VOLUME, "") == record_b.get(Fields.VOLUME, ""))
            else 0
        )

        number_similarity = (
            1
            if (record_a.get(Fields.NUMBER, "") == record_b.get(Fields.NUMBER, ""))
            else 0
        )

        # Put more weight on other fields if the title is very common
        # ie., non-distinctive
        # The list is based on a large export of distinct papers, tabulated
        # according to titles and sorted by frequency
        if all(
            title
            in [
                "editorial",
                "editorial introduction",
                "editorial notes",
                "editor's comments",
                "book reviews",
                "editorial note",
                "reviewer ackowledgment",
            ]
            for title in [
                record_a.get(Fields.TITLE, "").lower(),
                record_b.get(Fields.TITLE, "").lower(),
            ]
        ):
            weights = [0.175, 0, 0.175, 0.175, 0.275, 0.2]
        else:
            weights = [0.2, 0.25, 0.13, 0.2, 0.12, 0.1]

        similarities = [
            author_similarity,
            title_similarity,
            year_similarity,
            outlet_similarity,
            volume_similarity,
            number_similarity,
        ]

    else:
        weights = [0.15, 0.75, 0.05, 0.05]
        similarities = [
            author_similarity,
            title_similarity,
            year_similarity,
            outlet_similarity,
        ]

    weighted_average = sum(
        similarities[g] * weights[g] for g in range(len(similarities))
    )
    return round(weighted_average, 4)
