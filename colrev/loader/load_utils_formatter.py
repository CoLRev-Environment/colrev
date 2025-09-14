#! /usr/bin/env python
"""Function for load formatting"""
from __future__ import annotations

import html
import re

import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods


class LoadFormatter:
    """Load formatter class"""

    # Based on
    # https://en.wikibooks.org/wiki/LaTeX/Special_Characters
    _LATEX_SPECIAL_CHAR_MAPPING = {
        '\\"a': "ä",
        '\\"o': "ö",
        '\\"u': "ü",
        '\\"A': "Ä",
        '\\"O': "Ö",
        '\\"U': "Ü",
        "\\&": "&",
        "\\textendash": "–",
        "\\textemdash": "—",
        "\\~a": "ã",
        "\\'o": "ó",
        "\\emph": "",
        "\\textit": "",
        "\\'e": "é",
        "\\`e": "è",
        '"a': "ä",
        '"o': "ö",
        '"u': "ü",
    }

    _FIELDS_TO_PROCESS = [
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

    def __init__(self) -> None:
        self.language_service = colrev.env.language_service.LanguageService()

    def _fix_author_particles(self, record: colrev.record.record.Record) -> None:
        # Fix the name particles in the author field
        if Fields.AUTHOR in record.data:
            names = record.data[Fields.AUTHOR].split(" and ")
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
                                + name[: -len(prefix)].rstrip().replace(", ", "}, ")
                            )
                        else:
                            name = (
                                "{" + prefix + " " + name[: -len(prefix)].rstrip() + "}"
                            )

                    names[ind] = name
            record.data[Fields.AUTHOR] = " and ".join(names)

    def _format_doi(self, record: colrev.record.record.Record) -> None:
        if Fields.DOI in record.data:
            record.data[Fields.DOI] = (
                record.data[Fields.DOI]
                .lower()
                .replace("https://", "http://")
                .replace("dx.doi.org", "doi.org")
                .replace("http://doi.org/", "")
                .upper()
            )

    def _unify_language(self, record: colrev.record.record.Record) -> None:
        if Fields.LANGUAGE in record.data and len(record.data[Fields.LANGUAGE]) != 3:
            try:
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data[Fields.LANGUAGE]

    def _rename_issue_to_number(self, record: colrev.record.record.Record) -> None:
        if Fields.NUMBER not in record.data and "issue" in record.data:
            record.data[Fields.NUMBER] = record.data.pop("issue")

    def _apply_strict_requirements(
        self, *, record: colrev.record.record.Record
    ) -> None:

        self._fix_author_particles(record)
        self._format_doi(record)
        self._unify_language(record)
        self._rename_issue_to_number(record)

    def _unescape_latex(self, *, input_str: str) -> str:
        for latex_char, repl_char in self._LATEX_SPECIAL_CHAR_MAPPING.items():
            input_str = input_str.replace(f"{{{latex_char}}}", repl_char)
            input_str = input_str.replace(latex_char, repl_char)
        return input_str

    def _unescape_html(self, *, input_str: str) -> str:
        input_str = html.unescape(input_str)
        if "<" in input_str:
            input_str = re.sub(r"<.*?>", "", input_str)
        return input_str

    def _unescape_field_values(self, *, record: colrev.record.record.Record) -> None:
        for field in record.data:
            if field not in self._FIELDS_TO_PROCESS:
                continue
            record.data[field] = str(record.data[field])
            if "\\" in record.data[field]:
                record.data[field] = self._unescape_latex(input_str=record.data[field])
            record.data[field] = self._unescape_html(input_str=record.data[field])

            record.data[field] = record.data[field].replace("\n", " ").rstrip().lstrip()

    def _standardize_field_values(self, *, record: colrev.record.record.Record) -> None:
        if record.data.get(Fields.TITLE, FieldValues.UNKNOWN) != FieldValues.UNKNOWN:
            record.data[Fields.TITLE] = re.sub(
                r"\s+", " ", record.data[Fields.TITLE]
            ).rstrip(".")

        # Fix floating point years
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

    def run(self, record: colrev.record.record.Record) -> None:
        """Run the load formatter"""

        self._apply_strict_requirements(record=record)

        if (
            Fields.STATUS in record.data
            and record.data[Fields.STATUS] != RecordState.md_retrieved
        ):
            return

        self._unescape_field_values(record=record)
        self._standardize_field_values(record=record)
