#! /usr/bin/env python3
"""Command-line interface for installing CoLRev."""
from __future__ import annotations

import sys
import typing
from importlib.metadata import distribution
from importlib.metadata import PackageNotFoundError
from runpy import run_module

import colrev.package_manager.colrev_internal_packages
import colrev.review_manager
from colrev.constants import Colors


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

    internal_packages_dict = (
        colrev.package_manager.colrev_internal_packages.get_internal_packages_dict()
    )

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
