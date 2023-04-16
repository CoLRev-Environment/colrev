#!/usr/bin/env python3
"""Collection of utility functions"""
import pkgutil
import typing
import unicodedata
from enum import Enum
from pathlib import Path

from jinja2 import Environment
from jinja2 import FunctionLoader
from jinja2.environment import Template

import colrev.exceptions as colrev_exceptions


def retrieve_package_file(*, template_file: Path, target: Path) -> None:
    """Retrieve a file from the CoLRev package"""
    filedata = pkgutil.get_data("colrev", str(template_file))
    if not filedata:
        raise colrev_exceptions.RepoSetupError(f"{template_file} not available")

    target.parent.mkdir(exist_ok=True, parents=True)
    with open(target, "w", encoding="utf8") as file:
        file.write(filedata.decode("utf-8"))


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


def get_template(*, template_path: str) -> Template:
    """Load a jinja template"""
    environment = Environment(
        loader=FunctionLoader(__load_jinja_template), autoescape=True
    )
    template = environment.get_template(template_path)
    return template


def __load_jinja_template(template_path: str) -> str:
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


def custom_asdict_factory(data) -> dict:  # type: ignore
    """Custom asdict factory for (dataclass)object-to-dict conversion"""

    def convert_value(obj: object) -> object:
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, float):
            # Save 1.0 as 1 per default to avoid parsing issues
            # e.g., with the web ui
            if str(obj) == "1.0":
                return 1
        if isinstance(obj, list):
            if all(isinstance(el, Path) for el in obj):
                return [str(el) for el in obj]
        return obj

    return {k: convert_value(v) for k, v in data}


def load_complementary_material_keywords() -> list:
    """Load the list of keywords identifying complementary materials"""
    complementary_material_keywords = []
    filedata = get_package_file_content(
        file_path=Path("template/ops/complementary_material_keywords.txt")
    )
    if filedata:
        complementary_material_keywords = list(filedata.decode("utf-8").splitlines())

    return complementary_material_keywords


def load_complementary_material_strings() -> list:
    """Load the list of exact strings identifying complementary materials"""

    complementary_material_keywords = []
    filedata = get_package_file_content(
        file_path=Path("template/ops/complementary_material_strings.txt")
    )
    if filedata:
        complementary_material_keywords = list(filedata.decode("utf-8").splitlines())

    return complementary_material_keywords


if __name__ == "__main__":
    pass
