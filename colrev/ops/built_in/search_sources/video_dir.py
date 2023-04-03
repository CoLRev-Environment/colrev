#! /usr/bin/env python
"""SearchSource: directory containing video files"""
from __future__ import annotations

import typing
from dataclasses import dataclass
from multiprocessing import Lock
from pathlib import Path

import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.built_in.search_sources.website as website_connector
import colrev.ops.search
import colrev.record
import colrev.ui_cli.cli_colors as colors

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class VideoDirSearchSource(JsonSchemaMixin):
    """SearchSource for directory containing video files"""

    # pylint: disable=too-many-instance-attributes

    settings_class = colrev.env.package_manager.DefaultSourceSettings
    source_identifier = "file"
    search_type = colrev.settings.SearchType.OTHER
    api_search_supported = True
    ci_supported: bool = False
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "Video directory"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/video_dir.md"
    )

    def __init__(
        self, *, source_operation: colrev.operation.CheckOperation, settings: dict
    ) -> None:
        self.search_source = from_dict(data_class=self.settings_class, data=settings)
        self.source_operation = source_operation
        self.pdf_preparation_operation = (
            source_operation.review_manager.get_pdf_prep_operation(
                notify_state_transition_operation=False
            )
        )

        self.video_path = source_operation.review_manager.path / Path(
            self.search_source.search_parameters["scope"]["path"]
        )
        self.review_manager = source_operation.review_manager
        self.prep_operation = self.review_manager.get_prep_operation()
        self.url_connector = website_connector.WebsiteConnector(
            source_operation=self.prep_operation
        )
        self.zotero_lock = Lock()

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        if "path" not in source.search_parameters["scope"]:
            raise colrev_exceptions.InvalidQueryException(
                "path required in search_parameters/scope"
            )
        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __index_video(self, *, path: Path) -> dict:
        record_dict = {"ENTRYTYPE": "online", "file": path}
        return record_dict

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of a directory containing videos"""

        search_operation.review_manager.logger.info(
            f"{colors.ORANGE}For better metadata, please add the url "
            f"(or authors and title){colors.END}"
        )

        video_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        overall_files = [
            x.relative_to(search_operation.review_manager.path)
            for x in self.video_path.glob("**/*.mp4")
        ]

        new_records_added = 0
        for file_to_add in overall_files:
            new_record = self.__index_video(path=file_to_add)

            try:
                video_feed.set_id(record_dict=new_record)
            except colrev_exceptions.NotFeedIdentifiableException:
                continue

            added = video_feed.add_record(
                record=colrev.record.Record(data=new_record),
            )
            if added:
                new_records_added += 1

        video_feed.save_feed_file()

        search_operation.review_manager.logger.info(
            f"New videos added: {new_records_added}"
        )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for video directories"""

        result = {"confidence": 0.0}
        if filename.suffix in [".mp4"]:
            result["confidence"] = 1.0
            return result
        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> typing.Optional[colrev.settings.SearchSource]:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""
        return None

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
        """Load fixes for video directories"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for video directories"""

        if "url" in record.data:
            self.zotero_lock = Lock()
            url_record = record.copy_prep_rec()
            self.url_connector.retrieve_md_from_website(
                record=url_record, prep_operation=self.prep_operation
            )
            if url_record.data.get("author", "") != "":
                record.update_field(
                    key="author", value=url_record.data["author"], source="website"
                )
            if url_record.data.get("title", "") != "":
                record.update_field(
                    key="title", value=url_record.data["title"], source="website"
                )
            self.zotero_lock.release()

        return record


if __name__ == "__main__":
    pass
