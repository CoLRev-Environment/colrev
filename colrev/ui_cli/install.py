#! /usr/bin/env python3
"""Command-line interface for installing CoLRev."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import typing
from importlib.metadata import distribution
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from runpy import run_module

import pkg_resources
import toml

import colrev.review_manager
from colrev.constants import Colors


# pylint: disable=too-many-return-statements
def _get_local_editable_colrev_path() -> str:

    try:
        dist = pkg_resources.get_distribution("colrev")
    except pkg_resources.DistributionNotFound:
        print("CoLRev not installed")
        return ""

    # Construct the .dist-info directory name
    dist_info_folder = f"{dist.project_name.replace('-', '_')}"
    dist_info_folder += f"-{dist.version}.dist-info"
    if not dist.location:
        raise ValueError
    dist_info_folder = os.path.join(dist.location, dist_info_folder)

    direct_url_path = os.path.join(dist_info_folder, "direct_url.json")
    if not os.path.exists(direct_url_path):
        return ""

    with open(direct_url_path, encoding="utf-8") as file:
        data = json.load(file)

    if "url" not in data:
        return ""

    editable_dir = data["url"].replace("file://", "")
    return editable_dir


def _clone_colrev_repository() -> Path:
    temp_dir = tempfile.mkdtemp()
    subprocess.run(
        ["git", "clone", "https://github.com/CoLRev-Environment/colrev", temp_dir],
        check=False,
    )
    return Path(temp_dir)


def _get_colrev_path() -> Path:

    local_editable_colrev_path = _get_local_editable_colrev_path()
    if local_editable_colrev_path:
        print(f"Local editable colrev path: {local_editable_colrev_path}")
        colrev_path = Path(local_editable_colrev_path)
        # Check if the path starts with a slash and contains a colon (e.g., /D:/)
        if local_editable_colrev_path.startswith("\\"):
            # Remove the leading slash to correct the path format
            corrected_path_str = str(local_editable_colrev_path).lstrip("\\")
            colrev_path = Path(corrected_path_str).resolve(strict=False)
        else:
            colrev_path = colrev_path.resolve(strict=False)
        print(f"Resolved local colrev path: {colrev_path}")
    else:
        colrev_path = _clone_colrev_repository().resolve(strict=False)
        print(f"Resolved cloned colrev path: {colrev_path}")

    # Check if there is a nested colrev directory
    potential_nested_path = colrev_path / "colrev"
    if potential_nested_path.is_dir():
        colrev_path = potential_nested_path
        print(f"Using nested colrev path: {colrev_path}")
    
    # list files in colrev_path
    for item in colrev_path.iterdir():
        print(f"Item: {item}")

    return colrev_path


def _is_package_installed(package_name: str) -> bool:
    try:
        p_dist = distribution(package_name.replace("-", "_"))
    except PackageNotFoundError:
        return False
    return p_dist is not None


def _install_project(
    force_reinstall: bool, review_manager: colrev.review_manager.ReviewManager
) -> typing.List[str]:

    review_manager.logger.info("Install project")
    packages = review_manager.settings.get_packages()
    review_manager.logger.info("Packages:")

    installed_packages = []
    for package in packages:
        if _is_package_installed(package):
            installed_packages.append(package)
            review_manager.logger.info(
                f" {Colors.GREEN}{package}: installed{Colors.END}"
            )
        else:
            review_manager.logger.info(
                f" {Colors.ORANGE}{package}: not installed{Colors.END}"
            )

    if not force_reinstall:
        packages = [p for p in packages if p not in installed_packages]

    return packages


def _get_internal_packages_dict() -> dict:
    colrev_path = _get_colrev_path()
    packages_dir = colrev_path / Path("packages")

    internal_packages_dict = {}
    for package_dir in packages_dir.iterdir():
        if package_dir.is_dir():
            package_path = str(package_dir)

            pyproject_path = os.path.join(package_path, "pyproject.toml")
            if not os.path.exists(pyproject_path):
                continue
            with open(pyproject_path, encoding="utf-8") as f:
                pyproject_data = toml.load(f)
            package_name = pyproject_data["tool"]["poetry"]["name"]

            internal_packages_dict[package_name] = package_path

    return internal_packages_dict


# pylint: disable=too-many-branches
def main(
    packages: typing.List[str],
    upgrade: bool,
    editable: str,
    force_reinstall: bool,
    no_cache_dir: bool,
) -> None:
    """Main method for colrev install"""

    if len(packages) == 1 and packages[0] == ".":
        review_manager = colrev.review_manager.ReviewManager()
        packages = _install_project(
            force_reinstall=force_reinstall, review_manager=review_manager
        )
        if len(packages) == 0:
            review_manager.logger.info("All packages are already installed")
            return

    internal_packages_dict = _get_internal_packages_dict()
    # Install packages from colrev monorepository first
    colrev_packages = []
    for package in packages:
        if package in internal_packages_dict:
            colrev_packages.append(package)
    packages = [p for p in packages if p not in colrev_packages]

    print(f"ColRev packages: {colrev_packages}")
    if colrev_packages:

        colrev_package_paths = [
            p_path
            for p_name, p_path in internal_packages_dict.items()
            if p_name in colrev_packages
        ]
        args = ["pip", "install"]
        args += colrev_package_paths
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

    print(f"Other packages: {packages}")
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
