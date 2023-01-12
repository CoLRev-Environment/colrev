#! /usr/bin/env python
"""Exclude records based on language as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pycountry
import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin
from lingua.builder import LanguageDetectorBuilder

import colrev.env.package_manager
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

        self.settings = self.settings_class.load_settings(data=settings)

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
        # gh_issue https://github.com/geritwagner/colrev/issues/64
        # set as settings parameter?
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
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the record by excluding records whose metadata is not in English"""

        # pylint: disable=too-many-locals
        # pylint: disable=too-many-return-statements
        # pylint: disable=too-many-branches

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

        # Deal with title fields containing titles in two languages
        if (
            len(record.data.get("title", "")) > 40
            and record.data.get("title", "").count("[") == 1
        ):

            confidence_values_part1 = (
                self.language_detector.compute_language_confidence_values(
                    text=record.data["title"].split("[")[0]
                )
            )
            confidence_values_part2 = (
                self.language_detector.compute_language_confidence_values(
                    text=record.data["title"].split("[")[1]
                )
            )

            if len(confidence_values_part1) == 0 or len(confidence_values_part2) == 0:
                record.set_status(
                    target_state=colrev.record.RecordState.md_needs_manual_preparation
                )
                return record

            lang_1, conf_1 = confidence_values_part1[0]
            lang_2, conf_2 = confidence_values_part2[0]

            predicted_language_1 = lang_1
            if lang_1.name.lower() in self.lang_code_mapping:
                predicted_language_1 = self.lang_code_mapping[lang_1.name.lower()]

            predicted_language_2 = lang_2
            if lang_2.name.lower() in self.lang_code_mapping:
                predicted_language_2 = self.lang_code_mapping[lang_2.name.lower()]

            if conf_1 < 0.9 and conf_2 < 0.9:
                record.update_field(
                    key="title",
                    value=record.data.get("title", ""),
                    source="",
                    note="quality_defect,language-not-found",
                )
                record.set_status(
                    target_state=colrev.record.RecordState.md_needs_manual_preparation
                )
                return record

            if "eng" == predicted_language_1:
                record.update_field(
                    key=f"title_{predicted_language_2}",
                    value=record.data["title"].split("[")[1].rstrip("]"),
                    source="LanguageDetector_split",
                )
                record.update_field(
                    key="title",
                    value=record.data["title"].split("[")[0].rstrip(),
                    source="LanguageDetector_split",
                )
                record.update_field(
                    key="language",
                    value="eng",
                    source="LanguageDetector",
                    note="",
                )
            else:
                record.update_field(
                    key=f"title_{predicted_language_1}",
                    value=record.data["title"].split("[")[0].rstrip(),
                    source="LanguageDetector_split",
                )
                record.update_field(
                    key="title",
                    value=record.data["title"].split("[")[1].rstrip(),
                    source="LanguageDetector_split",
                )
                record.update_field(
                    key="language",
                    value="eng",
                    source="LanguageDetector",
                    note="",
                )
                record.prescreen_exclude(
                    reason=f"language of title(s) not in [{','.join(self.languages_to_include)}]"
                )

            return record

        confidence_values = self.language_detector.compute_language_confidence_values(
            text=record.data["title"]
        )
        # if prep_operation.review_manager.verbose_mode:
        #     print(record.data["title"].lower())
        #     prep_operation.review_manager.p_printer.pprint(confidence_values)
        # If language not in record, add language (always - needed in dedupe.)
        set_most_likely_language = False
        for lang, conf in confidence_values:

            predicted_language = "not-found"
            # Map to ISO 639-3 language code
            if lang.name.lower() in self.lang_code_mapping:
                predicted_language = self.lang_code_mapping[lang.name.lower()]

            if not set_most_likely_language:
                record.update_field(
                    key="language",
                    value=predicted_language,
                    source="LanguageDetector",
                    note="",
                )
                set_most_likely_language = True
            if "eng" == predicted_language:
                if conf > 0.9:
                    record.data["language"] = "eng"
                    return record

            if conf < 0.9:
                record.update_field(
                    key="title",
                    value=record.data.get("title", ""),
                    source="",
                    note="quality_defect,language-not-found",
                )
                record.set_status(
                    target_state=colrev.record.RecordState.md_needs_manual_preparation
                )
                return record

        if len(confidence_values) == 0:
            record.update_field(
                key="title",
                value=record.data.get("title", ""),
                source="LanguageDetector",
                note="cannt_predict_language",
            )
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
            return record

        record.prescreen_exclude(
            reason=f"language of title not in [{','.join(self.languages_to_include)}]"
        )

        return record


if __name__ == "__main__":
    pass
