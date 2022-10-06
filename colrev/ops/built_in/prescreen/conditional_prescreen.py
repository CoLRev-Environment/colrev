#! /usr/bin/env python
"""Conditional prescreen"""
from __future__ import annotations

import typing
from dataclasses import dataclass

import zope.interface
from dacite import from_dict
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
class ConditionalPrescreen(JsonSchemaMixin):

    """Prescreen based on a condition (currently: include all)"""

    settings_class = colrev.env.package_manager.DefaultSettings

    def __init__(
        self,
        *,
        prescreen_operation: colrev.ops.prescreen.Prescreen,  # pylint: disable=unused-argument
        settings: dict,
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    def run_prescreen(
        self,
        prescreen_operation: colrev.ops.prescreen.Prescreen,
        records: dict,
        split: list,  # pylint: disable=unused-argument
    ) -> dict:
        """Prescreen records based on predefined conditions (rules)"""

        # TODO : conditions as a settings/parameter
        saved_args = locals()
        saved_args["include_all"] = ""
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
            script_call="colrev prescreen",
            saved_args=saved_args,
        )
        return records


if __name__ == "__main__":
    pass
