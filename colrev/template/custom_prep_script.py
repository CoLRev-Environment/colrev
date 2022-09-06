#!/usr/bin/env python3
from __future__ import annotations

from typing import TYPE_CHECKING

import timeout_decorator
import zope.interface
from dacite import from_dict

import colrev.process

if TYPE_CHECKING:
    import colrev.ops.prep


@zope.interface.implementer(colrev.process.PrepEndpoint)
class CustomPrep:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, prep_operation: colrev.ops.prep.Prep, settings: dict) -> None:
        self.settings = from_dict(
            data_class=colrev.process.DefaultSettings, data=settings
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(
        self, prep_operation: colrev.ops.prep.Prep, record: colrev.record.Record
    ) -> colrev.record.Record:

        if "journal" in record.data:
            if "MISQ" == record.data["journal"]:
                record.update_field(
                    key="journal", value="MIS Quarterly", source="custom_prep"
                )

        return record


if __name__ == "__main__":
    pass
