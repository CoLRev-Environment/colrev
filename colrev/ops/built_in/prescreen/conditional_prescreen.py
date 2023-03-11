#! /usr/bin/env python
"""Conditional prescreen"""
from __future__ import annotations

import typing
from dataclasses import dataclass

import zope.interface
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.record

if False:  # pylint: disable=using-constant-test
    if typing.TYPE_CHECKING:
        import colrev.ops.prescreen.Prescreen

# pylint: disable=too-few-public-methods
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.PrescreenPackageEndpointInterface
)
@dataclass
class ConditionalPrescreen(JsonSchemaMixin):

    """Conditional prescreen (currently: include all)"""

    settings_class = colrev.env.package_manager.DefaultSettings
    ci_supported: bool = True

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = self.settings_class.load_settings(data=settings)

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen records based on predefined conditions (rules)"""

        pad = 50
        for record in records.values():
            if record["colrev_status"] != colrev.record.RecordState.md_processed:
                continue
            prescreen_operation.review_manager.report_logger.info(
                f' {record["ID"]}'.ljust(pad, " ")
                + "Included in prescreen (automatically)"
            )
            record.update(
                colrev_status=colrev.record.RecordState.rev_prescreen_included
            )

        prescreen_operation.review_manager.dataset.save_records_dict(records=records)
        prescreen_operation.review_manager.dataset.add_record_changes()
        prescreen_operation.review_manager.create_commit(
            msg="Pre-screen (include_all)",
            manual_author=False,
        )
        return records


if __name__ == "__main__":
    pass
