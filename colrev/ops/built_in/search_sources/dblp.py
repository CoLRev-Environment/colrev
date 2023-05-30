#! /usr/bin/env python
"""SearchSource: DBLP"""
from __future__ import annotations

import html
import json
import re
import typing
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Lock
from pathlib import Path
from sqlite3 import OperationalError
from typing import Optional

import requests
import zope.interface
from dacite import from_dict
from dataclasses_jsonschema import JsonSchemaMixin

import colrev.env.package_manager
import colrev.exceptions as colrev_exceptions
import colrev.ops.search
import colrev.record
import colrev.settings

# pylint: disable=unused-argument
# pylint: disable=duplicate-code


@zope.interface.implementer(
    colrev.env.package_manager.SearchSourcePackageEndpointInterface
)
@dataclass
class DBLPSearchSource(JsonSchemaMixin):
    """SearchSource for DBLP"""

    __api_url = "https://dblp.org/search/publ/api?q="
    __api_url_venues = "https://dblp.org/search/venue/api?q="
    __START_YEAR = 1980

    source_identifier = "dblp_key"
    search_type = colrev.settings.SearchType.DB
    api_search_supported = True
    ci_supported: bool = True
    heuristic_status = colrev.env.package_manager.SearchSourceHeuristicStatus.supported
    short_name = "DBLP"
    link = (
        "https://github.com/CoLRev-Environment/colrev/blob/main/"
        + "colrev/ops/built_in/search_sources/dblp.md"
    )
    __dblp_md_filename = Path("data/search/md_dblp.bib")
    __timeout: int = 10

    @dataclass
    class DBLPSearchSourceSettings(colrev.settings.SearchSource, JsonSchemaMixin):
        """Settings for DBLPSearchSource"""

        # pylint: disable=duplicate-code
        # pylint: disable=too-many-instance-attributes
        endpoint: str
        filename: Path
        search_type: colrev.settings.SearchType
        search_parameters: dict
        load_conversion_package_endpoint: dict
        comment: Optional[str]

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
        source_operation: colrev.operation.Operation,
        settings: Optional[dict] = None,
    ) -> None:
        if settings:
            # DBLP as a search_source
            self.search_source = from_dict(
                data_class=self.settings_class, data=settings
            )
        else:
            # DBLP as an md-prep source
            dblp_md_source_l = [
                s
                for s in source_operation.review_manager.settings.sources
                if s.filename == self.__dblp_md_filename
            ]
            if dblp_md_source_l:
                self.search_source = dblp_md_source_l[0]
            else:
                self.search_source = colrev.settings.SearchSource(
                    endpoint="colrev.dblp",
                    filename=self.__dblp_md_filename,
                    search_type=colrev.settings.SearchType.OTHER,
                    search_parameters={},
                    load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                    comment="",
                )
        self.dblp_lock = Lock()
        self.origin_prefix = self.search_source.get_origin_prefix()
        self.review_manager = source_operation.review_manager

        _, self.email = source_operation.review_manager.get_committer()

    def check_availability(
        self, *, source_operation: colrev.operation.Operation
    ) -> None:
        """Check status (availability) of DBLP API"""

        try:
            # pylint: disable=duplicate-code
            test_rec = {
                "ENTRYTYPE": "article",
                "doi": "10.17705/1cais.04607",
                "author": "Schryen, Guido and Wagner, Gerit and Benlian, Alexander "
                "and Paré, Guy",
                "title": "A Knowledge Development Perspective on Literature Reviews: "
                "Validation of a new Typology in the IS Field",
                "ID": "SchryenEtAl2021",
                "journal": "Communications of the Association for Information Systems",
                "volume": "46",
                "year": "2020",
                "colrev_status": colrev.record.RecordState.md_prepared,  # type: ignore
            }

            query = "" + str(test_rec.get("title", "")).replace("-", "_")

            dblp_record = self.__retrieve_dblp_records(
                query=query,
            )[0]

            if 0 != len(dblp_record.data):
                assert dblp_record.data["title"] == test_rec["title"]
                assert dblp_record.data["author"] == test_rec["author"]
            else:
                if not source_operation.force_mode:
                    raise colrev_exceptions.ServiceNotAvailableException("DBLP")
        except requests.exceptions.RequestException as exc:
            if not source_operation.force_mode:
                raise colrev_exceptions.ServiceNotAvailableException("DBLP") from exc

    def __get_dblp_venue(
        self,
        *,
        session: requests.Session,
        venue_string: str,
        venue_type: str,
    ) -> str:
        # Note : venue_string should be like "behaviourIT"
        # Note : journals that have been renamed seem to return the latest
        # journal name. Example:
        # https://dblp.org/db/journals/jasis/index.html
        venue = venue_string
        url = self.__api_url_venues + venue_string.replace(" ", "+") + "&format=json"
        headers = {"user-agent": f"{__name__} (mailto:{self.email})"}
        try:
            ret = session.request("GET", url, headers=headers, timeout=self.__timeout)
            ret.raise_for_status()
            data = json.loads(ret.text)
            if "hit" not in data["result"]["hits"]:
                return ""
            hits = data["result"]["hits"]["hit"]
            for hit in hits:
                if hit["info"]["type"] != venue_type:
                    continue
                if f"/{venue_string.lower()}/" in hit["info"]["url"].lower():
                    venue = hit["info"]["venue"]
                    break

            venue = re.sub(r" \(.*?\)", "", venue)
        except requests.exceptions.RequestException:
            pass
        return venue

    def __dblp_json_set_type(self, *, item: dict, session: requests.Session) -> None:
        if item["type"] == "Withdrawn Items":
            if item["key"][:8] == "journals":
                item["type"] = "Journal Articles"
            if item["key"][:4] == "conf":
                item["type"] = "Conference and Workshop Papers"
            item["warning"] = "Withdrawn (according to DBLP)"

        if item["type"] == "Journal Articles":
            item["ENTRYTYPE"] = "article"
            lpos = item["key"].find("/") + 1
            rpos = item["key"].rfind("/")
            ven_key = item["key"][lpos:rpos]
            item["journal"] = self.__get_dblp_venue(
                session=session,
                venue_string=ven_key,
                venue_type="Journal",
            )
        elif item["type"] == "Conference and Workshop Papers":
            item["ENTRYTYPE"] = "inproceedings"
            lpos = item["key"].find("/") + 1
            rpos = item["key"].rfind("/")
            ven_key = item["key"][lpos:rpos]
            item["booktitle"] = self.__get_dblp_venue(
                session=session,
                venue_string=ven_key,
                venue_type="Conference or Workshop",
            )

    def __dblp_json_to_dict(
        self,
        *,
        session: requests.Session,
        item: dict,
    ) -> dict:
        # To test in browser:
        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        self.__dblp_json_set_type(item=item, session=session)
        if "title" in item:
            item["title"] = item["title"].rstrip(".").rstrip().replace("\n", " ")
            item["title"] = re.sub(r"\s+", " ", item["title"])
        if "pages" in item:
            item["pages"] = item["pages"].replace("-", "--")
        if "authors" in item:
            if "author" in item["authors"]:
                if isinstance(item["authors"]["author"], dict):
                    author_string = item["authors"]["author"]["text"]
                else:
                    authors_nodes = [
                        author
                        for author in item["authors"]["author"]
                        if isinstance(author, dict)
                    ]
                    authors = [x["text"] for x in authors_nodes if "text" in x]
                    author_string = " and ".join(authors)
                author_string = colrev.record.PrepRecord.format_author_field(
                    input_string=author_string
                )
                item["author"] = author_string

        if "key" in item:
            item["dblp_key"] = "https://dblp.org/rec/" + item["key"]

        if "doi" in item:
            item["doi"] = item["doi"].upper()
        if "ee" in item:
            if not any(
                x in item["ee"] for x in ["https://doi.org", "https://dblp.org"]
            ):
                item["url"] = item["ee"]

        item = {
            k: v
            for k, v in item.items()
            if k not in ["venue", "type", "access", "key", "ee", "authors"]
        }
        for key, value in item.items():
            item[key] = html.unescape(value).replace("{", "").replace("}", "")

        return item

    def __retrieve_dblp_records(
        self,
        *,
        query: Optional[str] = None,
        url: Optional[str] = None,
    ) -> list:
        """Retrieve records from DBLP based on a query"""

        # https://dblp.org/search/publ/api?q=ADD_TITLE&format=json

        try:
            assert query is not None or url is not None
            session = self.review_manager.get_cached_session()
            items = []

            if query:
                query = re.sub(r"[\W]+", " ", query.replace(" ", "_"))
                url = self.__api_url + query.replace(" ", "+") + "&format=json"

            headers = {"user-agent": f"{__name__}  (mailto:{self.email})"}
            # review_manager.logger.debug(url)
            ret = session.request(
                "GET", url, headers=headers, timeout=self.__timeout  # type: ignore
            )
            ret.raise_for_status()
            if ret.status_code == 500:
                return []

            data = json.loads(ret.text)
            if "hits" not in data["result"]:
                return []
            if "hit" not in data["result"]["hits"]:
                return []
            hits = data["result"]["hits"]["hit"]
            items = [hit["info"] for hit in hits]
            dblp_dicts = [
                self.__dblp_json_to_dict(
                    session=session,
                    item=item,
                )
                for item in items
            ]
            retrieved_records = [
                colrev.record.PrepRecord(data=dblp_dict) for dblp_dict in dblp_dicts
            ]
            for retrieved_record in retrieved_records:
                # Note : DBLP provides number-of-pages (instead of pages start-end)
                if "pages" in retrieved_record.data:
                    del retrieved_record.data["pages"]
                retrieved_record.add_provenance_all(
                    source=retrieved_record.data["dblp_key"]
                )

        # pylint: disable=duplicate-code
        except OperationalError as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "sqlite, required for requests CachedSession "
                "(possibly caused by concurrent operations)"
            ) from exc
        except (requests.exceptions.ReadTimeout, requests.exceptions.HTTPError) as exc:
            raise colrev_exceptions.ServiceNotAvailableException(
                "requests timed out "
                "(possibly because the DBLP service is temporarily not available)"
            ) from exc

        return retrieved_records

    def validate_source(
        self,
        search_operation: colrev.ops.search.Search,
        source: colrev.settings.SearchSource,
    ) -> None:
        """Validate the SearchSource (parameters etc.)"""

        search_operation.review_manager.logger.debug(
            f"Validate SearchSource {source.filename}"
        )

        # maybe : validate/assert that the venue_key is available
        if "scope" in source.search_parameters:
            if "venue_key" not in source.search_parameters["scope"]:
                raise colrev_exceptions.InvalidQueryException(
                    "venue_key required in search_parameters/scope"
                )
            if "journal_abbreviated" not in source.search_parameters["scope"]:
                raise colrev_exceptions.InvalidQueryException(
                    "journal_abbreviated required in search_parameters/scope"
                )
        elif "query" in source.search_parameters:
            assert source.search_parameters["query"].startswith(self.__api_url)
        elif source.is_md_source() or source.is_quasi_md_source():
            pass  # No parameters required
        else:
            raise colrev_exceptions.InvalidQueryException(
                "scope or query required in search_parameters"
            )

        search_operation.review_manager.logger.debug(
            f"SearchSource {source.filename} validated"
        )

    def __run_md_search_update(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        dblp_feed: colrev.ops.search.GeneralOriginFeed,
    ) -> None:
        records = search_operation.review_manager.dataset.load_records_dict()

        for feed_record_dict in dblp_feed.feed_records.values():
            feed_record = colrev.record.Record(data=feed_record_dict)
            query = "" + feed_record.data.get("title", "").replace("-", "_")
            for retrieved_record in self.__retrieve_dblp_records(
                query=query,
            ):
                if retrieved_record.data["dblp_key"] != feed_record.data["dblp_key"]:
                    continue

                try:
                    dblp_feed.set_id(record_dict=retrieved_record.data)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if retrieved_record.data["ID"] in dblp_feed.feed_records:
                    prev_record_dict_version = dblp_feed.feed_records[
                        retrieved_record.data["ID"]
                    ]

                dblp_feed.add_record(record=retrieved_record)
                changed = search_operation.update_existing_record(
                    records=records,
                    record_dict=retrieved_record.data,
                    prev_record_dict_version=prev_record_dict_version,
                    source=self.search_source,
                    update_time_variant_fields=True,
                )
                if changed:
                    dblp_feed.nr_changed += 1

        dblp_feed.print_post_run_search_infos(records=records)
        dblp_feed.save_feed_file()
        search_operation.review_manager.dataset.save_records_dict(records=records)
        search_operation.review_manager.dataset.add_record_changes()

    def __run_param_search_year_batch(
        self,
        *,
        query: str,
        search_operation: colrev.ops.search.Search,
        dblp_feed: colrev.ops.search.GeneralOriginFeed,
        records: dict,
        rerun: bool,
    ) -> None:
        batch_size_cumulative = 0
        batch_size = 250
        while True:
            url = (
                query.replace(" ", "+")
                + f"&format=json&h={batch_size}&f={batch_size_cumulative}"
            )
            batch_size_cumulative += batch_size

            retrieved = False
            for retrieved_record in self.__retrieve_dblp_records(url=url):
                retrieved = True

                if (
                    "scope" in self.search_source.search_parameters
                    and (
                        f"{self.search_source.search_parameters['scope']['venue_key']}/"
                        not in retrieved_record.data["dblp_key"]
                    )
                ) or retrieved_record.data.get("ENTRYTYPE", "") not in [
                    "article",
                    "inproceedings",
                ]:
                    continue

                try:
                    dblp_feed.set_id(record_dict=retrieved_record.data)
                except colrev_exceptions.NotFeedIdentifiableException:
                    continue

                prev_record_dict_version = {}
                if retrieved_record.data["ID"] in dblp_feed.feed_records:
                    prev_record_dict_version = dblp_feed.feed_records[
                        retrieved_record.data["ID"]
                    ]

                added = dblp_feed.add_record(
                    record=retrieved_record,
                )

                if added:
                    self.review_manager.logger.info(
                        " retrieve " + retrieved_record.data["dblp_key"]
                    )
                    dblp_feed.nr_added += 1

                else:
                    changed = search_operation.update_existing_record(
                        records=records,
                        record_dict=retrieved_record.data,
                        prev_record_dict_version=prev_record_dict_version,
                        source=self.search_source,
                        update_time_variant_fields=rerun,
                    )
                    if changed:
                        dblp_feed.nr_changed += 1

            if not retrieved:
                break

        dblp_feed.save_feed_file()
        self.review_manager.dataset.save_records_dict(records=records)
        self.review_manager.dataset.add_record_changes()

    def __get_query(self, *, year: int) -> str:
        if "scope" in self.search_source.search_parameters:
            # Note : journal_abbreviated is the abbreviated venue_key
            query = (
                self.__api_url
                + self.search_source.search_parameters["scope"]["journal_abbreviated"]
                + "+"
                + str(year)
            )
            # query = params['scope']["venue_key"] + "+" + str(year)
        elif "query" in self.search_source.search_parameters:
            query = self.search_source.search_parameters["query"] + "+" + str(year)
        return query

    def __run_parameter_search(
        self,
        *,
        search_operation: colrev.ops.search.Search,
        dblp_feed: colrev.ops.search.GeneralOriginFeed,
        rerun: bool,
    ) -> None:
        records = self.review_manager.dataset.load_records_dict()
        try:
            start = self.__START_YEAR
            if len(dblp_feed.feed_records) > 100 and not rerun:
                start = datetime.now().year - 2

            for year in range(start, datetime.now().year + 1):
                self.review_manager.logger.debug(f"Retrieve year {year}")
                self.__run_param_search_year_batch(
                    query=self.__get_query(year=year),
                    search_operation=search_operation,
                    dblp_feed=dblp_feed,
                    records=records,
                    rerun=rerun,
                )

            dblp_feed.print_post_run_search_infos(records=records)

        except (requests.exceptions.RequestException,):
            pass

    def run_search(
        self, search_operation: colrev.ops.search.Search, rerun: bool
    ) -> None:
        """Run a search of DBLP"""

        search_operation.review_manager.logger.debug(
            f"Retrieve DBLP: {self.search_source.search_parameters}"
        )

        dblp_feed = self.search_source.get_feed(
            review_manager=search_operation.review_manager,
            source_identifier=self.source_identifier,
            update_only=(not rerun),
        )

        if self.search_source.is_md_source() or self.search_source.is_quasi_md_source():
            self.__run_md_search_update(
                search_operation=search_operation,
                dblp_feed=dblp_feed,
            )

        else:
            self.__run_parameter_search(
                search_operation=search_operation,
                dblp_feed=dblp_feed,
                rerun=rerun,
            )

    @classmethod
    def heuristic(cls, filename: Path, data: str) -> dict:
        """Source heuristic for DBLP"""

        result = {"confidence": 0.0}
        # Simple heuristic:
        if "dblp_key" in data:
            result["confidence"] = 1.0
            return result

        if "dblp computer science bibliography" in data:
            if data.count("dblp computer science bibliography") >= data.count("\n@"):
                result["confidence"] = 1.0

        return result

    @classmethod
    def add_endpoint(
        cls, search_operation: colrev.ops.search.Search, query: str
    ) -> colrev.settings.SearchSource:
        """Add SearchSource as an endpoint (based on query provided to colrev search -a )"""

        if (
            "https://dblp.org/search?q=" in query
            or "https://dblp.org/search/publ?q=" in query
        ):
            query = query.replace("https://dblp.org/search?q=", cls.__api_url).replace(
                "https://dblp.org/search/publ?q=", cls.__api_url
            )

            filename = search_operation.get_unique_filename(
                file_path_string=f"dblp_{query.replace(cls.__api_url, '')}"
            )
            add_source = colrev.settings.SearchSource(
                endpoint="colrev.dblp",
                filename=filename,
                search_type=colrev.settings.SearchType.DB,
                search_parameters={"query": query},
                load_conversion_package_endpoint={"endpoint": "colrev.bibtex"},
                comment="",
            )
            return add_source

        raise colrev_exceptions.PackageParameterError(
            f"Cannot add backward_search endpoint with query {query}"
        )

    def load_fixes(
        self,
        load_operation: colrev.ops.load.Load,
        source: colrev.settings.SearchSource,
        records: typing.Dict,
    ) -> dict:
        """Load fixes for DBLP"""

        return records

    def prepare(
        self, record: colrev.record.Record, source: colrev.settings.SearchSource
    ) -> colrev.record.Record:
        """Source-specific preparation for DBLP"""

        if record.data.get("author", "UNKNOWN") != "UNKNOWN":
            # DBLP appends identifiers to non-unique authors
            record.update_field(
                key="author",
                value=str(re.sub(r"[0-9]{4}", "", record.data["author"])),
                source="dblp",
                keep_source_if_equal=True,
            )
        record.remove_field(key="bibsource")
        if any(x in record.data.get("url", "") for x in ["dblp.org", "doi.org"]):
            record.remove_field(key="url")
        record.remove_field(key="timestamp")

        return record

    def get_masterdata(
        self,
        prep_operation: colrev.ops.prep.Prep,
        record: colrev.record.Record,
        save_feed: bool = True,
        timeout: int = 10,
    ) -> colrev.record.Record:
        """Retrieve masterdata from DBLP based on similarity with the record provided"""

        if any(self.origin_prefix in o for o in record.data["colrev_origin"]):
            # Already linked to a crossref record
            return record

        same_record_type_required = (
            prep_operation.review_manager.settings.is_curated_masterdata_repo()
        )
        self.__timeout = timeout

        try:
            # Note: queries combining title+author/journal do not seem to work any more
            query = "" + record.data.get("title", "").replace("-", "_")
            for retrieved_record in self.__retrieve_dblp_records(
                query=query,
            ):
                if "dblp_key" in record.data:
                    if retrieved_record.data["dblp_key"] != record.data["dblp_key"]:
                        continue

                similarity = colrev.record.PrepRecord.get_retrieval_similarity(
                    record_original=record,
                    retrieved_record_original=retrieved_record,
                    same_record_type_required=same_record_type_required,
                )
                if similarity > prep_operation.retrieval_similarity:
                    try:
                        self.dblp_lock.acquire(timeout=60)

                        # Note : need to reload file
                        # because the object is not shared between processes
                        dblp_feed = self.search_source.get_feed(
                            review_manager=prep_operation.review_manager,
                            source_identifier=self.source_identifier,
                            update_only=False,
                        )

                        dblp_feed.set_id(record_dict=retrieved_record.data)
                        dblp_feed.add_record(record=retrieved_record)

                        record.merge(
                            merging_record=retrieved_record,
                            default_source=retrieved_record.data["colrev_origin"][0],
                        )
                        record.set_masterdata_complete(
                            source=retrieved_record.data["colrev_origin"][0],
                            masterdata_repository=self.review_manager.settings.is_curated_repo(),
                        )
                        record.set_status(
                            target_state=colrev.record.RecordState.md_prepared
                        )
                        if "Withdrawn (according to DBLP)" in record.data.get(
                            "warning", ""
                        ):
                            record.prescreen_exclude(reason="retracted")
                            record.remove_field(key="warning")

                        dblp_feed.save_feed_file()
                        self.dblp_lock.release()
                        return record

                    except (
                        colrev_exceptions.InvalidMerge,
                        colrev_exceptions.NotFeedIdentifiableException,
                    ):
                        self.dblp_lock.release()
                        continue

        except requests.exceptions.RequestException:
            pass

        return record
