#! /usr/bin/env python
"""Exclude records with non-latin alphabets as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import zope.interface
from alphabet_detector import AlphabetDetector
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

# pylint: disable=duplicate-code
if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class ExcludeNonLatinAlphabetsPrep(JsonSchemaMixin):
    """Prepares records by excluding ones that have a non-latin alphabet
    (in the title, author, journal, or booktitle field)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    alphabet_detector = AlphabetDetector()

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the records by excluding records whose metadata is not in Latin alphabet"""

        if prep_operation.polish:
            return record

        def mostly_latin_alphabet(str_to_check: str) -> bool:
            assert len(str_to_check) != 0
            nr_non_latin = 0
            for character in str_to_check:
                if not self.alphabet_detector.only_alphabet_chars(character, "LATIN"):
                    nr_non_latin += 1
            return nr_non_latin / len(str_to_check) > 0.75

        # TB:D join or check independently?
        str_to_check = " ".join(
            [
                record.data.get("title", ""),
                record.data.get("author", ""),
                record.data.get("journal", ""),
                record.data.get("booktitle", ""),
            ]
        )
        if mostly_latin_alphabet(str_to_check):
            record.prescreen_exclude(reason="non_latin_alphabet")

        return record


if __name__ == "__main__":
    pass
