#! /usr/bin/env python
"""Functionality to determine similarity betwen records."""
from __future__ import annotations

import re
import typing

import pandas as pd
from bib_dedupe.bib_dedupe import block
from bib_dedupe.bib_dedupe import match
from bib_dedupe.bib_dedupe import prep
from rapidfuzz import fuzz

import colrev.env.utils
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


def container_is_abbreviated(record: colrev.record.record.Record) -> bool:
    """Check whether the container title is abbreviated"""
    if Fields.CONTAINER_TITLE in record.data:
        if record.data[Fields.CONTAINER_TITLE].count(".") > 2:
            return True
        if record.data[Fields.CONTAINER_TITLE].isupper():
            return True
    return False


def _format_authors_string_for_comparison(record: colrev.record.record.Record) -> None:
    if Fields.AUTHOR not in record.data:  # pragma: no cover
        return
    authors = str(record.data[Fields.AUTHOR]).lower()
    authors = colrev.env.utils.remove_accents(authors)

    # abbreviate first names
    # "Webster, Jane" -> "Webster, J"
    # also remove all special characters and do not include separators (and)
    authors_string = ""
    for author in authors.split(" and "):
        if "," in author:
            last_names = [
                word[0] for word in author.split(",")[1].split(" ") if len(word) > 0
            ]
            authors_string = (
                authors_string + author.split(",")[0] + " " + " ".join(last_names) + " "
            )
        else:
            authors_string = authors_string + author + " "
    authors_string = re.sub(r"[^A-Za-z0-9, ]+", "", authors_string.rstrip())
    record.data[Fields.AUTHOR] = authors_string


def _abbreviate_container_title(
    record: colrev.record.record.Record,
) -> None:
    def abbreviate_container(
        record: colrev.record.record.Record, *, min_len: int
    ) -> None:
        abbreviated_container = " ".join(
            [x[:min_len] for x in record.data[Fields.CONTAINER_TITLE].split(" ")]
        )
        record.data[Fields.CONTAINER_TITLE] = abbreviated_container

    def get_abbrev_container_min_len(record: colrev.record.record.Record) -> int:
        return min(
            len(x)
            for x in record.data[Fields.CONTAINER_TITLE].replace(".", "").split(" ")
        )

    if Fields.CONTAINER_TITLE not in record.data:
        record.data[Fields.CONTAINER_TITLE] = (
            record.data.get(Fields.JOURNAL, "")
            + record.data.get(Fields.BOOKTITLE, "")
            + record.data.get(Fields.SERIES, "")
        )

    if container_is_abbreviated(record):
        min_len = get_abbrev_container_min_len(record)
        abbreviate_container(record, min_len=min_len)


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


def _ensure_mandatory_fields(
    record_a: colrev.record.record.Record, record_b: colrev.record.record.Record
) -> None:
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
            record_a.data.get(mandatory_field, FieldValues.UNKNOWN)
            == FieldValues.UNKNOWN
        ):
            record_a.data[mandatory_field] = ""
        if (
            record_b.data.get(mandatory_field, FieldValues.UNKNOWN)
            == FieldValues.UNKNOWN
        ):
            record_b.data[mandatory_field] = ""


def get_record_similarity(
    record_a: colrev.record.record.Record, record_b: colrev.record.record.Record
) -> float:
    """Determine the similarity between two records (their masterdata)"""

    record_a = record_a.copy()
    record_b = record_b.copy()

    _ensure_mandatory_fields(record_a, record_b)

    _abbreviate_container_title(record_a)
    _abbreviate_container_title(record_b)
    _format_authors_string_for_comparison(record_a)
    _format_authors_string_for_comparison(record_b)

    return _get_similarity_detailed(record_a.get_data(), record_b.get_data())


def matches(
    record_a: colrev.record.record.Record, record_b: colrev.record.record.Record
) -> bool:
    """Determine whether two records match (correspond to the same entity)."""
    record_a_dict = record_a.copy().get_data()
    record_b_dict = record_b.copy().get_data()
    record_a_dict[Fields.ID] = "a"
    record_b_dict[Fields.ID] = "b"

    records_df = pd.DataFrame([record_a_dict, record_b_dict])
    records_df = prep(records_df, verbosity_level=0, cpu=1)
    blocked_df = block(records_df, verbosity_level=0, cpu=1)
    matched_df = match(blocked_df, verbosity_level=0, cpu=1)
    duplicate_label = matched_df["duplicate_label"]
    if len(duplicate_label) == 0:  # pragma: no cover
        return False

    return duplicate_label.iloc[0] == "duplicate"
