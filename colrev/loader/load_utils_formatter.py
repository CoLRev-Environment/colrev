#! /usr/bin/env python
"""Function for load formatting."""

from __future__ import annotations

import html
import re
import logging
import itertools
import os
import string

import typing
from pathlib import Path
import colrev.env.language_service
import colrev.exceptions as colrev_exceptions
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState

# pylint: disable=too-few-public-methods


def run_fix_bib_file(filename: Path, *, logger: logging.Logger) -> None:
    """Fix a BibTeX file."""
    # pylint: disable=too-many-statements

    def fix_key(
        file: typing.IO, line: bytes, replacement_line: bytes, seekpos: int
    ) -> int:
        logger.info(
            f"Fix invalid key: \n{line.decode('utf-8')}"
            f"{replacement_line.decode('utf-8')}"
        )
        line = file.readline()
        remaining = line + file.read()
        file.seek(seekpos)
        file.write(replacement_line)
        seekpos = file.tell()
        file.flush()
        os.fsync(file)
        file.write(remaining)
        file.truncate()  # if the replacement is shorter...
        file.seek(seekpos)
        return seekpos

    def generate_next_unique_id(
        *,
        temp_id: str,
        existing_ids: list,
    ) -> str:
        """Get the next unique ID."""
        order = 0
        letters = list(string.ascii_lowercase)
        next_unique_id = temp_id
        appends: list = []
        while next_unique_id.lower() in [i.lower() for i in existing_ids]:
            if len(appends) == 0:
                order += 1
                appends = list(itertools.product(letters, repeat=order))
            next_unique_id = temp_id + "".join(list(appends.pop(0)))
        temp_id = next_unique_id
        return temp_id

    if filename is not None:

        with open(filename, encoding="utf8") as bibtex_file:
            contents = bibtex_file.read()
            if len(contents) < 10:
                return

        # Errors to fix before pybtex loading:
        # - set_incremental_ids (otherwise, not all records will be loaded)
        # - fix_keys (keys containing white spaces)
        record_ids: typing.List[str] = []
        with open(filename, "r+b") as file:
            seekpos = file.tell()
            line = file.readline()
            while line:
                if b"@" in line[:3]:
                    current_id = line[line.find(b"{") + 1 : line.rfind(b",")]
                    current_id_str = current_id.decode("utf-8").lstrip().rstrip()

                    if any(x in current_id_str for x in [";"]):
                        replacement_line = re.sub(
                            r";",
                            r"_",
                            line.decode("utf-8"),
                        ).encode("utf-8")
                        seekpos = fix_key(file, line, replacement_line, seekpos)

                    if current_id_str in record_ids:
                        next_id = generate_next_unique_id(
                            temp_id=current_id_str, existing_ids=record_ids
                        )
                        logger.info(f"Fix duplicate ID: {current_id_str} >> {next_id}")

                        replacement_line = (
                            line.decode("utf-8")
                            .replace(current_id.decode("utf-8"), next_id)
                            .encode("utf-8")
                        )

                        line = file.readline()
                        remaining = line + file.read()
                        file.seek(seekpos)
                        file.write(replacement_line)
                        seekpos = file.tell()
                        file.flush()
                        os.fsync(file)
                        file.write(remaining)
                        file.truncate()  # if the replacement is shorter...
                        file.seek(seekpos)

                        record_ids.append(next_id)

                    else:
                        record_ids.append(current_id_str)

                # Fix keys
                if re.match(
                    r"^\s*[a-zA-Z0-9]+\s+[a-zA-Z0-9]+\s*\=", line.decode("utf-8")
                ):
                    replacement_line = re.sub(
                        r"(^\s*)([a-zA-Z0-9]+)\s+([a-zA-Z0-9]+)(\s*\=)",
                        r"\1\2_\3\4",
                        line.decode("utf-8"),
                    ).encode("utf-8")
                    seekpos = fix_key(file, line, replacement_line, seekpos)

                # Fix IDs
                if re.match(
                    r"^@[a-zA-Z0-9]+\{[a-zA-Z0-9]+\s[a-zA-Z0-9]+,",
                    line.decode("utf-8"),
                ):
                    replacement_line = re.sub(
                        r"^(@[a-zA-Z0-9]+\{[a-zA-Z0-9]+)\s([a-zA-Z0-9]+,)",
                        r"\1_\2",
                        line.decode("utf-8"),
                    ).encode("utf-8")
                    seekpos = fix_key(file, line, replacement_line, seekpos)

                seekpos = file.tell()
                line = file.readline()


def run_resolve_crossref(records: dict, *, logger: logging.Logger) -> None:
    """Resolve cross-references between records."""
    # Handle cross-references between records
    crossref_ids = []
    for record_dict in records.values():
        if "crossref" not in record_dict:
            continue

        crossref_record = records.get(record_dict["crossref"], None)

        if not crossref_record:
            logger.error(f"crossref record (ID={record_dict['crossref']}) not found")
            continue
        crossref_ids.append(crossref_record["ID"])
        for key, value in crossref_record.items():
            if key not in record_dict:
                record_dict[key] = value
        del record_dict["crossref"]

    for crossref_id in crossref_ids:
        del records[crossref_id]


class LoadFormatter:
    """Load formatter class."""

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
        """Initialize the instance."""
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
        """Run the load formatter."""
        self._apply_strict_requirements(record=record)

        if (
            Fields.STATUS in record.data
            and record.data[Fields.STATUS] != RecordState.md_retrieved
        ):
            return

        self._unescape_field_values(record=record)
        self._standardize_field_values(record=record)
