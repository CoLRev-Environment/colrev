#!/usr/bin/env python3


class CustomPrepare:
    @classmethod
    def prepare(cls, PREP_RECORD):

        PREP_RECORD.data["mod"] = "this is a change..."

        return PREP_RECORD


if __name__ == "__main__":
    pass
