"""Tests for the CoLRev command-line interface."""

from pathlib import Path

from click.testing import CliRunner

import colrev.loader.load_utils
import colrev.ui_cli.cli
import colrev.writer.write_utils


def _patch_conversion(monkeypatch, converted_files: list[Path]) -> None:
    monkeypatch.setattr(
        colrev.loader.load_utils,
        "load",
        lambda input_file: {"record": {"ID": "record"}},
    )
    monkeypatch.setattr(
        colrev.writer.write_utils,
        "write_file",
        lambda *, records_dict, filename: converted_files.append(filename),
    )


def test_convert_accepts_file(tmp_path: Path, monkeypatch) -> None:
    """A regular file does not require recursive mode."""
    input_file = tmp_path / "references.ris"
    input_file.touch()
    converted_files: list[Path] = []
    _patch_conversion(monkeypatch, converted_files)

    result = CliRunner().invoke(
        colrev.ui_cli.cli.convert, [str(input_file), "--to", "bib"]
    )

    assert result.exit_code == 0
    assert converted_files == [input_file.with_suffix(".bib")]


def test_convert_rejects_directory_without_recursive(tmp_path: Path) -> None:
    """A directory requires explicit recursive mode."""
    result = CliRunner().invoke(
        colrev.ui_cli.cli.convert, [str(tmp_path), "--to", "bib"]
    )

    assert result.exit_code != 0
    assert "directory" in result.output
    assert "-r/--recursive" in result.output


def test_convert_recursively_processes_supported_files(
    tmp_path: Path, monkeypatch
) -> None:
    """Short recursive mode discovers eligible files below the directory."""
    nested_directory = tmp_path / "nested"
    nested_directory.mkdir()
    first_input = tmp_path / "first.ris"
    second_input = nested_directory / "second.csv"
    ignored_input = nested_directory / "notes.pdf"
    for input_file in (first_input, second_input, ignored_input):
        input_file.touch()
    converted_files: list[Path] = []
    _patch_conversion(monkeypatch, converted_files)

    result = CliRunner().invoke(
        colrev.ui_cli.cli.convert, ["-r", str(tmp_path), "--to", "bib"]
    )

    assert result.exit_code == 0
    assert set(converted_files) == {
        first_input.with_suffix(".bib"),
        second_input.with_suffix(".bib"),
    }


def test_convert_long_recursive_option(tmp_path: Path, monkeypatch) -> None:
    """The long recursive option is equivalent to its short form."""
    input_file = tmp_path / "references.ris"
    input_file.touch()
    converted_files: list[Path] = []
    _patch_conversion(monkeypatch, converted_files)

    result = CliRunner().invoke(
        colrev.ui_cli.cli.convert,
        ["--recursive", str(tmp_path), "--to", "bib"],
    )

    assert result.exit_code == 0
    assert converted_files == [input_file.with_suffix(".bib")]
