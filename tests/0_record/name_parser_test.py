"""Tests for parsing personal names in bibliographic records."""

from colrev.constants import Fields
from colrev.record.name_parser import parse_names
from colrev.record.name_parser import parse_names_in_records
from colrev.record.name_parser import split_tex_string


def test_split_tex_string_does_not_split_inside_braces() -> None:
    """Preserve whitespace inside a braced TeX name group."""
    assert split_tex_string("{John Doe} Smith", sep=" ") == [
        "{John Doe}",
        "Smith",
    ]


def test_parse_names_formats_first_last_and_particles() -> None:
    """Format first-last names, including lowercase name particles."""
    assert parse_names("John Doe and Alex van der Meer") == (
        "Doe, John and van der Meer, Alex"
    )


def test_parse_names_in_records_formats_author_and_editor() -> None:
    """Apply name parsing to author and editor fields in records."""
    records = {
        "record-1": {
            Fields.AUTHOR: "John Doe and Jane Smith",
            Fields.EDITOR: "Alex van der Meer",
            Fields.TITLE: "A title",
        }
    }

    parse_names_in_records(records)

    assert records["record-1"][Fields.AUTHOR] == "Doe, John and Smith, Jane"
    assert records["record-1"][Fields.EDITOR] == "van der Meer, Alex"
    assert records["record-1"][Fields.TITLE] == "A title"
