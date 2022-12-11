#! /usr/bin/env python
"""SearchSource: Unknown source (default for all other sources)"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import dacite
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
class UnknownSearchSource(JsonSchemaMixin):
    """SearchSource for unknown search results"""

    settings_class = colrev.env.package_manager.DefaultSourceSettings

    source_identifier = "colrev_built_in.unknown_source"
    search_type = colrev.settings.SearchType.DB
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.na
    short_name = "Unknown Source"
    link = (
        "https://github.com/geritwagner/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/unknown_source.py"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:

        converters = {Path: Path, Enum: Enum}
        self.search_source = from_dict(
            data_class=self.settings_class,
            data=settings,
            config=dacite.Config(type_hooks=converters, cast=[Enum]),  # type: ignore
        )
        self.review_manager = source_operation.review_manager

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for unknown sources"""

        result = {"confidence": 0.0}

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

        if "query_file" in source.search_parameters:
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
        """Load fixes for unknown sources"""

        return records

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for unknown sources"""

        # pylint: disable=too-many-branches

        if not record.has_inconsistent_fields() or record.masterdata_is_curated():
            return record

        if (
            "colrev_built_in.md_to_bib"
            == source.load_conversion_package_endpoint["endpoint"]
        ):
            if "misc" == record.data["ENTRYTYPE"] and "publisher" in record.data:
                record.update_field(
                    key="ENTRYTYPE", value="book", source="unkown_source_prep"
                )
            if record.data.get("year", "year") == record.data.get("date", "date"):
                record.remove_field(key="date")
            if (
                "inbook" == record.data["ENTRYTYPE"]
                and "chapter" not in record.data
                and "title" in record.data
            ):
                # TODO : check update_field/append_edit for rename_field?
                record.rename_field(key="title", new_key="chapter")

        # Prepare the record by heuristically correcting erroneous ENTRYTYPEs
        padding = 40

        if (
            "dissertation" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.update_field(
                key="ENTRYTYPE", value="phdthesis", source="unkown_source_prep"
            )
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(padding, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("dissertation" in fulltext link)'
            )

        if (
            "thesis" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.update_field(
                key="ENTRYTYPE", value="phdthesis", source="unkown_source_prep"
            )
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(padding, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "This thesis" in record.data.get("abstract", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.update_field(
                key="ENTRYTYPE", value="phdthesis", source="unkown_source_prep"
            )
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(padding, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

        # Journal articles should not have booktitles/series set.
        if "article" == record.data["ENTRYTYPE"]:
            if "booktitle" in record.data:
                if "journal" not in record.data:
                    record.update_field(
                        key="journal",
                        value=record.data["booktitle"],
                        source="unkown_source_prep",
                    )
                    record.remove_field(key="booktitle")
            if "series" in record.data:
                if "journal" not in record.data:
                    record.update_field(
                        key="journal",
                        value=record.data["series"],
                        source="unkown_source_prep",
                    )
                    record.remove_field(key="series")

        if "article" == record.data["ENTRYTYPE"]:
            if "journal" not in record.data:
                if "series" in record.data:
                    journal_string = record.data["series"]
                    record.update_field(
                        key="journal", value=journal_string, source="unkown_source_prep"
                    )
                    record.remove_field(key="series")

        return record


if __name__ == "__main__":
    pass
