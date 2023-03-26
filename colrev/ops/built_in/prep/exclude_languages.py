#! /usr/bin/env python
"""Exclude records based on language as a prep operation"""
from __future__ import annotations

from dataclasses import dataclass

import timeout_decorator
import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.language_service
import colrev.env.package_manager
import colrev.ops.search_sources
import colrev.record

if False:  # pylint: disable=using-constant-test
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        import colrev.ops.prep

# pylint: disable=too-few-public-methods


@zope.interface.implementer(colrev.env.package_manager.PrepPackageEndpointInterface)
@dataclass
class ExcludeLanguagesPrep(JsonSchemaMixin):
    """Prepares records by excluding ones that are not in the languages_to_include"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, prep_operation: colrev.ops.prep.Prep, settings: dict) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

        # Note : the following objects have heavy memory footprints and should be
        # class (not object) properties to keep parallel processing as
        # efficient as possible (the object is passed to each thread)
        languages_to_include = ["eng"]
        # if not prep_operation.review_manager.in_ci_environment():
        self.language_service = colrev.env.language_service.LanguageService()

        prescreen_package_endpoints = (
            prep_operation.review_manager.settings.prescreen.prescreen_package_endpoints
        )
        if "scope_prescreen" in [s["endpoint"] for s in prescreen_package_endpoints]:
            for scope_prescreen in [
                s
                for s in prescreen_package_endpoints
                if "scope_prescreen" == s["endpoint"]
            ]:
                languages_to_include.extend(
                    scope_prescreen.get("LanguageScope", ["eng"])
                )
        self.language_service.validate_iso_639_3_language_codes(
            lang_code_list=languages_to_include
        )
        self.languages_to_include = list(set(languages_to_include))

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the record by excluding records whose metadata is not in English"""

        # pylint: disable=too-many-statements
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-return-statements

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
                self.language_service.compute_language_confidence_values(
                    text=record.data["title"].split("[")[0]
                )
            )
            confidence_values_part2 = (
                self.language_service.compute_language_confidence_values(
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

            if conf_1 < 0.8 and conf_2 < 0.8:
                record.update_field(
                    key="title",
                    value=record.data.get("title", ""),
                    source="",
                    note="quality_defect,language-not-found",
                    append_edit=True,
                )
                record.remove_field(key="language")
                record.set_status(
                    target_state=colrev.record.RecordState.md_needs_manual_preparation
                )
                return record

            if "eng" == lang_1:
                record.update_field(
                    key=f"title_{lang_2}",
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
                    key=f"title_{lang_1}",
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

        confidence_values = self.language_service.compute_language_confidence_values(
            text=record.data["title"]
        )

        if len(confidence_values) == 0:
            record.update_field(
                key="title",
                value=record.data.get("title", ""),
                source="LanguageDetector",
                note="cannot_predict_language",
            )
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
            return record

        predicted_language, conf = confidence_values.pop()

        if conf > 0.8:
            record.update_field(
                key="language",
                value=predicted_language,
                source="LanguageDetector",
                note="",
                append_edit=False,
            )

        else:
            record.update_field(
                key="title",
                value=record.data.get("title", ""),
                source="",
                note="quality_defect,language-not-found",
                append_edit=True,
            )
            record.remove_field(key="language")
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )

        if record.data.get("language", "") not in self.languages_to_include:
            record.prescreen_exclude(
                reason=f"language of title not in [{','.join(self.languages_to_include)}]"
            )

        return record


if __name__ == "__main__":
    pass
