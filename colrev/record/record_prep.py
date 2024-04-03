#! /usr/bin/env python
"""Functionality for individual records."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from nameparser import HumanName

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.packages.prep.utils as prep_utils
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues

if TYPE_CHECKING:  # pragma: no cover
    import colrev.review_manager
    import colrev.record.qm.quality_model

# pylint: disable=too-many-lines
# pylint: disable=too-many-public-methods


class PrepRecord(colrev.record.record.Record):
    """The PrepRecord class provides a range of convenience functions for record preparation"""

    @classmethod
    def format_author_field(cls, *, input_string: str) -> str:
        """Format the author field (recognizing first/last names based on HumanName parser)"""

        def mostly_upper_case(input_string: str) -> bool:
            if not re.match(r"[a-zA-Z]+", input_string):
                return False
            input_string = input_string.replace(".", "").replace(",", "")
            words = input_string.split()
            return sum(word.isupper() for word in words) / len(words) > 0.8

        input_string = input_string.replace("\n", " ")
        # DBLP appends identifiers to non-unique authors
        input_string = str(re.sub(r"[0-9]{4}", "", input_string))

        if " and " in input_string:
            names = input_string.split(" and ")
        elif input_string.count(";") > 1:
            names = input_string.split(";")
        elif input_string.count(",") > 1:
            names = input_string.split(" ")
        else:
            names = [input_string]
        author_string = ""
        for name in names:
            # Note: https://github.com/derek73/python-nameparser
            # is very effective (maybe not perfect)

            parsed_name = HumanName(name)
            if mostly_upper_case(input_string.replace(" and ", "").replace("Jr", "")):
                parsed_name.capitalize(force=True)

            # Fix typical parser error
            if parsed_name.last == "" and parsed_name.title != "":
                parsed_name.last = parsed_name.title

            # pylint: disable=chained-comparison
            # Fix: when first names are abbreviated, nameparser creates errors:
            if (
                len(parsed_name.last) <= 3
                and parsed_name.last.isupper()
                and len(parsed_name.first) > 3
                and not parsed_name.first.isupper()
            ):
                # in these casees, first and last names are confused
                author_name_string = parsed_name.first + ", " + parsed_name.last
            else:
                parsed_name.string_format = "{last} {suffix}, {first} {middle}"
                # '{last} {suffix}, {first} ({nickname}) {middle}'
                author_name_string = str(parsed_name).replace(" , ", ", ")
                # Note: there are errors for the following author:
                # JR Cromwell and HK Gardner
                # The JR is probably recognized as Junior.
                # Check whether this is fixed in the Grobid name parser

            if author_string == "":
                author_string = author_name_string
            else:
                author_string = author_string + " and " + author_name_string

        return author_string

    @classmethod
    def _format_authors_string_for_comparison(
        cls, *, record: colrev.record.record.Record
    ) -> None:
        if Fields.AUTHOR not in record.data:
            return
        authors = record.data[Fields.AUTHOR]
        authors = str(authors).lower()
        authors_string = ""
        authors = colrev.env.utils.remove_accents(authors)

        # abbreviate first names
        # "Webster, Jane" -> "Webster, J"
        # also remove all special characters and do not include separators (and)
        for author in authors.split(" and "):
            if "," in author:
                last_names = [
                    word[0] for word in author.split(",")[1].split(" ") if len(word) > 0
                ]
                authors_string = (
                    authors_string
                    + author.split(",")[0]
                    + " "
                    + " ".join(last_names)
                    + " "
                )
            else:
                authors_string = authors_string + author + " "
        authors_string = re.sub(r"[^A-Za-z0-9, ]+", "", authors_string.rstrip())
        record.data[Fields.AUTHOR] = authors_string

    def container_is_abbreviated(self) -> bool:
        """Check whether the container title is abbreviated"""
        if Fields.JOURNAL in self.data:
            if self.data[Fields.JOURNAL].count(".") > 2:
                return True
            if self.data[Fields.JOURNAL].isupper():
                return True
        if Fields.BOOKTITLE in self.data:
            if self.data[Fields.BOOKTITLE].count(".") > 2:
                return True
            if self.data[Fields.BOOKTITLE].isupper():
                return True
        # add heuristics? (e.g., Hawaii Int Conf Syst Sci)
        return False

    @classmethod
    def _abbreviate_container_titles(
        cls,
        *,
        record: colrev.record.record_prep.PrepRecord,
        retrieved_record: colrev.record.record_prep.PrepRecord,
    ) -> None:
        def abbreviate_container(
            *, record: colrev.record.record.Record, min_len: int
        ) -> None:
            if Fields.JOURNAL in record.data:
                record.data[Fields.JOURNAL] = " ".join(
                    [x[:min_len] for x in record.data[Fields.JOURNAL].split(" ")]
                )

        def get_abbrev_container_min_len(*, record: colrev.record.record.Record) -> int:
            min_len = -1
            if Fields.JOURNAL in record.data:
                min_len = min(
                    len(x)
                    for x in record.data[Fields.JOURNAL].replace(".", "").split(" ")
                )
            if Fields.BOOKTITLE in record.data:
                min_len = min(
                    len(x)
                    for x in record.data[Fields.BOOKTITLE].replace(".", "").split(" ")
                )
            return min_len

        if record.container_is_abbreviated():
            min_len = get_abbrev_container_min_len(record=record)
            abbreviate_container(record=retrieved_record, min_len=min_len)
            abbreviate_container(record=record, min_len=min_len)
        if retrieved_record.container_is_abbreviated():
            min_len = get_abbrev_container_min_len(record=retrieved_record)
            abbreviate_container(record=record, min_len=min_len)
            abbreviate_container(record=retrieved_record, min_len=min_len)

    @classmethod
    def _prep_records_for_similarity(
        cls,
        *,
        record: colrev.record.record_prep.PrepRecord,
        retrieved_record: colrev.record.record_prep.PrepRecord,
    ) -> None:
        cls._abbreviate_container_titles(
            record=record, retrieved_record=retrieved_record
        )

        if Fields.TITLE in record.data:
            record.data[Fields.TITLE] = record.data[Fields.TITLE][:90]
        if Fields.TITLE in retrieved_record.data:
            retrieved_record.data[Fields.TITLE] = retrieved_record.data[Fields.TITLE][
                :90
            ]

        if Fields.AUTHOR in record.data:
            cls._format_authors_string_for_comparison(record=record)
            record.data[Fields.AUTHOR] = record.data[Fields.AUTHOR][:45]
        if Fields.AUTHOR in retrieved_record.data:
            cls._format_authors_string_for_comparison(record=retrieved_record)
            retrieved_record.data[Fields.AUTHOR] = retrieved_record.data[Fields.AUTHOR][
                :45
            ]
        if not (
            Fields.VOLUME in record.data and Fields.VOLUME in retrieved_record.data
        ):
            record.data[Fields.VOLUME] = "nan"
            retrieved_record.data[Fields.VOLUME] = "nan"
        if not (
            Fields.NUMBER in record.data and Fields.NUMBER in retrieved_record.data
        ):
            record.data[Fields.NUMBER] = "nan"
            retrieved_record.data[Fields.NUMBER] = "nan"
        if not (Fields.PAGES in record.data and Fields.PAGES in retrieved_record.data):
            record.data[Fields.PAGES] = "nan"
            retrieved_record.data[Fields.PAGES] = "nan"
        # Sometimes, the number of pages is provided (not the range)
        elif not (
            "--" in record.data[Fields.PAGES]
            and "--" in retrieved_record.data[Fields.PAGES]
        ):
            record.data[Fields.PAGES] = "nan"
            retrieved_record.data[Fields.PAGES] = "nan"

        if Fields.YEAR in record.data and Fields.YEAR in retrieved_record.data:
            if record.data[Fields.YEAR] == FieldValues.FORTHCOMING:
                record.data[Fields.YEAR] = retrieved_record.data[Fields.YEAR]
            if retrieved_record.data[Fields.YEAR] == FieldValues.FORTHCOMING:
                retrieved_record.data[Fields.YEAR] = record.data[Fields.YEAR]

    @classmethod
    def get_retrieval_similarity(
        cls,
        *,
        record_original: colrev.record.record.Record,
        retrieved_record_original: colrev.record.record.Record,
        same_record_type_required: bool = True,
    ) -> float:
        """Get the retrieval similarity between the record and a retrieved record"""

        if same_record_type_required:
            if record_original.data.get(
                Fields.ENTRYTYPE, "a"
            ) != retrieved_record_original.data.get(Fields.ENTRYTYPE, "b"):
                return 0.0

        record = record_original.copy_prep_rec()
        retrieved_record = retrieved_record_original.copy_prep_rec()

        cls._prep_records_for_similarity(
            record=record, retrieved_record=retrieved_record
        )

        if "editorial" in record.data.get(Fields.TITLE, "NA").lower():
            if not all(x in record.data for x in [Fields.VOLUME, Fields.NUMBER]):
                return 0.0

        similarity = cls.get_record_similarity(record, retrieved_record)
        return similarity

    def format_if_mostly_upper(self, *, key: str, case: str = "sentence") -> None:
        """Format the field if it is mostly in upper case"""

        if key not in self.data or self.data[key] == FieldValues.UNKNOWN:
            return

        if colrev.env.utils.percent_upper_chars(self.data[key]) < 0.6:
            return

        # Note: the truecase package is not very reliable (yet)

        self.data[key] = self.data[key].replace("\n", " ")

        if case == "sentence":
            self.data[key] = self.data[key].capitalize()
        elif case == "title":
            self.data[key] = self.data[key].title()
        else:
            raise colrev_exceptions.ParameterError(
                parameter="case", value=case, options=["sentence", "title"]
            )

        self.data[key] = prep_utils.capitalize_entities(self.data[key])

    def rename_fields_based_on_mapping(self, *, mapping: dict) -> None:
        """Convenience function for the prep scripts (to rename fields)"""

        mapping = {k.lower(): v.lower() for k, v in mapping.items()}
        prior_keys = list(self.data.keys())
        # Note : warning: do not create a new dict.
        for key in prior_keys:
            if key.lower() in mapping:
                self.rename_field(key=key, new_key=mapping[key.lower()])

    def unify_pages_field(self) -> None:
        """Unify the format of the page field"""
        if Fields.PAGES not in self.data:
            return
        if not isinstance(self.data[Fields.PAGES], str):
            return
        if 1 == self.data[Fields.PAGES].count("-"):
            self.data[Fields.PAGES] = self.data[Fields.PAGES].replace("-", "--")
        self.data[Fields.PAGES] = (
            self.data[Fields.PAGES]
            .replace("–", "--")
            .replace("----", "--")
            .replace(" -- ", "--")
            .rstrip(".")
        )
        if re.match(r"^\d+\-\-\d+$", self.data[Fields.PAGES]):
            from_page, to_page = re.findall(r"(\d+)", self.data[Fields.PAGES])
            if len(from_page) > len(to_page):
                self.data[Fields.PAGES] = (
                    f"{from_page}--{from_page[:-len(to_page)]}{to_page}"
                )

    def fix_name_particles(self) -> None:
        """Fix the name particles in the author field"""
        if Fields.AUTHOR not in self.data:
            return
        names = self.data[Fields.AUTHOR].split(" and ")
        for ind, name in enumerate(names):
            for prefix in [
                "van den",
                "von den",
                "van der",
                "von der",
                "vom",
                "van",
                "von",
            ]:
                if name.startswith(f"{prefix} "):
                    if "," in name:
                        name = "{" + name.replace(", ", "}, ")
                    else:
                        name = "{" + name + "}"
                if name.endswith(f" {prefix}"):
                    if "," in name:
                        name = (
                            "{"
                            + prefix
                            + " "
                            + name[: -len(prefix)].replace(", ", "}, ")
                        )
                    else:
                        name = "{" + prefix + " " + name[: -len(prefix)] + "}"

                names[ind] = name
        self.data[Fields.AUTHOR] = " and ".join(names)
