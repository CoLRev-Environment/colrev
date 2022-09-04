#!/usr/bin/env python3
import pkgutil
import unicodedata
from pathlib import Path

# Collection of utility functions


def retrieve_package_file(*, template_file: Path, target: Path) -> None:
    filedata = pkgutil.get_data(__name__, str(template_file))
    if filedata:
        with open(target, "w", encoding="utf8") as file:
            file.write(filedata.decode("utf-8"))


def load_jinja_template(template_path) -> str:
    filedata_b = pkgutil.get_data(__name__, template_path)
    if filedata_b:
        filedata = filedata_b.decode("utf-8")
        filedata = filedata.replace("\n", "")
        filedata = filedata.replace("<br>", "\n")
        return filedata
    return ""


def remove_accents(*, input_str: str) -> str:
    def rmdiacritics(char):
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


if __name__ == "__main__":
    pass
