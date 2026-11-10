"""Tests for package discovery checks."""

# pylint: disable=protected-access

import pytest

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.check as package_check


def test_package_discovery_reports_missing_package(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A missing CoLRev package is reported as a failed discovery check."""

    def raise_missing_dependency(_package_name: str) -> None:
        raise colrev_exceptions.MissingDependencyError("not installed")

    monkeypatch.setattr(package_check, "Package", raise_missing_dependency)

    assert not package_check._check_colrev_discovers_package(
        {"project": {"name": "example.package"}}
    )
    assert "could not discover" in capsys.readouterr().out


def test_package_discovery_does_not_hide_unexpected_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected discovery errors are not reported as missing packages."""

    def raise_unexpected_error(_package_name: str) -> None:
        raise RuntimeError("unexpected package metadata error")

    monkeypatch.setattr(package_check, "Package", raise_unexpected_error)

    with pytest.raises(RuntimeError, match="unexpected package metadata error"):
        package_check._check_colrev_discovers_package(
            {"project": {"name": "example.package"}}
        )
