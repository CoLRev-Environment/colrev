#! /usr/bin/env python
"""Exclude records with non-latin alphabets as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from alphabet_detector import AlphabetDetector
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageInterface)
@dataclass
class ExcludeNonLatinAlphabetsPrep(JsonSchemaMixin):
    """Prepares records by excluding ones that have a non-latin alphabet
    (in the title, author, journal, or booktitle field)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True
    alphabet_detector = AlphabetDetector()

    def __init__(
        self,
        *,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        def mostly_latin_alphabet(str_to_check: str) -> bool:
            assert len(str_to_check) != 0
            nr_non_latin = 0
            for character in str_to_check:
                if not self.alphabet_detector.only_alphabet_chars(character, "LATIN"):
                    nr_non_latin += 1
            return nr_non_latin / len(str_to_check) > 0.75

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
