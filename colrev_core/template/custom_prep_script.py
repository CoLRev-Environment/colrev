#!/usr/bin/env python3
import zope.interface

from colrev_core.prep import PrepScript


@zope.interface.implementer(PrepScript)
class CustomPrepare:
    @classmethod
    def prepare(cls, PREP_RECORD):

        if "journal" in PREP_RECORD.data:
            PREP_RECORD.data["journal"] = PREP_RECORD.data["journal"].replace(
                "MISQ", "MIS Quarterly"
            )

        return PREP_RECORD


if __name__ == "__main__":
    pass
