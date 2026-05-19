#!/usr/bin/env python
"""Security tests for package-manager subprocess arguments."""

from __future__ import annotations

from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest
from packaging.requirements import InvalidRequirement

from colrev.package_manager import check
from colrev.package_manager.package_manager import PackageManager
from colrev.package_manager.package_manager import _validate_external_package_selection
from colrev.package_manager.package_manager import _validate_internal_package_selection


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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    internal_dir = tmp_path / "colrev-allowed"
    internal_dir.mkdir()
    (internal_dir / "pyproject.toml").write_text("[project]\nname='colrev-allowed'\n")

    run_mock = MagicMock()
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.subprocess.run", run_mock
    )
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.get_internal_packages_dict",
        MagicMock(return_value={"colrev.allowed": str(internal_dir)}),
    )

    PackageManager().install(packages=["colrev.allowed"], upgrade=False)

    run_mock.assert_called_once_with(
        [sys.executable, "-m", "pip", "install", str(internal_dir.resolve())],
        check=True,
    )


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


@pytest.mark.parametrize("package_spec", ["requests", "requests>=2.0"])
def test_validate_external_package_accepts(package_spec: str) -> None:
    assert (
        _validate_external_package_selection(selected_package=package_spec)
        == package_spec
    )


@pytest.mark.parametrize(
    "package_spec", ["", "--index-url=https://example.com", "-r requirements.txt"]
)
def test_validate_external_package_rejects(package_spec: str) -> None:
    with pytest.raises((ValueError, InvalidRequirement)):
        _validate_external_package_selection(selected_package=package_spec)


def test_validate_internal_package_selection_accepts(tmp_path: Path) -> None:
    package_dir = tmp_path / "internal"
    package_dir.mkdir()
    (package_dir / "pyproject.toml").write_text("[project]\nname='internal'\n")

    selected = _validate_internal_package_selection(
        selected_package="colrev.allowed",
        internal_packages_dict={"colrev.allowed": str(package_dir)},
    )
    assert selected == str(package_dir.resolve())


def test_validate_internal_package_selection_rejects_missing_path(
    tmp_path: Path,
) -> None:
    missing_dir = tmp_path / "missing"
    with pytest.raises(ValueError):
        _validate_internal_package_selection(
            selected_package="colrev.allowed",
            internal_packages_dict={"colrev.allowed": str(missing_dir)},
        )


def test_validate_internal_package_selection_rejects_missing_pyproject(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / "internal"
    package_dir.mkdir()
    with pytest.raises(ValueError):
        _validate_internal_package_selection(
            selected_package="colrev.allowed",
            internal_packages_dict={"colrev.allowed": str(package_dir)},
        )


def test_install_uses_uv_executable_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.subprocess.run", run_mock
    )
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.shutil.which", lambda _: "/usr/bin/uv"
    )
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.get_internal_packages_dict",
        MagicMock(return_value={}),
    )

    PackageManager().install(packages=["requests"], upgrade=False, uv=True)

    run_mock.assert_called_once_with(
        ["/usr/bin/uv", "pip", "install", "requests"],
        check=True,
    )


def test_install_validates_external_packages_before_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_mock = MagicMock()
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.subprocess.run", run_mock
    )
    monkeypatch.setattr(
        "colrev.package_manager.package_manager.get_internal_packages_dict",
        MagicMock(return_value={}),
    )

    with pytest.raises(ValueError, match="must not start with '-'"):
        PackageManager().install(
            packages=["--index-url=https://example.com"],
            upgrade=False,
        )

    run_mock.assert_not_called()
