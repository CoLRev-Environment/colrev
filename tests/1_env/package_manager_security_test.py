#!/usr/bin/env python
"""Security tests for package-manager subprocess arguments."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from colrev.package_manager import check
from colrev.package_manager.package_manager import PackageManager


@pytest.mark.parametrize(
    "package_name",
    ["colrev", "my-package", "my_package", "my.package", "p1._-name"],
)
def test_validate_package_name_accepts_valid_names(package_name: str) -> None:
    assert check._validate_package_name(package_name) == package_name


@pytest.mark.parametrize("package_name", ["", "-help", "bad name", "name;rm -rf /"])
def test_validate_package_name_rejects_invalid_names(package_name: str) -> None:
    with pytest.raises(ValueError):
        check._validate_package_name(package_name)


def test_check_package_installed_validates_package_name_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    check_output_mock = MagicMock()
    monkeypatch.setattr(check.subprocess, "check_output", check_output_mock)

    result = check._check_package_installed({"project": {"name": "colrev"}})

    assert result is True
    check_output_mock.assert_called_once()


def test_install_accepts_internal_package_and_calls_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.subprocess.run", run_mock
    )
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.get_internal_packages_dict",
        MagicMock(return_value={"colrev.allowed": "colrev-allowed"}),
    )

    PackageManager().install(packages=["colrev.allowed"], upgrade=False)

    run_mock.assert_called_once_with(["pip", "install", "colrev-allowed"], check=True)


def test_install_rejects_unknown_internal_package_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.subprocess.run", run_mock
    )
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.get_internal_packages_dict",
        MagicMock(return_value={"colrev.allowed": "colrev-allowed"}),
    )

    with pytest.raises(ValueError):
        PackageManager().install(packages=["colrev.unknown"], upgrade=False)

    run_mock.assert_not_called()
