#!/usr/bin/env python
"""Tests for record formatting and standardization."""

import unittest

from colrev.record.record import Fields
from colrev.record.record import Record
from colrev.record.record import RecordState
from colrev.record.record_formatter import RecordFormatter


class RecordFormatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record_formatter = RecordFormatter()

    def test_pre_md_retrieved(self) -> None:
        record = Record(
            {
                Fields.STATUS: RecordState.md_retrieved,
                "author": "van der Aalst, Wil and Brocke, Jan vom and van Wee and Dis van",
                "title": "My Title \\textendash With special chars &amp; symbols",
                "ID": "123",
                "year": "2020.0",
                "pages": "n.pag",
                "volume": "ahead-of-print",
                "number": "ahead-of-print",
                "url": "https://login?url=https://www.example.com",
            }
        )

        self.record_formatter.run(record=record)

        self.assertEqual(
            record.data["author"],
            "{van der Aalst}, Wil and {vom Brocke}, Jan and {van Wee} and {van Dis}",
        )
        self.assertEqual(
            record.data["title"], "My Title – With special chars & symbols"
        )
        self.assertEqual(record.data["ID"], "123")
        self.assertEqual(record.data["year"], "2020")
        self.assertEqual(record.data["url"], "https://www.example.com")
        assert "pages" not in record.data
        assert "volume" not in record.data
        assert "number" not in record.data

    def test_post_md_retrieved(self) -> None:
        record = Record(
            {
                Fields.DOI: "http://dx.doi.org/10.1234",
                Fields.LANGUAGE: "eng",
                Fields.STATUS: RecordState.md_processed,
                "issue": "1",
            }
        )

        self.record_formatter.run(record=record)

        self.assertEqual(record.data[Fields.DOI], "10.1234")
        self.assertEqual(record.data[Fields.LANGUAGE], "eng")
        self.assertEqual(record.data[Fields.NUMBER], "1")


if __name__ == "__main__":
    unittest.main()
