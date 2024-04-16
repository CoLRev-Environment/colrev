#!/usr/bin/env python3
"""Collection of utility functions"""
import operator
import pkgutil
import re
import typing
import unicodedata
from enum import Enum
from functools import reduce
from pathlib import Path

from jinja2 import Environment
from jinja2 import FunctionLoader
from jinja2.environment import Template

import colrev.exceptions as colrev_exceptions


def retrieve_package_file(*, template_file: Path, target: Path) -> None:
    """Retrieve a file from the CoLRev package"""
    try:
        filedata = pkgutil.get_data("colrev", str(template_file))
        if filedata:
            target.parent.mkdir(exist_ok=True, parents=True)
            with open(target, "w", encoding="utf8") as file:
                file.write(filedata.decode("utf-8"))
            return
    except FileNotFoundError:
        pass
    raise colrev_exceptions.TemplateNotAvailableError(str(template_file))


def get_package_file_content(
    *, module: str, filename: Path
) -> typing.Union[bytes, None]:
    """Get the content of a file in the CoLRev package"""
    return pkgutil.get_data(module, str(filename))


def inplace_change(*, filename: Path, old_string: str, new_string: str) -> None:
    """Replace a string in a file"""
    with open(filename, encoding="utf8") as file:
        content = file.read()
        if old_string not in content:
            return
    with open(filename, "w", encoding="utf8") as file:
        content = content.replace(old_string, new_string)
        file.write(content)


def get_template(template_path: str) -> Template:
    """Load a jinja template"""
    environment = Environment(
        loader=FunctionLoader(_load_jinja_template), autoescape=True
    )
    template = environment.get_template(template_path)
    return template


def _load_jinja_template(template_path: str) -> str:
    try:
        filedata_b = pkgutil.get_data("colrev", template_path)
        if filedata_b:
            filedata = filedata_b.decode("utf-8")
            filedata = filedata.replace("\n", "")
            filedata = filedata.replace("\r", "")
            filedata = filedata.replace("<br>", "\n")
            return filedata
    except FileNotFoundError:
        pass
    raise colrev_exceptions.TemplateNotAvailableError(template_path)


def remove_accents(input_str: str) -> str:
    """Replace the accents in a string"""

    nfkd_form = unicodedata.normalize("NFKD", input_str)
    wo_ac_list = [c for c in nfkd_form if not unicodedata.combining(c)]
    return "".join(wo_ac_list)


def percent_upper_chars(input_string: str) -> float:
    """Get the percentage of upper-case characters in a string"""

    input_string = re.sub(r"[^a-zA-Z]", "", input_string)
    if len(input_string) == 0:
        return 0.0
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
            if str(obj) == "1.0":  # pragma: no cover
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
        module="colrev.env", filename=Path("complementary_material_keywords.txt")
    )
    if filedata:
        complementary_material_keywords = list(filedata.decode("utf-8").splitlines())

    return complementary_material_keywords


def load_complementary_material_strings() -> list:
    """Load the list of exact strings identifying complementary materials"""

    complementary_material_keywords = []
    filedata = get_package_file_content(
        module="colrev.env", filename=Path("complementary_material_strings.txt")
    )
    if filedata:
        complementary_material_keywords = list(filedata.decode("utf-8").splitlines())

    return complementary_material_keywords


def load_complementary_material_prefixes() -> list:
    """Load the list of prefixes identifying complementary materials"""

    complementary_material_keywords = []
    filedata = get_package_file_content(
        module="colrev.env", filename=Path("complementary_material_prefixes.txt")
    )
    if filedata:
        complementary_material_keywords = list(filedata.decode("utf-8").splitlines())

    return complementary_material_keywords


def get_by_path(root: dict, items: typing.List[str]) -> typing.Any:
    """Access a nested object in root by item sequence."""

    return reduce(operator.getitem, items, root)


def dict_set_nested(root: dict, keys: typing.List[str], value: typing.Any) -> None:
    """Set dict value by nested key, this works on empty dict"""
    for key in keys[:-1]:
        root = root.setdefault(key, {})
    root[keys[-1]] = value
