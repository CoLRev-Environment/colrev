#! /usr/bin/env python
from pathlib import Path

import zope.interface
from dacite import from_dict

import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.process
import colrev.record


# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.process.SearchSourceEndpoint)
class TransportResearchInternationalDocumentation:
    settings_class = colrev.process.DefaultSourceSettings
    source_identifier = "{{biburl}}"

    def __init__(self, *, source_operation, settings: dict) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        result = {"confidence": 0, "source_identifier": cls.source_identifier}
        # Simple heuristic:
        if "UR  - https://trid.trb.org/view/" in data:
            result["confidence"] = 0.9
            return result
        return result

    def load_fixes(self, load_operation, source, records):

        return records

    def prepare(self, record: colrev.record.Record) -> colrev.record.Record:
        # TODO (if any)
        return record


if __name__ == "__main__":
    pass
