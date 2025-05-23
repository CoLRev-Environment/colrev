#! /usr/bin/env python
"""Package check."""
from __future__ import annotations

import subprocess
import sys
from importlib import import_module
from importlib import util
from pathlib import Path
from typing import Any
from typing import Dict

import toml

import colrev.package_manager.package_base_classes as base_classes
from colrev.constants import Colors
from colrev.package_manager.package_base_classes import BASECLASS_MAP


def _check_package_installed(data: dict) -> bool:
    package_name = data["project"]["name"]
    try:
        subprocess.check_output(["pip", "show", package_name])
    except subprocess.CalledProcessError:
        print(
            f"Navigate to {Path.cwd()} and run: {Colors.GREEN} pip install -e .{Colors.END}"
        )

    return True


def _check_key_exists(data: Dict[str, Any], key: str) -> bool:
    keys = key.split(".")
    sub_data = data
    for k in keys:
        if k not in sub_data:
            return False
        sub_data = sub_data[k]
    return True


def _check_project(data: dict) -> bool:
    return _check_key_exists(data, "project")


def _check_project_name(data: dict) -> bool:
    return _check_key_exists(data, "project.name")


def _check_project_description(data: dict) -> bool:
    return _check_key_exists(data, "project.description")


def _check_project_version(data: dict) -> bool:
    return _check_key_exists(data, "project.version")


def _check_project_license(data: dict) -> bool:
    return _check_key_exists(data, "project.license")


def _check_project_authors(data: dict) -> bool:
    return _check_key_exists(data, "project.authors")


def _check_project_plugins_colrev(data: dict) -> bool:
    return _check_key_exists(data, "project.entry-points.colrev")


def _check_project_entry_points_colrev_keys(data: dict) -> bool:
    """Check if all colrev entry-points in pyproject.toml are valid."""

    colrev_data = data.get("project", {}).get("entry-points", {}).get("colrev", {})
    return all(key in BASECLASS_MAP for key in colrev_data)


# pylint: disable=too-many-locals
def _check_project_plugins_colrev_classes(data: dict) -> bool:
    colrev_data = data.get("project", {}).get("entry-points", {}).get("colrev", {})

    for interface_identifier, endpoint_str in colrev_data.items():
        module_path, class_name = endpoint_str.rsplit(":")

        package, module_path = module_path.split(".", 1)

        try:

            package_spec = util.find_spec(package)
            if not package_spec:
                return False
            if not package_spec.origin:
                return False
            package_path = Path(package_spec.origin).parent
            filepath = package_path / Path(module_path.replace(".", "/") + ".py")
            module_spec = util.spec_from_file_location(
                f"{package}.{module_path}", filepath
            )

            module = import_module(f"{package}.{module_path}")
            module_spec.loader.exec_module(module)  # type: ignore
            cls = getattr(module, class_name)  # type: ignore
            baseclass: str = BASECLASS_MAP.get(interface_identifier)  # type: ignore

            baseclass_class = getattr(base_classes, baseclass)
            if not issubclass(cls, baseclass_class):
                raise TypeError(
                    f"{cls} must implement all abstract methods of {baseclass_class}!"
                )
        except (ImportError, AttributeError) as exc:
            print(exc)
            return False
    return True


def _check_build_system(data: dict) -> bool:
    return _check_key_exists(data, "build-system")


# Define checks with preconditions
checks = {
    "check_project": {"method": _check_project, "preconditions": []},
    "check_project_name": {
        "method": _check_project_name,
        "preconditions": ["check_project"],
    },
    "check_project_description": {
        "method": _check_project_description,
        "preconditions": ["check_project"],
    },
    "check_project_version": {
        "method": _check_project_version,
        "preconditions": ["check_project"],
    },
    "check_project_license": {
        "method": _check_project_license,
        "preconditions": ["check_project"],
    },
    "check_project_authors": {
        "method": _check_project_authors,
        "preconditions": ["check_project"],
    },
    "check_project_plugins_colrev": {
        "method": _check_project_plugins_colrev,
        "preconditions": ["check_project"],
    },
    "check_project_plugins_colrev_keys": {
        "method": _check_project_entry_points_colrev_keys,
        "preconditions": ["_check_project_plugins_colrev"],
    },
    "check_project_plugins_colrev_classes": {
        "method": _check_project_plugins_colrev_classes,
        "preconditions": ["_check_project_plugins_colrev"],
    },
    "check_package_installed": {
        "method": _check_package_installed,
        "preconditions": [],
    },
    "check_build_system": {"method": _check_build_system, "preconditions": []},
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
            print(f"{Colors.RED}Check failed: {check_name}{Colors.END}")
            failed_checks.append(check_name)
        else:
            print(f"Check passed: {check_name}")

    return failed_checks


def main() -> None:
    """Run checks of a CoLRev project."""

    file_path = "pyproject.toml"

    try:
        with open(file_path, encoding="utf-8") as file:
            data = toml.load(file)

        failed_checks = _validate_structure(data, checks)
        if failed_checks:
            print("The pyproject.toml file structure is invalid. Failed checks:")
            for check in failed_checks:
                print(f" - {check}")
        else:
            print("Check passed: check_pyproject_valid_structure")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error reading pyproject.toml: {exc}")
        sys.exit(1)
