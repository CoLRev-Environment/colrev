#! /usr/bin/env python
"""Package check."""
from __future__ import annotations

import subprocess
import sys
import typing
from importlib import import_module
from importlib import util
from pathlib import Path

import toml

import colrev.package_manager.package_base_classes as base_classes
from colrev.constants import Colors
from colrev.package_manager.package import Package
from colrev.package_manager.package_base_classes import BASECLASS_MAP

HELP_MESSAGES: dict[str, str] = {
    "check_project": (
        "The [project] table is missing in your pyproject.toml.\n"
        "Add at least a minimal project section, for example:\n\n"
        "[project]\n"
        'name = "my-colrev-package"\n'
        'version = "0.1.0"\n'
        'description = "Short description of the package"\n'
        'requires-python = ">=3.10"\n'
    ),
    "check_project_name": (
        "The project name is missing.\n"
        "Add a name in the [project] section of pyproject.toml, e.g.:\n\n"
        "[project]\n"
        'name = "my-colrev-package"\n'
    ),
    "check_project_description": (
        "The project description is missing.\n"
        "Add a description in the [project] section, e.g.:\n\n"
        "[project]\n"
        'description = "Short description of what this CoLRev package does."\n'
    ),
    "check_project_version": (
        "The project version is missing.\n"
        "Add a version in the [project] section, e.g.:\n\n"
        "[project]\n"
        'version = "0.1.0"\n'
    ),
    "check_project_license": (
        "The project license is missing.\n"
        "Add a license in the [project] section of pyproject.toml, for example:\n\n"
        "[project]\n"
        'license = { text = "MIT" }\n'
        "# or (when you have a LICENSE file):\n"
        'license = { file = "LICENSE" }\n'
    ),
    "check_project_authors": (
        "The project authors are missing.\n"
        "Add an authors list in the [project] section, e.g.:\n\n"
        "[project]\n"
        "authors = [\n"
        '  { name = "Your Name", email = "you@example.com" },\n'
        "]\n"
    ),
    "check_project_plugins_colrev": (
        "No CoLRev entry-points were found.\n"
        'Define them under [project.entry-points."colrev"], for example:\n\n'
        '[project.entry-points."colrev"]\n'
        '# interface_identifier = "your_package.module:YourEndpointClass"\n'
        '"colrev.operations.built_in" = "my_colrev_package.operations:MyOperation"\n'
    ),
    "check_project_plugins_colrev_keys": (
        "Some CoLRev entry-point keys are not valid BASECLASS_MAP keys.\n"
        'Ensure that all keys under [project.entry-points."colrev"] correspond\n'
        "to supported CoLRev interfaces. Example structure:\n\n"
        '[project.entry-points."colrev"]\n'
        '"colrev.built_in.search_source" = "my_colrev_package.search_source:MySource"\n"'
    ),
    "check_project_plugins_colrev_classes": (
        "At least one CoLRev plugin class could not be imported or does not implement\n"
        "the required CoLRev base class.\n"
        "Check that your entry-points point to existing classes and that these classes\n"
        "subclass the correct CoLRev base class from colrev.package_manager.package_base_classes.\n"
    ),
    "check_package_installed": (
        "The package does not appear to be installed in editable mode.\n"
        "From the project root, run:\n\n"
        "  pip install -e .\n"
    ),
    "check_colrev_discovers_package": (
        "CoLRev could not discover this package by its project.name.\n"
        "Make sure the package is installed in the active environment and that\n"
        "the CoLRev package metadata is correctly configured.\n"
        "Typical workflow from the project root:\n\n"
        "  pip install -e .\n"
        "  colrev env --help  # to verify that CoLRev is installed and working\n"
    ),
    "check_build_system": (
        "The [build-system] table is missing.\n"
        "Add a standard build system configuration to pyproject.toml, for example:\n\n"
        "[build-system]\n"
        'requires = ["setuptools>=61", "wheel"]\n'
        'build-backend = "setuptools.build_meta"\n'
    ),
}


def _check_package_installed(data: dict) -> bool:
    package_name = data["project"]["name"]
    try:
        subprocess.check_output(["pip", "show", package_name])
    except subprocess.CalledProcessError:
        print(
            f"Navigate to {Path.cwd()} and run: "
            f"{Colors.GREEN}pip install -e .{Colors.END}"
        )
        return False

    return True


def _check_key_exists(data: typing.Dict[str, typing.Any], key: str) -> bool:
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
            cls = getattr(module, class_name)  # type: ignore[attr-defined]
            baseclass: str = BASECLASS_MAP.get(interface_identifier)  # type: ignore[assignment]

            baseclass_class = getattr(base_classes, baseclass)
            if not issubclass(cls, baseclass_class):
                raise TypeError(
                    f"{cls} must implement all abstract methods of {baseclass_class}!"
                )
        except (ImportError, AttributeError, FileNotFoundError, TypeError) as exc:
            print(exc)
            return False
    return True


def _check_build_system(data: dict) -> bool:
    return _check_key_exists(data, "build-system")


def _check_colrev_discovers_package(data: dict) -> bool:
    """Check whether CoLRev can discover this package as a CoLRev package."""

    package_name = data.get("project", {}).get("name")
    if not package_name:
        print("No project.name found – cannot check CoLRev package discovery.")
        return False

    try:
        Package(package_name)
    except Exception as exc:  # noqa: BLE001
        print(
            f"{Colors.RED}CoLRev could not discover the package '{package_name}': "
            f"{exc}{Colors.END}"
        )
        return False

    return True


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
        "preconditions": ["check_project_plugins_colrev"],
    },
    "check_project_plugins_colrev_classes": {
        "method": _check_project_plugins_colrev_classes,
        "preconditions": ["check_project_plugins_colrev"],
    },
    "check_package_installed": {
        "method": _check_package_installed,
        "preconditions": ["check_project", "check_project_name"],
    },
    "check_colrev_discovers_package": {
        "method": _check_colrev_discovers_package,
        "preconditions": ["check_package_installed", "check_project_plugins_colrev"],
    },
    "check_build_system": {"method": _check_build_system, "preconditions": []},
}


def _validate_structure(data: dict, checks_dict: dict) -> list[str]:
    failed_checks: list[str] = []
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
            help_msg = HELP_MESSAGES.get(check_name)
            if help_msg:
                print(f"{Colors.GREEN}How to fix {check_name}:{Colors.END}")
                print(help_msg)
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
            sys.exit(1)
        else:
            print()
            print(f"{Colors.GREEN}✅ The package is a valid CoLRev plugin!{Colors.END}")
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error reading pyproject.toml: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
