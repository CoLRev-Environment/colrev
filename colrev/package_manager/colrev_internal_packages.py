#! /usr/bin/env python
"""Discovering and using packages."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from importlib.metadata import distribution
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import toml


# pylint: disable=too-many-return-statements
def _get_local_editable_colrev_path() -> str:
    try:
        dist = distribution("colrev")
    except PackageNotFoundError:
        print("CoLRev not installed")
        return ""

    # Construct the .dist-info directory name
    dist_info_folder = (
        f"{dist.metadata['Name'].replace('-', '_')}-{dist.version}.dist-info"
    )

    if not dist.locate_file(""):
        raise ValueError("Distribution location not found")

    dist_info_folder = os.path.join(str(dist.locate_file("")), dist_info_folder)

    direct_url_path = os.path.join(dist_info_folder, "direct_url.json")
    if not os.path.exists(direct_url_path):
        return ""

    with open(direct_url_path, encoding="utf-8") as file:
        data = json.load(file)

    if "url" not in data or not data["url"].startswith("file://"):
        return ""

    return data["url"].replace("file://", "")


def _clone_colrev_repository() -> Path:
    temp_dir = tempfile.mkdtemp()
    print(f"Clone to {temp_dir}")
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/CoLRev-Environment/colrev",
            temp_dir,
        ],
        check=False,
    )
    return Path(temp_dir)


def _get_colrev_path() -> Path:

    local_editable_colrev_path = _get_local_editable_colrev_path()
    if local_editable_colrev_path:
        colrev_path = Path(local_editable_colrev_path)
        if local_editable_colrev_path.startswith("/D:"):
            # Remove the leading slash to correct the path format
            corrected_path_str = local_editable_colrev_path.lstrip("/")
            colrev_path = Path(corrected_path_str).resolve(strict=False)
        else:
            colrev_path = colrev_path.resolve(strict=False)
    else:
        colrev_path = _clone_colrev_repository().resolve(strict=False)

    # Check if there is a nested colrev directory
    potential_nested_path = colrev_path / "colrev"
    if potential_nested_path.is_dir():
        colrev_path = potential_nested_path

    return colrev_path


def get_internal_packages_dict() -> dict:
    """Get a dictionary of internal CoLRev packages"""

    colrev_path = _get_colrev_path()
    packages_dir = colrev_path / Path("packages")

    internal_packages_dict = {}
    for package_dir in packages_dir.iterdir():
        if package_dir.is_dir():
            package_path = str(package_dir)

            pyproject_path = os.path.join(package_path, "pyproject.toml")
            if not os.path.exists(pyproject_path):
                continue
            with open(pyproject_path, encoding="utf-8") as file:
                pyproject_data = toml.load(file)
            package_name = pyproject_data["project"]["name"]

            internal_packages_dict[package_name] = package_path

    return internal_packages_dict
