#!/usr/bin/env python3
"""Collection of utility functions"""
import pkgutil
import typing
import unicodedata
from pathlib import Path

import colrev.exceptions as colrev_exceptions


def retrieve_package_file(*, template_file: Path, target: Path) -> None:
    """Retrieve a file from the CoLRev package"""
    filedata = pkgutil.get_data("colrev", str(template_file))
    if filedata:
        with open(target, "w", encoding="utf8") as file:
            file.write(filedata.decode("utf-8"))
        return
    raise colrev_exceptions.RepoSetupError(f"{template_file} not available")


def get_package_file_content(*, file_path: Path) -> typing.Union[bytes, None]:
    """Get the content of a file in the CoLRev package"""
    return pkgutil.get_data("colrev", str(file_path))


def inplace_change(*, filename: Path, old_string: str, new_string: str) -> None:
    """Replace a string in a file"""
    with open(filename, encoding="utf8") as file:
        content = file.read()
        if old_string not in content:
            return
    with open(filename, "w", encoding="utf8") as file:
        content = content.replace(old_string, new_string)
        file.write(content)


def load_jinja_template(template_path: str) -> str:
    """Load a jinja template"""
    filedata_b = pkgutil.get_data("colrev", template_path)
    if filedata_b:
        filedata = filedata_b.decode("utf-8")
        filedata = filedata.replace("\n", "")
        filedata = filedata.replace("<br>", "\n")
        return filedata
    raise colrev_exceptions.RepoSetupError(f"{template_path} not available")


def remove_accents(*, input_str: str) -> str:
    """Replace the accents in a string"""

    def rmdiacritics(char: str) -> str:
        """
        Return the base character of char, by "removing" any
        diacritics like accents or curls and strokes and the like.
        """
        try:
            desc = unicodedata.name(char)
            cutoff = desc.find(" WITH ")
            if cutoff != -1:
                desc = desc[:cutoff]
                char = unicodedata.lookup(desc)
        except (KeyError, ValueError):
            pass  # removing "WITH ..." produced an invalid name
        return char

    try:
        nfkd_form = unicodedata.normalize("NFKD", input_str)
        wo_ac_list = [
            rmdiacritics(c) for c in nfkd_form if not unicodedata.combining(c)
        ]
        wo_ac = "".join(wo_ac_list)
    except ValueError:
        wo_ac = input_str
    return wo_ac


def percent_upper_chars(input_string: str) -> float:
    """Get the percentage of upper-case characters in a string"""
    return sum(map(str.isupper, input_string)) / len(input_string)


if __name__ == "__main__":
    pass
