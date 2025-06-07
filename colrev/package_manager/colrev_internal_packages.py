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
from urllib.parse import unquote
from urllib.parse import urlparse

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

    parsed_url = urlparse(data["url"])
    local_path = Path(unquote(parsed_url.path)).resolve(strict=False)

    return str(local_path)


def _clone_colrev_repository() -> Path:
    temp_dir = tempfile.mkdtemp()
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "https://github.com/CoLRev-Environment/colrev",
            temp_dir,
        ],
        check=True,
    )
    return Path(temp_dir)


def _get_colrev_path() -> Path:

    def is_colrev_root(path: Path) -> bool:
        return (path / "packages").is_dir()

    # Try editable install
    try:
        dist = distribution("colrev")
        dist_info_folder = (
            f"{dist.metadata['Name'].replace('-', '_')}-{dist.version}.dist-info"
        )
        dist_info_path = (
            Path(str(dist.locate_file(""))) / dist_info_folder / "direct_url.json"
        )

        if dist_info_path.exists():
            with open(dist_info_path, encoding="utf-8") as file:
                url = json.load(file).get("url", "")
                if url.startswith("file://"):
                    parsed = urlparse(url)
                    editable_path = Path(unquote(parsed.path)).resolve(strict=False)
                    if is_colrev_root(editable_path):
                        return editable_path
                    if (editable_path / "colrev").is_dir():
                        return editable_path / "colrev"
    except PackageNotFoundError:
        print("CoLRev not installed")

    # Fallback to clone
    clone_path = _clone_colrev_repository().resolve(strict=False)
    for candidate in [clone_path, *clone_path.glob("**/")]:
        if is_colrev_root(candidate):
            print(f"[DEBUG] Using candidate CoLRev root: {candidate}")
            return candidate

    raise FileNotFoundError(
        f"Cannot find CoLRev root folder with 'packages/' under: {clone_path}"
    )


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
