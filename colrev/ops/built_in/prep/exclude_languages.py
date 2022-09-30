#! /usr/bin/env python
"""Exclude records based on language as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pycountry
import timeout_decorator
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from lingua.builder import LanguageDetectorBuilder

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search_sources
import colrev.record

if TYPE_CHECKING:
    import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class ExcludeLanguagesPrep(JsonSchemaMixin):
    """Prepares records by excluding ones that are not in the languages_to_include"""

    settings_class = colrev.env.package_manager.DefaultSettings

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, prep_operation: colrev.ops.prep.Prep, settings: dict) -> None:

        self.settings = from_dict(data_class=self.settings_class, data=settings)

        # Note : Lingua is tested/evaluated relative to other libraries:
        # https://github.com/pemistahl/lingua-py
        # It performs particularly well for short strings (single words/word pairs)
        # The langdetect library is non-deterministic, especially for short strings
        # https://pypi.org/project/langdetect/

        # Note : the following objects have heavy memory footprints and should be
        # class (not object) properties to keep parallel processing as
        # efficient as possible (the object is passed to each thread)
        self.language_detector = (
            LanguageDetectorBuilder.from_all_languages_with_latin_script().build()
        )
        # Language formats: ISO 639-1 standard language codes
        # https://github.com/flyingcircusio/pycountry

        prescreen_package_endpoints = (
            prep_operation.review_manager.settings.prescreen.prescreen_package_endpoints
        )
        # TODO : set as settings parameter?
        languages_to_include = ["eng"]
        if "scope_prescreen" in [s["endpoint"] for s in prescreen_package_endpoints]:
            for scope_prescreen in [
                s
                for s in prescreen_package_endpoints
                if "scope_prescreen" == s["endpoint"]
            ]:
                languages_to_include.extend(
                    scope_prescreen.get("LanguageScope", ["eng"])
                )
        self.languages_to_include = list(set(languages_to_include))

        self.lang_code_mapping = {}
        for country in pycountry.languages:
            try:
                self.lang_code_mapping[country.name.lower()] = country.alpha_3
            except AttributeError:
                pass

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.PrepRecord
    ) -> colrev.record.Record:

        # Note : other languages are not yet supported
        # because the dedupe does not yet support cross-language merges

        if "language" in record.data:
            if record.data["language"] not in self.languages_to_include:
                record.prescreen_exclude(
                    reason=(
                        "language of title not in "
                        f"[{','.join(self.languages_to_include)}]"
                    )
                )
            return record

        # To avoid misclassifications for short titles
        if len(record.data.get("title", "")) < 30:
            # If language not in record, add language
            # (always - needed in dedupe.)
            record.data["language"] = "eng"
            return record

        confidence_values = self.language_detector.compute_language_confidence_values(
            text=record.data["title"]
        )

        if prep_operation.review_manager.debug_mode:
            print(record.data["title"].lower())
            prep_operation.review_manager.p_printer.pprint(confidence_values)

        # If language not in record, add language (always - needed in dedupe.)
        set_most_likely_language = False
        for lang, conf in confidence_values:

            predicted_language = "not-found"
            # Map to ISO 639-3 language code
            if lang.name.lower() in self.lang_code_mapping:
                predicted_language = self.lang_code_mapping[lang.name.lower()]

            if not set_most_likely_language:
                record.data["language"] = predicted_language
                set_most_likely_language = True
            if "eng" == predicted_language:
                if conf > 0.95:
                    record.data["language"] = "eng"
                    return record

        record.prescreen_exclude(
            reason=f"language of title not in [{','.join(self.languages_to_include)}]"
        )

        return record


if __name__ == "__main__":
    pass
