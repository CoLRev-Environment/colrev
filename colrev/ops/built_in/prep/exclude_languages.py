#! /usr/bin/env python
"""Exclude records based on language as a prep operation"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

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

    def __title_has_multiple_languages(self, *, title: str) -> bool:
        if "[" not in title:
            return False
        split_titles = [
            re.sub(r"\d", "", x.rstrip().rstrip("]")) for x in title.split("[")
        ]
        min_len = statistics.mean(len(x) for x in split_titles) - 20
        if all(len(x) > min_len for x in split_titles):
            return True
        return False

    def prepare(
        self,
        prep_operation: colrev.ops.prep.Prep,  # pylint: disable=unused-argument
        record: colrev.record.PrepRecord,
    ) -> colrev.record.Record:
        """Prepare the record by excluding records whose metadata is not in English"""

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

        if not self.__title_has_multiple_languages(title=record.data.get("title", "")):
            language = self.language_service.compute_language(text=record.data["title"])
            record.update_field(
                key="language",
                value=language,
                source="LanguageDetector",
                note="",
                append_edit=False,
            )
        else:
            # Deal with title fields containing titles in two or more languages
            split_titles = [
                x.rstrip().rstrip("]") for x in record.data["title"].split("[")
            ]
            for i, split_title in enumerate(split_titles):
                lang_split_title = self.language_service.compute_language(
                    text=split_title
                )
                if 0 == i:
                    record.update_field(
                        key="title",
                        value=split_title.rstrip(),
                        source="LanguageDetector_split",
                    )
                    record.update_field(
                        key="language",
                        value=lang_split_title,
                        source="LanguageDetector_split",
                    )
                else:
                    record.update_field(
                        key=f"title_{lang_split_title}",
                        value=split_title.rstrip("]"),
                        source="LanguageDetector_split",
                    )

        if record.data.get("language", "") == "":
            record.update_field(
                key="title",
                value=record.data.get("title", ""),
                source="LanguageDetector",
                note="language-not-found",
            )
            record.set_status(
                target_state=colrev.record.RecordState.md_needs_manual_preparation
            )
            return record

        if record.data.get("language", "") not in self.languages_to_include:
            record.prescreen_exclude(
                reason=f"language of title not in [{','.join(self.languages_to_include)}]"
            )

        return record


if __name__ == "__main__":
    pass
