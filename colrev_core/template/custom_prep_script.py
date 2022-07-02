#!/usr/bin/env python3
import zope.interface

from colrev_core.process import PreparationEndpoint


@zope.interface.implementer(PreparationEndpoint)
class CustomPrepare:
    @classmethod
    def prepare(cls, PREPARATION, RECORD):

        if "journal" in RECORD.data:
            RECORD.data["journal"] = RECORD.data["journal"].replace(
                "MISQ", "MIS Quarterly"
            )

        return RECORD


if __name__ == "__main__":
    pass
