#!/usr/bin/env python
"""Testing environment manager settings"""
from pathlib import Path

import pytest

import colrev.env.utils
import colrev.exceptions as colrev_exceptions


def test_get_template() -> None:

    with pytest.raises(colrev_exceptions.TemplateNotAvailableError):
        colrev.env.utils.get_template(template_path="unknown")


def test_retrieve_package_file() -> None:

    with pytest.raises(colrev_exceptions.TemplateNotAvailableError):
        colrev.env.utils.retrieve_package_file(
            template_file=Path("unknown"), target=Path("unknown")
        )


def test_inplace_change() -> None:
    # Create a temporary file
    with open("temp.txt", "w") as file:
        file.write("Some content.")

    colrev.env.utils.inplace_change(
        filename=Path("temp.txt"), old_string="Some", new_string="Another"
    )

    with open("temp.txt") as file:
        assert file.read() == "Another content."

    colrev.env.utils.inplace_change(
        filename=Path("temp.txt"), old_string="XY", new_string="Another"
    )

    with open("temp.txt") as file:
        assert file.read() == "Another content."


def test_remove_accents() -> None:

    assert colrev.env.utils.remove_accents("éàèùç") == "eaeuc"
    assert colrev.env.utils.remove_accents("Á") == "A"
    assert colrev.env.utils.remove_accents("Paré") == "Pare"
    assert colrev.env.utils.remove_accents("Müller") == "Muller"
