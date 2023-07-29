#! /usr/bin/env python
"""Convenience functions for load formatting"""
from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

import colrev.env.language_service

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
        if "doi" in record.data:
            record.data["doi"] = (
                record.data["doi"].replace("http://dx.doi.org/", "").upper()
            )
        if "language" in record.data and len(record.data["language"]) != 3:
            self.language_service.unify_to_iso_639_3_language_codes(record=record)
        if "number" not in record.data and "issue" in record.data:
            record.data["number"] = record.data.pop("issue")

    def __lower_case_keys(self, *, record: colrev.record.Record) -> None:
        # Consistently set keys to lower case
        lower_keys = [k.lower() for k in list(record.data.keys())]
        for key, n_key in zip(list(record.data.keys()), lower_keys):
            if key not in ["ID", "ENTRYTYPE"]:
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
            "author",
            "year",
            "title",
            "journal",
            "booktitle",
            "series",
            "volume",
            "number",
            "pages",
            "doi",
            "abstract",
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
        if record.data.get("title", "UNKNOWN") != "UNKNOWN":
            record.data["title"] = re.sub(r"\s+", " ", record.data["title"]).rstrip(".")

        if "year" in record.data and str(record.data["year"]).endswith(".0"):
            record.data["year"] = str(record.data["year"])[:-2]

        if "pages" in record.data:
            record.data["pages"] = record.data["pages"].replace("–", "--")
            if record.data["pages"].count("-") == 1:
                record.data["pages"] = record.data["pages"].replace("-", "--")
            if record.data["pages"].lower() == "n.pag":
                del record.data["pages"]

        if record.data.get("volume", "") == "ahead-of-print":
            del record.data["volume"]
        if record.data.get("number", "") == "ahead-of-print":
            del record.data["number"]

        if "url" in record.data and "login?url=https" in record.data["url"]:
            record.data["url"] = record.data["url"][
                record.data["url"].find("login?url=https") + 10 :
            ]

    def run(self, *, record: colrev.record.Record) -> None:
        """Run the load formatter"""

        self.__apply_strict_requirements(record=record)

        if record.data["colrev_status"] != colrev.record.RecordState.md_retrieved:
            return

        self.__lower_case_keys(record=record)
        self.__unescape_field_values(record=record)
        self.__standardize_field_values(record=record)
