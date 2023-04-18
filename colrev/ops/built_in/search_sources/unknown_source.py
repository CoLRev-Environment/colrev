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

import colrev.env.language_service
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

    source_identifier = "colrev.unknown_source"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = False
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.na
    short_name = "Unknown Source"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/unknown_source.md"
    )

    HTML_CLEANER = re.compile("<.*?>")
    __padding = 40

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
        self.language_service = colrev.env.language_service.LanguageService()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for unknown sources"""

        result = {"confidence": 0.0}

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

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

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of Crossref"""

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Not implemented"""
        return record

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for unknown sources"""

        return records

    def __heuristically_fix_entrytypes(
        self, *, record: colrev.record.PrepRecord, source_identifier: str
    ) -> None:
        """Prepare the record by heuristically correcting erroneous ENTRYTYPEs"""

        # Journal articles should not have booktitles/series set.
        if record.data["ENTRYTYPE"] == "article":
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

        if source_identifier == "colrev.md_to_bib":
            if record.data["ENTRYTYPE"] == "misc" and "publisher" in record.data:
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

        if (
            "dissertation" in record.data.get("fulltext", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.update_field(
                key="ENTRYTYPE", value="phdthesis", source="unkown_source_prep"
            )
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(self.__padding, " ")
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
                f' {record.data["ID"]}'.ljust(self.__padding, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in fulltext link)'
            )

        if (
            "this thesis" in record.data.get("abstract", "NA").lower()
            and record.data["ENTRYTYPE"] != "phdthesis"
        ):
            prior_e_type = record.data["ENTRYTYPE"]
            record.update_field(
                key="ENTRYTYPE", value="phdthesis", source="unkown_source_prep"
            )
            self.review_manager.report_logger.info(
                f' {record.data["ID"]}'.ljust(self.__padding, " ")
                + f"Set from {prior_e_type} to phdthesis "
                '("thesis" in abstract)'
            )

    def __format_inproceedings(self, *, record: colrev.record.PrepRecord) -> None:
        if record.data.get("booktitle", "UNKNOWN") == "UNKNOWN":
            return
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
            stripped_btitle = stripped_btitle.replace("Proceedings of the", "").replace(
                "Proceedings", ""
            )
            stripped_btitle = stripped_btitle.lstrip().rstrip()
            record.update_field(
                key="booktitle",
                value=stripped_btitle,
                source="unkown_source_prep",
                keep_source_if_equal=True,
            )

    def __format_article(self, record: colrev.record.PrepRecord) -> None:
        if record.data.get("journal", "UNKNOWN") != "UNKNOWN":
            if len(record.data["journal"]) > 10 and "UNKNOWN" != record.data["journal"]:
                record.format_if_mostly_upper(key="journal", case="title")

        if record.data.get("volume", "UNKNOWN") != "UNKNOWN":
            record.update_field(
                key="volume",
                value=record.data["volume"].replace("Volume ", ""),
                source="unkown_source_prep",
                keep_source_if_equal=True,
            )

    def __format_fields(self, *, record: colrev.record.PrepRecord) -> None:
        """Format fields"""

        if record.data["entrytype"] == "inproceedings":
            self.__format_inproceedings(record=record)
        elif record.data["entrytype"] == "article":
            self.__format_article(record=record)

        if record.data.get("author", "UNKNOWN") != "UNKNOWN":
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
            # Replace nicknames in parentheses
            record.data["author"] = re.sub(r"\([^)]*\)", "", record.data["author"])
            record.data["author"] = record.data["author"].replace("  ", " ").rstrip()

        if record.data.get("title", "UNKNOWN") != "UNKNOWN":
            record.format_if_mostly_upper(key="title")

        if "pages" in record.data:
            record.unify_pages_field()
            if (
                not re.match(r"^\d*$", record.data["pages"])
                and not re.match(r"^\d*--\d*$", record.data["pages"])
                and not re.match(r"^[xivXIV]*--[xivXIV]*$", record.data["pages"])
            ):
                self.review_manager.report_logger.info(
                    f' {record.data["ID"]}:'.ljust(self.__padding, " ")
                    + f'Unusual pages: {record.data["pages"]}'
                )

        if "url" in record.data and "fulltext" in record.data:
            if record.data["url"] == record.data["fulltext"]:
                record.remove_field(key="fulltext")

        if "language" in record.data:
            try:
                self.language_service.unify_to_iso_639_3_language_codes(record=record)
                record.update_field(
                    key="language",
                    value=record.data["language"],
                    source="unkown_source_prep",
                    keep_source_if_equal=True,
                )
            except colrev_exceptions.InvalidLanguageCodeException:
                del record.data["language"]

    def __remove_redundant_fields(self, *, record: colrev.record.PrepRecord) -> None:
        if record.data["ENTRYTYPE"] == "article":
            if "journal" in record.data and "booktitle" in record.data:
                similarity_journal_booktitle = fuzz.partial_ratio(
                    record.data["journal"].lower(), record.data["booktitle"].lower()
                )
                if similarity_journal_booktitle / 100 > 0.9:
                    record.remove_field(key="booktitle")

        if record.data.get("publisher", "") in ["researchgate.net"]:
            record.remove_field(key="publisher")

        if record.data["ENTRYTYPE"] == "inproceedings":
            if "journal" in record.data and "booktitle" in record.data:
                similarity_journal_booktitle = fuzz.partial_ratio(
                    record.data["journal"].lower(), record.data["booktitle"].lower()
                )
                if similarity_journal_booktitle / 100 > 0.9:
                    record.remove_field(key="journal")

    def __impute_missing_fields(self, *, record: colrev.record.PrepRecord) -> None:
        if "date" in record.data and "year" not in record.data:
            year = re.search(r"\d{4}", record.data["date"])
            if year:
                record.update_field(
                    key="year",
                    value=year.group(0),
                    source="unkown_source_prep",
                    keep_source_if_equal=True,
                )

    def __unify_special_characters(self, *, record: colrev.record.PrepRecord) -> None:
        # Remove html entities
        for field in list(record.data.keys()):
            # Skip dois (and their provenance), which may contain html entities
            if field in [
                "colrev_masterdata_provenance",
                "colrev_data_provenance",
                "doi",
            ]:
                continue
            if field in ["author", "title", "journal"]:
                record.data[field] = re.sub(r"\s+", " ", record.data[field])
                record.data[field] = re.sub(self.HTML_CLEANER, "", record.data[field])

    def prepare(
        self, record: colrev.record.PrepRecord, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for unknown sources"""

        if not record.has_inconsistent_fields() or record.masterdata_is_curated():
            return record

        self.__heuristically_fix_entrytypes(
            record=record,
            source_identifier=source.load_conversion_package_endpoint["endpoint"],
        )

        self.__impute_missing_fields(record=record)

        self.__format_fields(record=record)

        self.__remove_redundant_fields(record=record)

        self.__unify_special_characters(record=record)

        return record


if __name__ == "__main__":
    pass
