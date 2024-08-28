#! /usr/bin/env python3
"""Command-line interface for installing CoLRev."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import typing
from runpy import run_module

import pkg_resources
import toml


# pylint: disable=too-many-return-statements
def _get_local_editable_colrev_path() -> str:

    try:
        distribution = pkg_resources.get_distribution("colrev")
    except pkg_resources.DistributionNotFound:
        print("CoLRev not installed")
        return ""

    # Construct the .dist-info directory name
    dist_info_folder = f"{distribution.project_name.replace('-', '_')}"
    dist_info_folder += f"-{distribution.version}.dist-info"
    if not distribution.location:
        raise ValueError
    dist_info_folder = os.path.join(distribution.location, dist_info_folder)

    direct_url_path = os.path.join(dist_info_folder, "direct_url.json")
    if not os.path.exists(direct_url_path):
        return ""

    with open(direct_url_path, encoding="utf-8") as file:
        data = json.load(file)

    if "url" not in data:
        return ""

    editable_dir = data["url"].replace("file://", "")
    return editable_dir


def _clone_colrev_repository() -> str:
    temp_dir = tempfile.mkdtemp()
    subprocess.run(
        ["git", "clone", "https://github.com/CoLRev-Environment/colrev", temp_dir],
        check=False,
    )
    return temp_dir


def _get_colrev_path() -> str:
    local_editable_colrev_path = _get_local_editable_colrev_path()
    if local_editable_colrev_path:
        return local_editable_colrev_path

    return _clone_colrev_repository()


def _get_colrev_package_path(editable_dir: str, colrev_package: str) -> str:

    pyproject_path = os.path.join(editable_dir, "pyproject.toml")
    with open(pyproject_path, encoding="utf-8") as f:
        pyproject_data = toml.load(f)

    if colrev_package not in pyproject_data["tool"]["poetry"]["dependencies"]:
        print("Not in pyproject.toml")
        return ""
    path = pyproject_data["tool"]["poetry"]["dependencies"][colrev_package][
        "path"
    ].lstrip(".")
    colrev_package_path = editable_dir + path
    return colrev_package_path


# pylint: disable=too-many-branches
def main(
    packages: typing.List[str],
    upgrade: bool,
    editable: str,
    force_reinstall: bool,
    no_cache_dir: bool,
) -> None:
    """Main method for colrev install"""
    # Install packages from colrev monorepository first
    colrev_packages = []
    for package in packages:
        if (
            package.replace(".", "-").replace("_", "-")
            in pkg_resources.get_distribution("colrev").extras
        ):
            colrev_packages.append(package)
    packages = [p for p in packages if p not in colrev_packages]

    colrev_path = _get_colrev_path()
    if colrev_packages:
        for colrev_package in colrev_packages:
            colrev_package_path = _get_colrev_package_path(colrev_path, colrev_package)

            args = ["pip", "install"]
            args += [colrev_package_path]
            if upgrade:
                args += ["--upgrade"]
            if editable:
                args += ["--editable", editable]
            if force_reinstall:
                args += ["--force-reinstall"]
            if no_cache_dir:
                args += ["--no-cache-dir"]
            sys.argv = args
            run_module("pip", run_name="__main__")

    if packages:
        args = ["pip", "install"]
        if upgrade:
            args += ["--upgrade"]
        if editable:
            args += ["--editable", editable]
        if force_reinstall:
            args += ["--force-reinstall"]
        if no_cache_dir:
            args += ["--no-cache-dir"]
        args += list(packages)
        sys.argv = args
        run_module("pip", run_name="__main__")
