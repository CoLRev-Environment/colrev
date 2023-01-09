#! /usr/bin/env python
"""SearchSource: Unknown source (default for all other sources)"""
from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import dacite
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin
from thefuzz import fuzz

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

    HTML_CLEANER = re.compile("<.*?>")

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
        # pylint: disable=too-many-statements

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
                record.rename_field(key="title", new_key="chapter")

        if "UNKNOWN" != record.data.get("author", "UNKNOWN"):

            # fix name format
            if (1 == len(record.data["author"].split(" ")[0])) or (
                ", " not in record.data["author"]
            ):
                record.update_field(
                    key="author",
                    value=colrev.record.PrepRecord.format_author_field(
                        input_string=record.data["author"]
                    ),
                    source="unkown_source_prep",
                    keep_source_if_equal=True,
                )

        if "UNKNOWN" != record.data.get("title", "UNKNOWN"):
            record.format_if_mostly_upper(key="title")

        if "date" in record.data and "year" not in record.data:
            year = re.search(r"\d{4}", record.data["date"])
            if year:
                record.update_field(
                    key="year",
                    value=year.group(0),
                    source="unkown_source_prep",
                    keep_source_if_equal=True,
                )

        if "UNKNOWN" != record.data.get("journal", "UNKNOWN"):
            if len(record.data["journal"]) > 10 and "UNKNOWN" != record.data["journal"]:
                record.format_if_mostly_upper(key="journal", case="title")

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

        if "UNKNOWN" != record.data.get("booktitle", "UNKNOWN"):
            if (
                "UNKNOWN" != record.data["booktitle"]
                and "inbook" != record.data["ENTRYTYPE"]
            ):
                record.format_if_mostly_upper(key="booktitle", case="title")

                stripped_btitle = re.sub(r"\d{4}", "", record.data["booktitle"])
                stripped_btitle = re.sub(r"\d{1,2}th", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}nd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}rd", "", stripped_btitle)
                stripped_btitle = re.sub(r"\d{1,2}st", "", stripped_btitle)
                stripped_btitle = re.sub(r"\([A-Z]{3,6}\)", "", stripped_btitle)
                stripped_btitle = stripped_btitle.replace(
                    "Proceedings of the", ""
                ).replace("Proceedings", "")
                stripped_btitle = stripped_btitle.lstrip().rstrip()
                record.update_field(
                    key="booktitle",
                    value=stripped_btitle,
                    source="unkown_source_prep",
                    keep_source_if_equal=True,
                )

        record.unify_pages_field()
        if "pages" in record.data:
            if (
                not re.match(r"^\d*$", record.data["pages"])
                and not re.match(r"^\d*--\d*$", record.data["pages"])
                and not re.match(r"^[xivXIV]*--[xivXIV]*$", record.data["pages"])
            ):
                self.review_manager.report_logger.info(
                    f' {record.data["ID"]}:'.ljust(padding, " ")
                    + f'Unusual pages: {record.data["pages"]}'
                )

        if "UNKNOWN" != record.data.get("volume", "UNKNOWN"):
            record.update_field(
                key="volume",
                value=record.data["volume"].replace("Volume ", ""),
                source="unkown_source_prep",
                keep_source_if_equal=True,
            )

        if "url" in record.data and "fulltext" in record.data:
            if record.data["url"] == record.data["fulltext"]:
                record.remove_field(key="fulltext")

        if "language" in record.data:
            # gh_issue https://github.com/geritwagner/colrev/issues/64
            # use https://pypi.org/project/langcodes/
            record.update_field(
                key="language",
                value=record.data["language"]
                .replace("English", "eng")
                .replace("ENG", "eng"),
                source="unkown_source_prep",
                keep_source_if_equal=True,
            )

        for field in list(record.data.keys()):
            # Note : some dois (and their provenance) contain html entities
            if field in [
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "doi",
            ]:
                continue
            if field in ["author", "title", "journal"]:
                record.data[field] = re.sub(r"\s+", " ", record.data[field])
                record.data[field] = re.sub(self.HTML_CLEANER, "", record.data[field])

        if "article" == record.data["ENTRYTYPE"]:
            if "journal" in record.data and "booktitle" in record.data:
                if (
                    fuzz.partial_ratio(
                        record.data["journal"].lower(), record.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    record.remove_field(key="booktitle")
        if "inproceedings" == record.data["ENTRYTYPE"]:
            if "journal" in record.data and "booktitle" in record.data:
                if (
                    fuzz.partial_ratio(
                        record.data["journal"].lower(), record.data["booktitle"].lower()
                    )
                    / 100
                    > 0.9
                ):
                    record.remove_field(key="journal")

        if record.data.get("publisher", "") in ["researchgate.net"]:
            record.remove_field(key="publisher")

        # Replace nicknames in parentheses
        if "author" in record.data:
            record.data["author"] = re.sub(r"\([^)]*\)", "", record.data["author"])
            record.data["author"] = record.data["author"].replace("  ", " ").rstrip()

        return record


if __name__ == "__main__":
    pass
