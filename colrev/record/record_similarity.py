#! /usr/bin/env python
"""Functionality to determine similarity betwen records."""
from __future__ import annotations

from typing import TYPE_CHECKING

from rapidfuzz import fuzz

from colrev.constants import Fields
from colrev.constants import FieldValues

if TYPE_CHECKING:
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
    try:
        author_similarity = (
            fuzz.ratio(record_a[Fields.AUTHOR], record_b[Fields.AUTHOR]) / 100
        )

        title_similarity = (
            fuzz.ratio(
                record_a[Fields.TITLE].lower().replace(":", "").replace("-", ""),
                record_b[Fields.TITLE].lower().replace(":", "").replace("-", ""),
            )
            / 100
        )

        # partial ratio (catching 2010-10 or 2001-2002)
        year_similarity = (
            fuzz.ratio(str(record_a[Fields.YEAR]), str(record_b[Fields.YEAR])) / 100
        )

        outlet_similarity = 0.0
        if record_b[Fields.CONTAINER_TITLE] and record_a[Fields.CONTAINER_TITLE]:
            outlet_similarity = (
                fuzz.ratio(
                    record_a[Fields.CONTAINER_TITLE],
                    record_b[Fields.CONTAINER_TITLE],
                )
                / 100
            )

        if str(record_a[Fields.JOURNAL]) != "nan":
            # Note: for journals papers, we expect more details
            volume_similarity = (
                1 if (record_a[Fields.VOLUME] == record_b[Fields.VOLUME]) else 0
            )

            number_similarity = (
                1 if (record_a[Fields.NUMBER] == record_b[Fields.NUMBER]) else 0
            )

            # Put more weight on other fields if the title is very common
            # ie., non-distinctive
            # The list is based on a large export of distinct papers, tabulated
            # according to titles and sorted by frequency
            if [record_a[Fields.TITLE], record_b[Fields.TITLE]] in [
                ["editorial", "editorial"],
                ["editorial introduction", "editorial introduction"],
                ["editorial notes", "editorial notes"],
                ["editor's comments", "editor's comments"],
                ["book reviews", "book reviews"],
                ["editorial note", "editorial note"],
                ["reviewer ackowledgment", "reviewer ackowledgment"],
            ]:
                weights = [0.175, 0, 0.175, 0.175, 0.275, 0.2]
            else:
                weights = [0.2, 0.25, 0.13, 0.2, 0.12, 0.1]

            # sim_names = [
            #     Fields.AUTHOR,
            #     Fields.TITLE,
            #     Fields.YEAR,
            #     "outlet",
            #     Fields.VOLUME,
            #     Fields.NUMBER,
            # ]
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
            # sim_names = [
            #     Fields.AUTHOR,
            #     Fields.TITLE,
            #     Fields.YEAR,
            #     "outlet",
            # ]
            similarities = [
                author_similarity,
                title_similarity,
                year_similarity,
                outlet_similarity,
            ]

        weighted_average = sum(
            similarities[g] * weights[g] for g in range(len(similarities))
        )

        # details = (
        #     "["
        #     + ",".join([sim_names[g] for g in range(len(similarities))])
        #     + "]"
        #     + "*weights_vecor^T = "
        #     + "["
        #     + ",".join([str(similarities[g]) for g in range(len(similarities))])
        #     + "]*"
        #     + "["
        #     + ",".join([str(weights[g]) for g in range(len(similarities))])
        #     + "]^T"
        # )
        # print(details)
        similarity_score = round(weighted_average, 4)
    except AttributeError:
        similarity_score = 0

    return similarity_score
