#! /usr/bin/env python
"""Package check."""
from __future__ import annotations

import sys
from typing import Any
from typing import Dict

import toml


def _check_key_exists(data: Dict[str, Any], key: str) -> bool:
    keys = key.split(".")
    sub_data = data
    for k in keys:
        if k not in sub_data:
            return False
        sub_data = sub_data[k]
    return True


def _check_value(data: Dict[str, Any], key: str, expected: Any) -> bool:
    keys = key.split(".")
    sub_data = data
    for k in keys[:-1]:
        if k not in sub_data:
            return False
        sub_data = sub_data[k]
    return sub_data.get(keys[-1]) == expected


def _check_list_length(data: Dict[str, Any], key: str, expected_length: int) -> bool:
    keys = key.split(".")
    sub_data = data
    for k in keys:
        if k not in sub_data:
            return False
        sub_data = sub_data[k]
    return len(sub_data) == expected_length


def _check_tool_poetry(data: dict) -> bool:
    return _check_key_exists(data, "tool.poetry")


def __check_tool_poetry_name(data: dict) -> bool:
    return _check_value(data, "tool.poetry.name", "colrev.genai")


def __check_tool_poetry_description(data: dict) -> bool:
    return _check_value(data, "tool.poetry.description", "CoLRev package for GenAI")


def __check_tool_poetry_version(data: dict) -> bool:
    return _check_value(data, "tool.poetry.version", "0.1.0")


def __check_tool_poetry_license(data: dict) -> bool:
    return _check_value(data, "tool.poetry.license", "MIT")


def __check_tool_poetry_authors(data: dict) -> bool:
    return _check_list_length(data, "tool.poetry.authors", 2)


def _check_build_system(data: dict) -> bool:
    return _check_key_exists(data, "build-system")


# Define checks with preconditions
checks = {
    "_check_tool_poetry": {"method": _check_tool_poetry, "preconditions": []},
    "__check_tool_poetry_name": {
        "method": __check_tool_poetry_name,
        "preconditions": ["_check_tool_poetry"],
    },
    "__check_tool_poetry_description": {
        "method": __check_tool_poetry_description,
        "preconditions": ["_check_tool_poetry"],
    },
    "__check_tool_poetry_version": {
        "method": __check_tool_poetry_version,
        "preconditions": ["_check_tool_poetry"],
    },
    "__check_tool_poetry_license": {
        "method": __check_tool_poetry_license,
        "preconditions": ["_check_tool_poetry"],
    },
    "__check_tool_poetry_authors": {
        "method": __check_tool_poetry_authors,
        "preconditions": ["_check_tool_poetry"],
    },
    "_check_build_system": {"method": _check_build_system, "preconditions": []},
}


def _validate_structure(data: dict, checks_dict: dict) -> list:
    failed_checks = []
    for check_name, check in checks_dict.items():
        precondition_failed = any(
            precondition in failed_checks for precondition in check["preconditions"]
        )
        if precondition_failed:
            print(f"Skipping {check_name} due to failed preconditions.")
            continue

        method = check["method"]
        result = method(data)

        if not result:
            print(f"Check failed: {check_name}")
            failed_checks.append(check_name)
        else:
            print(f"Check passed: {check_name}")

    return failed_checks


def main() -> None:
    """Run checks of a CoLRev project."""

    file_path = "pyproject.toml"
    try:
        with open(file_path, encoding="utf-8") as f:
            data = toml.load(f)

        failed_checks = _validate_structure(data, checks)
        if failed_checks:
            print("The pyproject.toml file structure is invalid. Failed checks:")
            for check in failed_checks:
                print(f" - {check}")
        else:
            print("The pyproject.toml file structure is valid.")
    except Exception as e:  # pylint: disable=broad-except
        print(f"Error reading pyproject.toml: {e}")
        sys.exit(1)
