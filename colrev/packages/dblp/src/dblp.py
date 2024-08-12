#! /usr/bin/env python
"""SearchSource: DBLP"""
from __future__ import annotations

import re
import typing
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Lock
from pathlib import Path

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.exceptions as colrev_exceptions
import colrev.package_manager.interfaces
import colrev.package_manager.package_manager
import colrev.package_manager.package_settings
import colrev.record.record
import colrev.record.record_prep
import colrev.record.record_similarity
import colrev.settings
from colrev.constants import Fields
from colrev.constants import FieldValues
from colrev.constants import RecordState
from colrev.constants import SearchSourceHeuristicStatus
from colrev.constants import SearchType
from colrev.packages.dblp.src import dblp_api

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(colrev.package_manager.interfaces.SearchSourceInterface)
@dataclass
class DBLPSearchSource(JsonSchemaMixin):
    """DBLP API"""

    _api_url = "https://dblp.org/search/publ/api?q="
    _START_YEAR = 1980

    source_identifier = "dblp_key"
    search_types = [
        SearchType.API,
        SearchType.MD,
        SearchType.TOC,
    ]
    endpoint = "colrev.dblp"

    ci_supported: bool = True
    heuristic_status = SearchSourceHeuristicStatus.supported
    short_name = "DBLP"

    _dblp_md_filename = Path("data/search/md_dblp.bib")
    _timeout: int = 10

    @dataclass
    class DBLPSearchSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
        """Settings for DBLPSearchSource"""

        # pylint: disable=duplicate-code
        # pylint: disable=too-many-instance-attributes
        endpoint: str
        filename: Path
        search_type: SearchType
        search_parameters: dict
        comment: typing.Optional[str]

        _details = {
            "search_parameters": {
                "tooltip": "Currently supports a scope item "
                "with venue_key and journal_abbreviated fields."
            },
        }

    settings_class = DBLPSearchSourceSettings

    def __init__(
        self,
        *,
        source_operation: colrev.process.operation.Operation,
        settings: typing.Optional[dict] = None,
    ) -> None:
        self.review_manager = source_operation.review_manager
        self.search_source = self._get_search_source(settings)
        self.dblp_lock = Lock()
        self.origin_prefix = self.search_source.get_origin_prefix()

        _, self.email = self.review_manager.get_committer()

    def _get_search_source(
        self, settings: typing.Optional[dict]
    ) -> colrev.settings.SearchSource:
        if settings:
            # DBLP as a search_source
            return from_dict(data_class=self.settings_class, data=settings)
        # DBLP as an md-prep source
        dblp_md_source_l = [
            s
            for s in self.review_manager.settings.sources
            if s.filename == self._dblp_md_filename
        ]
        if dblp_md_source_l:
            return dblp_md_source_l[0]

        return colrev.settings.SearchSource(
            endpoint=self.endpoint,
            filename=self._dblp_md_filename,
            search_type=SearchType.MD,
            search_parameters={},
            comment="",
        )

    def check_availability(
        self, *, source_operation: colrev.process.operation.Operation
    ) -> None:
        """Check status (availability) of DBLP API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                Fields.ENTRYTYPE: "article",
                Fields.DOI: "10.17705/1cais.04607",
                Fields.AUTHOR: "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                Fields.TITLE: "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                Fields.ID: "SchryenEtAl2021",
                Fields.JOURNAL: "Communications of the Association for Information Systems",
                Fields.VOLUME: "46",
                Fields.YEAR: "2020",
                Fields.STATUS: RecordState.md_prepared,  # type: ignore
            }

            api = dblp_api.DBLPAPI(
                email=self.email,
                session=self.review_manager.get_cached_session(),
                query=str(test_rec[Fields.TITLE]),
                timeout=self._timeout,
            )

            retrieved_records = api.retrieve_records()
            dblp_record = retrieved_records[0]

            if 0 != len(dblp_record.data):
                assert dblp_record.data[Fields.TITLE] == test_rec[Fields.TITLE]
                assert dblp_record.data[Fields.AUTHOR] == test_rec[Fields.AUTHOR]
            else:
                if not self.review_manager.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("DBLP")
        except requests.exceptions.RequestException as exc:
            if not self.review_manager.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("DBLP") from exc

    def _validate_source(self) -> None:
        """Validate the SearchSource (parameters etc.)"""
        source = self.search_source
        self.review_manager.logger.debug(f"Validate SearchSource {source.filename}")

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

        self.review_manager.logger.debug(f"SearchSource {source.filename} validated")

    def _run_md_search(
        self,
        *,
        dblp_feed: colrev.ops.search_api_feed.SearchAPIFeed,
    ) -> None:

        api = dblp_api.DBLPAPI(
            email=self.email,
            session=self.review_manager.get_cached_session(),
            query="",
            timeout=self._timeout,
        )

        for feed_record_dict in dblp_feed.feed_records.values():
            if Fields.TITLE not in feed_record_dict:
                continue
            api.set_url_from_query(feed_record_dict[Fields.TITLE])
            for retrieved_record in api.retrieve_records():
                try:
                    if (
                        retrieved_record.data["dblp_key"]
                        != feed_record_dict["dblp_key"]
                    ):
                        continue
                    if retrieved_record.data.get("type", "") == "Editorship":
                        continue

                    dblp_feed.add_update_record(retrieved_record)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

        dblp_feed.save()

    def _run_param_search_year_batch(
        self,
        *,
        dblp_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        year: int,
    ) -> None:
        batch_size_cumulative = 0
        batch_size = 250
        api = dblp_api.DBLPAPI(
            email=self.email,
            session=self.review_manager.get_cached_session(),
            url="",
            timeout=self._timeout,
        )
        while True:
            batch_size_cumulative += batch_size
            api.url = self._get_url(
                year=year,
                batch_size=batch_size,
                batch_size_cumulative=batch_size_cumulative,
            )

            retrieved = False
            for retrieved_record in api.retrieve_records():
                try:
                    retrieved = True

                    if (
                        "scope" in self.search_source.search_parameters
                        and (
                            f"{self.search_source.search_parameters['scope']['venue_key']}/"
                            not in retrieved_record.data["dblp_key"]
                        )
                    ) or retrieved_record.data.get(Fields.ENTRYTYPE, "") not in [
                        "article",
                        "inproceedings",
                    ]:
                        continue

                    dblp_feed.add_update_record(retrieved_record)

                except colrev_exceptions.NotFeedIdentifiableException as exc:
                    print(exc)
                    continue

            if not retrieved:
                break

    def _get_url(
        self, *, year: int, batch_size: int, batch_size_cumulative: int
    ) -> str:
        if "scope" in self.search_source.search_parameters:
            # Note : journal_abbreviated is the abbreviated venue_key
            query = (
                self._api_url
                + self.search_source.search_parameters["scope"]["journal_abbreviated"]
                + "+"
                + str(year)
            )
            # query = params['scope']["venue_key"] + "+" + str(year)
        elif "query" in self.search_source.search_parameters:
            query = self.search_source.search_parameters["query"] + "+" + str(year)
        return (
            query.replace(" ", "+")
            + f"&format=json&h={batch_size}&f={batch_size_cumulative}"
        )

    def _run_api_search(
        self,
        *,
        dblp_feed: colrev.ops.search_api_feed.SearchAPIFeed,
        rerun: bool,
    ) -> None:
        try:
            start = self._START_YEAR
            if len(dblp_feed.feed_records) > 100 and not rerun:
                start = datetime.now().year - 2

            for year in range(start, datetime.now().year + 1):
                self.review_manager.logger.debug(f"Retrieve year {year}")
                self._run_param_search_year_batch(dblp_feed=dblp_feed, year=year)
            dblp_feed.save()

        except (requests.exceptions.RequestException,):
            pass

    def search(self, rerun: bool) -> None:
        """Run a search of DBLP"""

        self._validate_source()

        dblp_feed = self.search_source.get_api_feed(
            review_manager=self.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
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
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search --add )"""

        params_dict = {}
        if params:
            if params.startswith("http"):
                params_dict = {Fields.URL: params}
            else:
                for item in params.split(";"):
                    key, value = item.split("=")
                    params_dict[key] = value

        search_type = operation.select_search_type(
            search_types=cls.search_types, params=params_dict
        )

        if search_type == SearchType.API:
            if len(params_dict) == 0:
                search_source = operation.create_api_source(endpoint=cls.endpoint)

            # pylint: disable=colrev-missed-constant-usage
            elif "url" in params_dict:
                query = (
                    params_dict["url"]
                    .replace("https://dblp.org/search?q=", cls._api_url)
                    .replace("https://dblp.org/search/publ?q=", cls._api_url)
                )

                filename = operation.get_unique_filename(file_path_string="dblp")
                search_source = colrev.settings.SearchSource(
                    endpoint=cls.endpoint,
                    filename=filename,
                    search_type=SearchType.API,
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

    def load(self, load_operation: colrev.ops.load.Load) -> dict:
        """Load the records from the SearchSource file"""

        if self.search_source.filename.suffix == ".bib":

            def field_mapper(record_dict: dict) -> None:
                if "timestamp" in record_dict:
                    record_dict[f"{self.endpoint}.timestamp"] = record_dict.pop(
                        "timestamp"
                    )
                if "biburl" in record_dict:
                    record_dict[f"{self.endpoint}.biburl"] = record_dict.pop("biburl")
                if "bibsource" in record_dict:
                    record_dict[f"{self.endpoint}.bibsource"] = record_dict.pop(
                        "bibsource"
                    )
                if "dblp_key" in record_dict:
                    record_dict[Fields.DBLP_KEY] = record_dict.pop("dblp_key")

            records = colrev.loader.load_utils.load(
                filename=self.search_source.filename,
                unique_id_field="ID",
                field_mapper=field_mapper,
                logger=self.review_manager.logger,
            )
            return records

        raise NotImplementedError

    def prepare(
        self,
        record: colrev.record.record_prep.PrepRecord,
        source: colrev.settings.SearchSource,
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

        self._timeout = timeout

        try:

            # Note: queries combining title+author/journal do not seem to work any more
            api = dblp_api.DBLPAPI(
                email=self.email,
                session=self.review_manager.get_cached_session(),
                query=record.data[Fields.TITLE],
                timeout=self._timeout,
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
                dblp_feed = self.search_source.get_api_feed(
                    review_manager=self.review_manager,
                    source_identifier=self.source_identifier,
                    update_only=False,
                    prep_mode=True,
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

                dblp_feed.save()
                self.dblp_lock.release()

            except (colrev_exceptions.NotFeedIdentifiableException,):
                self.dblp_lock.release()

        except requests.exceptions.RequestException:
            pass
        except colrev_exceptions.ServiceNotAvailableException:
            if self.review_manager.force_mode:
                self.review_manager.logger.error("Service not available: DBLP")

        return record
