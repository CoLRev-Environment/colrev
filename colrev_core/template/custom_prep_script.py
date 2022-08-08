#!/usr/bin/env python3
import timeout_decorator
import zope.interface
from dacite import from_dict

import colrev_core.process


@zope.interface.implementer(colrev_core.process.PreparationEndpoint)
class CustomPrepare:

    source_correction_hint = "check with the developer"
    always_apply_changes = True

    def __init__(self, *, PREPARATION, SETTINGS):
        self.SETTINGS = from_dict(
            data_class=colrev_core.process.DefaultSettings, data=SETTINGS
        )

    @timeout_decorator.timeout(60, use_signals=False)
    def prepare(self, PREPARATION, RECORD):

        if "journal" in RECORD.data:
            RECORD.data["journal"] = RECORD.data["journal"].replace(
                "MISQ", "MIS Quarterly"
            )

        return RECORD


if __name__ == "__main__":
    pass
