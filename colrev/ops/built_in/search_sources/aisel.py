#! /usr/bin/env python
"""SearchSource: AIS electronic Library"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.ops.built_in.database_connectors
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


def apply_field_mapping(
    *, record: colrev.record.PrepRecord, mapping: dict
) -> colrev.record.PrepRecord:
    """Convenience function for the prep scripts"""
    # TODO : could move the function to PrepRecord?

    mapping = {k.lower(): v.lower() for k, v in mapping.items()}
    prior_keys = list(record.data.keys())
    # Note : warning: do not create a new dict.
    for key in prior_keys:
        if key.lower() in mapping:
            record.rename_field(key=key, new_key=mapping[key.lower()])

    return record


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class AISeLibrarySearchSource(JsonSchemaMixin):

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "https://aisel.aisnet.org/"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.settings = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for AIS electronic Library (AISeL)"""

        result = {"confidence": 0.0}
        # TBD: aisel does not return bibtex?!
        nr_ais_links = data.count("https://aisel.aisnet.org/")
        nr_items = data.count("\n@")
        if nr_items > 0:
            result["confidence"] = nr_ais_links / nr_items

        return result

    def run_search(self, search_operation: colrev.ops.search.Search) -> None:
        """Run a search of the AIS electronic Library (AISeL)"""

        search_operation.review_manager.logger.info(
            "Automated search not (yet) supported."
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for AIS electronic Library (AISeL)"""

        return records

    def prepare(self, record: colrev.record.PrepRecord) -> colrev.record.Record:
        """Source-specific preparation for the AIS electronic Library (AISeL)"""

        # pylint: disable=too-many-branches
        ais_mapping: dict = {}
        record = apply_field_mapping(record=record, mapping=ais_mapping)

        # Note : simple heuristic
        # but at the moment, AISeLibrary only indexes articles and conference papers
        if (
            record.data.get("volume", "UNKNOWN") != "UNKNOWN"
            or record.data.get("number", "UNKNOWN") != "UNKNOWN"
        ) and not any(
            x in record.data.get("journal", "")
            for x in [
                "HICSS",
                "ICIS",
                "ECIS",
                "AMCIS",
                "Proceedings",
                "All Sprouts Content",
            ]
        ):
            record.data["ENTRYTYPE"] = "article"
            if "journal" not in record.data and "booktitle" in record.data:
                record.rename_field(key="booktitle", new_key="journal")
            if (
                "journal" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):
                record.rename_field(key="title", new_key="journal")
                record.rename_field(key="chapter", new_key="title")
                record.remove_field(key="publisher")

        else:
            record.data["ENTRYTYPE"] = "inproceedings"
            record.remove_field(key="publisher")
            if record.data.get("volume", "") == "UNKNOWN":
                record.remove_field(key="volume")
            if record.data.get("number", "") == "UNKNOWN":
                record.remove_field(key="number")

            if (
                "booktitle" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):

                record.rename_field(key="title", new_key="booktitle")
                record.rename_field(key="chapter", new_key="title")

            if "journal" in record.data and "booktitle" not in record.data:
                record.rename_field(key="journal", new_key="booktitle")

            if record.data.get("booktitle", "") in [
                "Research-in-Progress Papers",
                "Research Papers",
            ]:
                if "https://aisel.aisnet.org/ecis" in record.data.get("url", ""):
                    record.update_field(
                        key="booktitle", value="ECIS", source="prep_ais_source"
                    )

        if record.data.get("journal", "") == "Management Information Systems Quarterly":
            record.update_field(
                key="journal", value="MIS Quarterly", source="prep_ais_source"
            )

        if "inproceedings" == record.data["ENTRYTYPE"]:
            if "ICIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="International Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "PACIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Pacific-Asia Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ECIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="European Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "AMCIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Americas Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "HICSS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Hawaii International Conference on System Sciences",
                    source="prep_ais_source",
                )
            if "MCIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Mediterranean Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ACIS" in record.data["booktitle"]:
                record.update_field(
                    key="booktitle",
                    value="Australasian Conference on Information Systems",
                    source="prep_ais_source",
                )

        if "abstract" in record.data:
            if "N/A" == record.data["abstract"]:
                record.remove_field(key="abstract")
        if "author" in record.data:
            record.update_field(
                key="author",
                value=record.data["author"].replace("\n", " "),
                source="prep_ais_source",
                keep_source_if_equal=True,
            )

        return record


if __name__ == "__main__":
    pass
