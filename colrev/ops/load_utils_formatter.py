#! /usr/bin/env python
"""Convenience functions for load formatting"""
from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

import colrev.env.language_service
from colrev.constants import Fields
from colrev.constants import FieldValues

if TYPE_CHECKING:
    import colrev.ops.load


# pylint: disable=too-few-public-methods


class LoadFormatter:
    """Load formatter class"""

    __LATEX_SPECIAL_CHAR_MAPPING = {
        '\\"u': "ü",
        "\\&": "&",
        '\\"o': "ö",
        '\\"a': "ä",
        '\\"A': "Ä",
        '\\"O': "Ö",
        '\\"U': "Ü",
        "\\textendash": "–",
        "\\textemdash": "—",
        "\\~a": "ã",
        "\\'o": "ó",
    }

    def __init__(self) -> None:
        self.language_service = colrev.env.language_service.LanguageService()

    def __apply_strict_requirements(self, *, record: colrev.record.Record) -> None:
        if Fields.DOI in record.data:
            record.data[Fields.DOI] = (
                record.data[Fields.DOI].replace("http://dx.doi.org/", "").upper()
            )
        if Fields.LANGUAGE in record.data and len(record.data[Fields.LANGUAGE]) != 3:
            self.language_service.unify_to_iso_639_3_language_codes(record=record)
        if Fields.NUMBER not in record.data and "issue" in record.data:
            record.data[Fields.NUMBER] = record.data.pop("issue")

    def __lower_case_keys(self, *, record: colrev.record.Record) -> None:
        # Consistently set keys to lower case
        lower_keys = [k.lower() for k in list(record.data.keys())]
        for key, n_key in zip(list(record.data.keys()), lower_keys):
            if key not in [Fields.ID, Fields.ENTRYTYPE]:
                record.data[n_key] = record.data.pop(key)

    def __unescape_latex(self, *, input_str: str) -> str:
        # Based on
        # https://en.wikibooks.org/wiki/LaTeX/Special_Characters

        for latex_char, repl_char in self.__LATEX_SPECIAL_CHAR_MAPPING.items():
            input_str = input_str.replace(latex_char, repl_char)

        input_str = input_str.replace("\\emph", "")
        input_str = input_str.replace("\\textit", "")

        return input_str

    def __unescape_html(self, *, input_str: str) -> str:
        input_str = html.unescape(input_str)
        if "<" in input_str:
            input_str = re.sub(r"<.*?>", "", input_str)
        return input_str

    def __unescape_field_values(self, *, record: colrev.record.Record) -> None:
        fields_to_process = [
            Fields.AUTHOR,
            Fields.YEAR,
            Fields.TITLE,
            Fields.JOURNAL,
            Fields.BOOKTITLE,
            Fields.SERIES,
            Fields.VOLUME,
            Fields.NUMBER,
            Fields.PAGES,
            Fields.DOI,
            Fields.ABSTRACT,
        ]

        for field in record.data:
            if field not in fields_to_process:
                continue
            if "\\" in record.data[field]:
                record.data[field] = self.__unescape_latex(input_str=record.data[field])
            if "<" in record.data[field]:
                record.data[field] = self.__unescape_html(input_str=record.data[field])

            record.data[field] = (
                record.data[field]
                .replace("\n", " ")
                .rstrip()
                .lstrip()
                .replace("{", "")
                .replace("}", "")
            )

    def __standardize_field_values(self, *, record: colrev.record.Record) -> None:
        if record.data.get(Fields.TITLE, FieldValues.UNKNOWN) != FieldValues.UNKNOWN:
            record.data[Fields.TITLE] = re.sub(
                r"\s+", " ", record.data[Fields.TITLE]
            ).rstrip(".")

        if Fields.YEAR in record.data and str(record.data[Fields.YEAR]).endswith(".0"):
            record.data[Fields.YEAR] = str(record.data[Fields.YEAR])[:-2]

        if Fields.PAGES in record.data:
            record.data[Fields.PAGES] = record.data[Fields.PAGES].replace("–", "--")
            if record.data[Fields.PAGES].count("-") == 1:
                record.data[Fields.PAGES] = record.data[Fields.PAGES].replace("-", "--")
            if record.data[Fields.PAGES].lower() == "n.pag":
                del record.data[Fields.PAGES]

        if record.data.get(Fields.VOLUME, "") == "ahead-of-print":
            del record.data[Fields.VOLUME]
        if record.data.get(Fields.NUMBER, "") == "ahead-of-print":
            del record.data[Fields.NUMBER]

        if Fields.URL in record.data and "login?url=https" in record.data[Fields.URL]:
            record.data[Fields.URL] = record.data[Fields.URL][
                record.data[Fields.URL].find("login?url=https") + 10 :
            ]

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the load formatter"""

        self.__apply_strict_requirements(record=record)

        if record.data[Fields.STATUS] != colrev.record.RecordState.md_retrieved:
            return

        self.__lower_case_keys(record=record)
        self.__unescape_field_values(record=record)
        self.__standardize_field_values(record=record)
