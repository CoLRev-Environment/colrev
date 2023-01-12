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
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class AISeLibrarySearchSource(JsonSchemaMixin):
    """SearchSource for the AIS electronic Library (AISeL)"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "url"
    search_type = colrev.settings.SearchType.DB
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "AIS eLibrary"
    link = "https://aisel.aisnet.org/"

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for AIS electronic Library (AISeL)"""

        result = {"confidence": 0.0}
        # TBD: aisel does not return bibtex?!
        nr_ais_links = data.count("https://aisel.aisnet.org/")
        nr_items = data.count("\n@")
        if nr_items > 0 and "colrev_status" not in data:
            result["confidence"] = nr_ais_links / nr_items

        if "%T " in data and "colrev_status" not in data:
            if data.count("%U https://aisel.aisnet.org") > 0.9 * data.count("%T "):
                result["confidence"] = 1.0

        if "@article" in data or "@inproc" in data and "colrev_status" not in data:
            if data.count("https://aisel.aisnet.org") > 0.9 * data.count("\n@"):
                result["confidence"] = 1.0

        return result

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "query_file" not in source.search_parameters:
            raise colrev_exceptions.InvalidQueryException(
                f"Source missing query_file search_parameter ({source.filename})"
            )

        if not Path(source.search_parameters["query_file"]).is_file():
            raise colrev_exceptions.InvalidQueryException(
                f"File does not exist: query_file {source.search_parameters['query_file']} "
                f"for ({source.filename})"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for AIS electronic Library (AISeL)"""

        return records

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for the AIS electronic Library (AISeL)"""

        # pylint: disable=too-many-branches
        ais_mapping: dict = {}
        record.rename_fields_based_on_mapping(mapping=ais_mapping)

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

            if (
                "journal" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):
                record.rename_field(key="title", new_key="journal")
                record.rename_field(key="chapter", new_key="title")
                record.remove_field(key="publisher")

            record.change_entrytype(new_entrytype="article")

        else:

            record.remove_field(key="publisher")

            if (
                "booktitle" not in record.data
                and "title" in record.data
                and "chapter" in record.data
            ):

                record.rename_field(key="title", new_key="booktitle")
                record.rename_field(key="chapter", new_key="title")

            record.change_entrytype(new_entrytype="inproceedings")

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
            if "ICIS" in record.data.get("booktitle", ""):
                record.update_field(
                    key="booktitle",
                    value="International Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "PACIS" in record.data.get("booktitle", ""):
                record.update_field(
                    key="booktitle",
                    value="Pacific-Asia Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ECIS" in record.data.get("booktitle", ""):
                record.update_field(
                    key="booktitle",
                    value="European Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "AMCIS" in record.data.get("booktitle", ""):
                record.update_field(
                    key="booktitle",
                    value="Americas Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "HICSS" in record.data.get("booktitle", ""):
                record.update_field(
                    key="booktitle",
                    value="Hawaii International Conference on System Sciences",
                    source="prep_ais_source",
                )
            if "MCIS" in record.data.get("booktitle", ""):
                record.update_field(
                    key="booktitle",
                    value="Mediterranean Conference on Information Systems",
                    source="prep_ais_source",
                )
            if "ACIS" in record.data.get("booktitle", ""):
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
