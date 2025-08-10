#! /usr/bin/env python
"""SearchSource: DBLP"""
from __future__ import annotations

import logging
import re
import typing
from multiprocessing import Lock
from pathlib import Path
from typing import Optional

import requests
from pydantic import BaseModel
from pydantic import Field

import colrev.exceptions as colrev_exceptions
import colrev.ops.search_api_feed
from colrev.ops.search_api_feed import create_api_source
import colrev.package_manager.package_base_classes as base_classes
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.search_file
import colrev.utils
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.dblp.src import dblp_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


class DBLPSearchSourceSettings(colrev.search_file.ExtendedSearchFile, BaseModel):
    """Settings for DBLPSearchSource"""

    # pylint: disable=duplicate-code
    # pylint: disable=too-many-instance-attributes
    platform: str
    filepath: Path
    search_type: SearchType
    search_parameters: dict
    version: typing.Optional[str]
    comment: typing.Optional[str]

    _details = {
        "search_parameters": {
            "tooltip": "Currently supports a scope item "
            "with venue_key and journal_abbreviated fields."
        },
    }


class DBLPSearchSource(base_classes.SearchSourcePackageBaseClass):
    """DBLP API"""

    source_identifier = "dblp_key"
    search_types = [
        SearchType.API,
        SearchType.MD,
        SearchType.TOC,
    ]
    endpoint = "colrev.dblp"

    ci_supported: bool = Field(default=True)
    heuristic_status = SearchSourceHeuristicStatus.supported

    settings_class = DBLPSearchSourceSettings

    _timeout: int = 20

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        search_file: colrev.search_file.ExtendedSearchFile,
        logger: Optional[logging.Logger] = None,
        verbose_mode: bool = False,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_mode = verbose_mode
        self.review_manager = source_operation.review_manager
        self.search_source = search_file
        self.dblp_lock = Lock()
        self.origin_prefix = self.search_source.get_origin_prefix()
        _, self.email = self.review_manager.get_committer()

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for DBLP"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        # pylint: disable=colrev-missed-constant-usage
        if "dblp_key" in data:
            result["confidence"] = 1.0
            return result

        if "dblp computer science bibliography" in data:
            if data.count("dblp computer science bibliography") >= data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls,
        operation: colrev.ops.search.Search,
        params: str,
    ) -> colrev.search_file.ExtendedSearchFile:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = colrev.utils.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = create_api_source(
                    platform=cls.endpoint, path=operation.review_manager.path
                )

            # pylint: disable=colrev-missed-constant-usage
            elif "url" in params_dict:
                api_url = "https://dblp.org/search/publ/api?q="
                query = (
                    params_dict["url"]
                    .replace("https://dblp.org/search?q=", api_url)
                    .replace("https://dblp.org/search/publ?q=", api_url)
                )

                filename = colrev.utils.get_unique_filename(
                    base_path=operation.review_manager.path,
                    file_path_string="dblp",
                )
                search_source = colrev.search_file.ExtendedSearchFile(
                    platform=cls.endpoint,
                    search_results_path=filename,
                    search_type=SearchType.API,
                    search_string="",
                    search_parameters={"query": query},
                    comment="",
                )
            else:
                raise NotImplementedError

        # elif search_type == SearchType.TOC:
        else:
            raise colrev_exceptions.PackageParameterError(
                f"Cannot add dblp endpoint with query {params}"
            )

        operation.add_source_and_search(search_source)
        return search_source

    def check_availability(self) -> None:
        """Check status (availability) of DBLP API"""
        api = dblp_api.DBLPAPI(
            params={},
            email=self.email,
            session=colrev.utils.get_cached_session(),
            timeout=self._timeout,
        )
        api.check_availability()

    def _run_md_search(
        self,
        *,
        dblp_feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:

        api = dblp_api.DBLPAPI(
            params={},
            email=self.email,
            session=colrev.utils.get_cached_session(),
            rerun=True,
            timeout=self._timeout,
        )

        for feed_record_dict in dblp_feed.feed_records.values():
            if Fields.TITLE not in feed_record_dict:
                continue
            api.params = {"query": feed_record_dict[Fields.TITLE]}
            api.set_url_from_query()
            for retrieved_record in api.retrieve_records():
                try:
                    if (
                        retrieved_record.data["dblp_key"]
                        != feed_record_dict["dblp_key"]
                    ) or retrieved_record.data.get("type", "") == "Editorship":
                        continue

                    dblp_feed.add_update_record(retrieved_record)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

        dblp_feed.save()

    def _run_api_search(
        self,
        *,
        dblp_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:

        api = dblp_api.DBLPAPI(
            params=self.search_source.search_parameters,
            email=self.email,
            session=colrev.utils.get_cached_session(),
            rerun=(len(dblp_feed.feed_records) < 100 or rerun),
            timeout=self._timeout,
        )

        total = api.total
        self.logger.info(f"Total: {total:,}")
        if not rerun and len(dblp_feed.feed_records) > 0:
            self.logger.info("Retrieving latest results (no estimate available)")
        elif total > 0 and rerun:
            seconds = 10 + (total / 10)
            if total > 1000:
                seconds += total / 100 * 60  # request timeouts

            formatted_time = (
                str(int(seconds // 3600)).zfill(2)
                + ":"
                + str(int((seconds % 3600) // 60)).zfill(2)
                + ":"
                + str(int(seconds % 60)).zfill(2)
            )

            self.logger.info("Estimated runtime [hh:mm:ss]: %s", formatted_time)

        while True:
            api.set_next_url()

            for retrieved_record in api.retrieve_records():
                try:

                    if "scope" in self.search_source.search_parameters and (
                        f"{self.search_source.search_parameters['scope']['venue_key']}/"
                        not in retrieved_record.data["dblp_key"]
                        or retrieved_record.data.get(Fields.ENTRYTYPE, "")
                        not in [
                            "article",
                            "inproceedings",
                        ]
                    ):
                        continue

                    dblp_feed.add_update_record(retrieved_record)

                except colrev_exceptions.NotFeedIdentifiableException as exc:
                    print(exc)
                    continue

            if api.processed_all_urls():
                break

        dblp_feed.save()

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""
        source = self.search_source
        self.logger.debug(f"Validate SearchSource {source.search_results_path}")

        assert source.search_type in self.search_types

        # maybe : validate/assert that the venue_key is available
        if source.search_type == SearchType.TOC:
            assert "scope" in source.search_parameters
            if "venue_key" not in source.search_parameters["scope"]:
                raise colrev_exceptions.InvalidQueryException(
                    "venue_key required in search_parameters/scope"
                )
            if "journal_abbreviated" not in source.search_parameters["scope"]:
                raise colrev_exceptions.InvalidQueryException(
                    "journal_abbreviated required in search_parameters/scope"
                )
        elif source.search_type == SearchType.API:
            assert "query" in source.search_parameters

        elif source.search_type == SearchType.MD:
            pass  # No parameters required
        else:
            raise colrev_exceptions.InvalidQueryException(
                "scope or query required in search_parameters"
            )

        self.logger.debug("SearchSource %s validated", source.search_results_path)

    def search(self, rerun: bool) -> None:
        """Run a search of DBLP"""

        self._validate_source()

        dblp_feed = colrev.ops.search_api_feed.SearchAPIFeed(
            source_identifier=self.source_identifier,
            search_source=self.search_source,
            update_only=(not rerun),
            logger=self.logger,
            verbose_mode=self.verbose_mode,
        )
        if self.search_source.search_type == SearchType.MD:
            self._run_md_search(dblp_feed=dblp_feed)

        elif self.search_source.search_type in [
            SearchType.API,
            SearchType.TOC,
        ]:
            self._run_api_search(dblp_feed=dblp_feed, rerun=rerun)

        else:
            raise NotImplementedError

    @classmethod
    def load(cls, *, filename: Path, logger: logging.Logger) -> dict:
        """Load the records from the SearchSource file"""

        if filename.suffix == ".bib":

            def field_mapper(record_dict: dict) -> None:
                if "timestamp" in record_dict:
                    record_dict[f"{cls.endpoint}.timestamp"] = record_dict.pop(
                        "timestamp"
                    )
                if "biburl" in record_dict:
                    record_dict[f"{cls.endpoint}.biburl"] = record_dict.pop("biburl")
                if "bibsource" in record_dict:
                    record_dict[f"{cls.endpoint}.bibsource"] = record_dict.pop(
                        "bibsource"
                    )
                if "dblp_key" in record_dict:
                    record_dict[Fields.DBLP_KEY] = record_dict.pop("dblp_key")

            records = colrev.loader.load_utils.load(
                filename=filename,
                unique_id_field="ID",
                field_mapper=field_mapper,
                logger=logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
    ) -> colrev.record.record_prep.PrepRecord:
        """Source-specific preparation for DBLP"""

        if record.data.get(Fields.AUTHOR, FieldValues.UNKNOWN) != FieldValues.UNKNOWN:
            # DBLP appends identifiers to non-unique authors
            record.update_field(
                key=Fields.AUTHOR,
                value=str(re.sub(r"[0-9]{4}", "", record.data[Fields.AUTHOR])),
                source="dblp",
                keep_source_if_equal=True,
            )
        record.remove_field(key="colrev.dblp.bibsource")
        if any(x in record.data.get(Fields.URL, "") for x in ["dblp.org", "doi.org"]):
            record.remove_field(key=Fields.URL)
        record.remove_field(key="colrev.dblp.timestamp")

        return record

    def prep_link_md(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.record.Record,
        save_feed: bool = True,
        timeout: int = 60,
    ) -> colrev.record.record.Record:
        """Retrieve masterdata from DBLP based on similarity with the record provided"""

        if any(self.origin_prefix in o for o in record.data[Fields.ORIGIN]):
            # Already linked to a crossref record
            return record
        if Fields.TITLE not in record.data:
            return record

        try:

            # Note: queries combining title+author/journal do not seem to work any more
            api = dblp_api.DBLPAPI(
                params={"query": record.data[Fields.TITLE]},
                email=self.email,
                session=colrev.utils.get_cached_session(),
                timeout=timeout,
            )

            retrieved_records = api.retrieve_records()
            if not retrieved_records:
                return record
            retrieved_record = retrieved_records[0]
            if Fields.DBLP_KEY in record.data:
                if retrieved_record.data["dblp_key"] != record.data[Fields.DBLP_KEY]:
                    return record

            if not colrev.record.record_similarity.matches(record, retrieved_record):
                return record

            try:
                self.dblp_lock.acquire(timeout=60)

                # Note : need to reload file
                # because the object is not shared between processes
                dblp_feed = colrev.ops.search_api_feed.SearchAPIFeed(
                    source_identifier=self.source_identifier,
                    search_source=self.search_source,
                    update_only=False,
                    prep_mode=True,
                    records=self.review_manager.dataset.load_records_dict(),
                    logger=self.logger,
                    verbose_mode=self.verbose_mode,
                )

                dblp_feed.add_update_record(retrieved_record)

                # Assign schema
                retrieved_record.data[Fields.DBLP_KEY] = retrieved_record.data.pop(
                    "dblp_key"
                )

                record.merge(
                    retrieved_record,
                    default_source=retrieved_record.data[Fields.ORIGIN][0],
                )
                record.set_masterdata_complete(
                    source=retrieved_record.data[Fields.ORIGIN][0],
                    masterdata_repository=self.review_manager.settings.is_curated_repo(),
                )
                record.set_status(RecordState.md_prepared)
                if "Withdrawn (according to DBLP)" in record.data.get(
                    "colrev.dblp.warning", ""
                ):
                    record.prescreen_exclude(reason=FieldValues.RETRACTED)
                    # record.remove_field(key="warning")

                self.review_manager.dataset.save_records_dict(
                    dblp_feed.get_records(),
                )
                dblp_feed.save()
                self.dblp_lock.release()

            except (colrev_exceptions.NotFeedIdentifiableException,):
                self.dblp_lock.release()

        except requests.exceptions.RequestException:
            pass
        except colrev_exceptions.ServiceNotAvailableException:
            if self.review_manager.force_mode:
                self.logger.error("Service not available: DBLP")

        return record
