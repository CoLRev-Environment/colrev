#! /usr/bin/env python
"""Prescreen based on specified scope"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record

if typing.TYPE_CHECKING:
    import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class ScopePrescreen(JsonSchemaMixin):

    """Rule-based prescreen (scope)"""

    @dataclass
    class ScopePrescreenSettings(
        colrev.env.package_manager.DefaultSettings, JsonSchemaMixin
    ):
        """Settings for ScopePrescreen"""

        # pylint: disable=invalid-name
        # pylint: disable=too-many-instance-attributes

        endpoint: str
        TimeScopeFrom: typing.Optional[int]
        TimeScopeTo: typing.Optional[int]
        LanguageScope: typing.Optional[list]
        ExcludeComplementaryMaterials: typing.Optional[bool]
        OutletInclusionScope: typing.Optional[dict]
        OutletExclusionScope: typing.Optional[dict]
        ENTRYTYPEScope: typing.Optional[list]

        _details = {
            "TimeScopeFrom": {
                "tooltip": "Lower bound for the time scope",
                "min": 1900,
                "max": 2050,
            },
            "TimeScopeTo": {
                "tooltip": "Upper bound for the time scope",
                "min": 1900,
                "max": 2050,
            },
            "LanguageScope": {"tooltip": "Language scope"},
            "ExcludeComplementaryMaterials": {
                "tooltip": "Whether complementary materials (coverpages etc.) are excluded"
            },
            "OutletInclusionScope": {
                "tooltip": "Particular outlets that should be included (exclusively)"
            },
            "OutletExclusionScope": {
                "tooltip": "Particular outlets that should be excluded"
            },
            "ENTRYTYPEScope": {
                "tooltip": "Particular ENTRYTYPEs that should be included (exclusively)"
            },
        }

    settings_class = ScopePrescreenSettings

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:

        if "TimeScopeFrom" in settings:
            assert settings["TimeScopeFrom"] > 1900
        if "TimeScopeFrom" in settings:
            assert settings["TimeScopeFrom"] < 2100
        if "TimeScopeTo" in settings:
            assert settings["TimeScopeTo"] > 1900
        if "TimeScopeTo" in settings:
            assert settings["TimeScopeTo"] < 2100
        # gh_issue https://github.com/geritwagner/colrev/issues/64
        # validate values (assert, e.g., LanguageScope)

        self.settings = self.settings_class.load_settings(data=settings)

        self.predatory_journals_beal = self.__load_predatory_journals_beal()

        self.title_complementary_materials_keywords = (
            colrev.env.utils.load_complementary_material_keywords()
        )

    def __load_predatory_journals_beal(self) -> dict:

        predatory_journals = {}

        filedata = colrev.env.utils.get_package_file_content(
            file_path=Path("template/ops/predatory_journals_beall.csv")
        )

        if filedata:
            for pred_journal in filedata.decode("utf-8").splitlines():
                predatory_journals[pred_journal.lower()] = pred_journal.lower()

        return predatory_journals

    def __conditional_prescreen(
        self, *, prescreen_operation: colrev.ops.prescreen.Prescreen, record_dict: dict
    ) -> None:
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-nested-blocks

        if record_dict["colrev_status"] != colrev.record.RecordState.md_processed:
            return

        pad = 50

        # Note : LanguageScope is covered in prep
        # because dedupe cannot handle merges between languages

        if self.settings.ENTRYTYPEScope:
            if record_dict["ENTRYTYPE"] not in self.settings.ENTRYTYPEScope:
                colrev.record.Record(data=record_dict).prescreen_exclude(
                    reason="not in ENTRYTYPEScope"
                )

        if self.settings.OutletExclusionScope:
            if "values" in self.settings.OutletExclusionScope:
                for resource in self.settings.OutletExclusionScope["values"]:
                    for key, value in resource.items():
                        if key in record_dict and record_dict.get(key, "") == value:
                            colrev.record.Record(data=record_dict).prescreen_exclude(
                                reason="in OutletExclusionScope"
                            )
            if "list" in self.settings.OutletExclusionScope:
                for resource in self.settings.OutletExclusionScope["list"]:
                    for key, value in resource.items():
                        if "resource" == key and "predatory_journals_beal" == value:
                            if "journal" in record_dict:
                                if (
                                    record_dict["journal"].lower()
                                    in self.predatory_journals_beal
                                ):
                                    colrev.record.Record(
                                        data=record_dict
                                    ).prescreen_exclude(
                                        reason="predatory_journals_beal"
                                    )

        if self.settings.TimeScopeFrom:
            if int(record_dict.get("year", 0)) < self.settings.TimeScopeFrom:
                colrev.record.Record(data=record_dict).prescreen_exclude(
                    reason="not in TimeScopeFrom " f"(>{self.settings.TimeScopeFrom})"
                )

        if self.settings.TimeScopeTo:
            if int(record_dict.get("year", 5000)) > self.settings.TimeScopeTo:
                colrev.record.Record(data=record_dict).prescreen_exclude(
                    reason="not in TimeScopeTo " f"(<{self.settings.TimeScopeTo})"
                )

        if self.settings.OutletInclusionScope:
            in_outlet_scope = False
            if "values" in self.settings.OutletInclusionScope:
                for outlet in self.settings.OutletInclusionScope["values"]:
                    for key, value in outlet.items():
                        if key in record_dict and record_dict.get(key, "") == value:
                            in_outlet_scope = True
            if not in_outlet_scope:
                colrev.record.Record(data=record_dict).prescreen_exclude(
                    reason="not in OutletInclusionScope"
                )

        if self.settings.ExcludeComplementaryMaterials:
            if self.settings.ExcludeComplementaryMaterials:
                if "title" in record_dict:
                    if (
                        record_dict["title"].lower()
                        in self.title_complementary_materials_keywords
                    ):
                        colrev.record.Record(data=record_dict).prescreen_exclude(
                            reason="complementary material"
                        )

        if (
            record_dict["colrev_status"]
            == colrev.record.RecordState.rev_prescreen_excluded
        ):
            prescreen_operation.review_manager.report_logger.info(
                f' {record_dict["ID"]}'.ljust(pad, " ")
                + "Prescreen excluded (automatically)"
            )

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen records based on the scope parameters"""

        for record_dict in records.values():
            self.__conditional_prescreen(
                prescreen_operation=prescreen_operation, record_dict=record_dict
            )

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()
        prescreen_operation.review_manager.create_commit(
            msg="Pre-screen (scope)",
            manual_author=False,
        )
        return records


if __name__ == "__main__":
    pass
