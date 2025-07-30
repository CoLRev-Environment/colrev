#! /usr/bin/env python
"""Class for the preparation of records."""
from __future__ import annotations

import re

from nameparser import HumanName

import colrev.env.utils
import colrev.exceptions as colrev_exceptions
import colrev.record.record
from colrev.constants import Fields
from colrev.constants import FieldValues


NO_CAPS = ["of", "for", "the", "and"]
ALL_CAPS = ["IEEE", "ACM", "M&A", "B2B", "B2C", "C2C", "I"]
ALL_CAPS_DICT = {r"U\.S\.": "U.S."}


def capitalize_entities(input_str: str) -> str:
    """Utility function to capitalize entities"""

    for all_cap in ALL_CAPS:
        input_str = re.sub(
            rf"\b{all_cap.lower()}\b", all_cap.upper(), input_str, flags=re.IGNORECASE
        )

    for all_cap, repl in ALL_CAPS_DICT.items():
        input_str = re.sub(
            rf"\b{all_cap.lower()}\b", repl, input_str, flags=re.IGNORECASE
        )

    for no_cap in NO_CAPS:
        if input_str.lower().startswith(no_cap):
            continue
        input_str = re.sub(
            rf"\b{no_cap.lower()}\b", no_cap, input_str, flags=re.IGNORECASE
        )

    input_str = input_str.replace(" i'", " I'").replace("'S ", "'s ")

    input_str = re.sub(r"it-(\w)", r"IT-\1", input_str, flags=re.IGNORECASE)
    input_str = re.sub(r"is-(\w)", r"IS-\1", input_str, flags=re.IGNORECASE)

    return input_str


class PrepRecord(colrev.record.record.Record):
    """The PrepRecord class provides a range of Function for record preparation"""

    @classmethod
    def format_author_field(cls, input_string: str) -> str:
        """Format the author field (recognizing first/last names based on HumanName parser)"""

        def mostly_upper_case(input_string: str) -> bool:
            input_string = input_string.replace(".", "").replace(",", "")
            words = input_string.split()
            if len(words) == 0:
                return False
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

    def format_if_mostly_upper(self, key: str, *, case: str = "sentence") -> None:
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

        self.data[key] = capitalize_entities(self.data[key])

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
